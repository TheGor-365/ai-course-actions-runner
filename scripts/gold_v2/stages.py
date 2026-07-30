#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Mapping

from .archive import ArchivePolicy, deterministic_zip, inspect_archive
from .artifacts import build_human_review_queue, file_set_hashes, require_exact_file_set, write_sha256sums
from .common import RunnerError, canonical_json_bytes, load_json, sha256_file
from .gitops import assert_clean, git_blob_sha


class StageMixin:
    manifest: dict[str, Any]
    workspace: Path
    repos: dict[str, Path]
    receipt: dict[str, Any]

    def _stage(self, name: str, result: str = "PASS", **extra: Any) -> None: ...
    def _run_named(self, name: str, *, receipt_key: str | None = None, log_name: str | None = None, **values: str) -> dict[str, Any]: ...
    def _fresh_checkout(self, key: str, destination: Path, lease_name: str) -> Path: ...

    def _package_directory(
        self,
        root: Path,
        *,
        archive_name: str,
        artifact_kind: str,
        acceptance_state: str,
        receipt_schemas: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        payload_hashes = file_set_hashes(root)
        final_file_set = sorted(set(payload_hashes) | {"artifact_receipt.json", "archive_descriptor.json", "SHA256SUMS"})
        provenance = {
            "manifest_id": self.manifest["manifest_id"],
            "authorization_payload_sha256": self.manifest["authorization_payload_sha256"],
            "oc_document_id": self.manifest["oc_document_id"],
            "control_head": self.manifest["control_head"],
            "source_head": self.manifest["source_head"],
            "shared_source_head": self.manifest["shared_source_head"],
            "production_head": self.manifest["production_head"],
            "runner_head": self.manifest["runner_head"],
        }
        for name in ("compiler_head", "runtime_head"):
            if name in self.manifest:
                provenance[name] = self.manifest[name]
        artifact_receipt = {
            "schema_version": "gold_v2_runner_artifact_receipt.v1",
            "result": "PASS",
            "artifact_kind": artifact_kind,
            "acceptance_state": acceptance_state,
            "exact_file_set": final_file_set,
            "payload_file_sha256": payload_hashes,
            "provenance": provenance,
            "secrets_or_private_payload_present": False,
            "no_fake_green": True,
        }
        descriptor = {
            "schema_version": "gold_v2_runner_archive_descriptor.v1",
            "artifact_kind": artifact_kind,
            "acceptance_state": acceptance_state,
            "exact_file_set": final_file_set,
            "checksums_path": "SHA256SUMS",
            "max_file_count": 4096,
            "max_member_bytes": 67108864,
            "max_total_bytes": 536870912,
            "max_compression_ratio": 200.0,
            "provenance": provenance,
            "no_fake_green": True,
        }
        (root / "artifact_receipt.json").write_bytes(canonical_json_bytes(artifact_receipt))
        (root / "archive_descriptor.json").write_bytes(canonical_json_bytes(descriptor))
        write_sha256sums(root, file_set_hashes(root))
        observed = file_set_hashes(root)
        require_exact_file_set(observed, final_file_set, "ARTIFACT_EXACT_FILE_SET_MISMATCH")
        archive_path = self.workspace / "artifacts" / archive_name
        archive_sha = deterministic_zip(root, archive_path, final_file_set)
        schemas = {
            "artifact_receipt.json": "gold_v2_runner_artifact_receipt.v1",
            "archive_descriptor.json": "gold_v2_runner_archive_descriptor.v1",
        }
        schemas.update(receipt_schemas or {})
        policy = ArchivePolicy(
            expected_files=frozenset(final_file_set),
            receipt_schemas=schemas,
            expected_archive_sha256=archive_sha,
            forbidden_suffixes=frozenset({".env", ".pem", ".key", ".p12"}),
        )
        return {
            "archive_path": str(archive_path.relative_to(self.workspace)),
            "archive_sha256": archive_sha,
            "acceptance_state": acceptance_state,
            "exact_file_set": final_file_set,
            "security_receipt": inspect_archive(archive_path, policy),
        }

    def _compile(self) -> None:
        runs_root = self.workspace / "compile-runs"
        first, second = runs_root / "run-1", runs_root / "run-2"
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        original_compiler_repo = self.repos["compiler"]
        try:
            run_one_repo = self._fresh_checkout("compiler", self.workspace / "compile-checkouts" / "run-1", "compiler_run_1")
            self.repos["compiler"] = run_one_repo
            self._run_named("compiler", receipt_key="compiler_run_1", log_name="compiler-run-1", output_dir=str(first))
            assert_clean(run_one_repo)

            run_two_repo = self._fresh_checkout("compiler", self.workspace / "compile-checkouts" / "run-2", "compiler_run_2")
            self.repos["compiler"] = run_two_repo
            self._run_named("compiler", receipt_key="compiler_run_2", log_name="compiler-run-2", output_dir=str(second))
            assert_clean(run_two_repo)
        finally:
            self.repos["compiler"] = original_compiler_repo

        first_hashes = file_set_hashes(first)
        second_hashes = file_set_hashes(second)
        expected_files = self.manifest["expected_outputs"]["compiler_files"]
        require_exact_file_set(first_hashes, expected_files, "COMPILER_EXACT_FILE_SET_MISMATCH")
        require_exact_file_set(second_hashes, expected_files, "COMPILER_EXACT_FILE_SET_MISMATCH")
        if first_hashes != second_hashes:
            raise RunnerError("COMPILER_REPRODUCIBILITY_FAILED")
        artifact_path = self.manifest["compiler_artifact_path"]
        if first_hashes.get(artifact_path) != self.manifest["compiler_artifact_sha256"]:
            raise RunnerError("COMPILER_ARTIFACT_SHA256_MISMATCH")

        stage = self.workspace / "artifacts" / "compiler"
        stage.mkdir(parents=True)
        for relative in sorted(expected_files):
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(first / relative, target)
        receipt = {
            "schema_version": "gold_v2_runner_compiler_receipt.v1",
            "result": "PASS",
            "acceptance_state": "UNACCEPTED_EXECUTION_EVIDENCE",
            "compiler_head": self.manifest["compiler_head"],
            "source_head": self.manifest["source_head"],
            "shared_source_head": self.manifest["shared_source_head"],
            "two_run_byte_identical": True,
            "independent_exact_checkouts": True,
            "exact_file_set": sorted(expected_files),
            "file_sha256": first_hashes,
            "no_fake_green": True,
        }
        (stage / "compiler_receipt.json").write_bytes(canonical_json_bytes(receipt))
        write_sha256sums(stage, file_set_hashes(stage))
        hashes = file_set_hashes(stage)
        descriptor = {
            "schema_version": "gold_v2_runner_archive_descriptor.v1",
            "artifact_kind": "COMPILER_EXECUTION_EVIDENCE",
            "acceptance_state": "UNACCEPTED_EXECUTION_EVIDENCE",
            "exact_file_set": sorted([*hashes, "archive_descriptor.json"]),
            "checksums_path": "SHA256SUMS",
            "max_file_count": 4096,
            "max_member_bytes": 67108864,
            "max_total_bytes": 536870912,
            "max_compression_ratio": 200.0,
            "provenance": {
                "authorization_payload_sha256": self.manifest["authorization_payload_sha256"],
                "control_head": self.manifest["control_head"],
                "source_head": self.manifest["source_head"],
                "production_head": self.manifest["production_head"],
                "runner_head": self.manifest["runner_head"],
                "compiler_head": self.manifest["compiler_head"],
            },
            "no_fake_green": True,
        }
        (stage / "archive_descriptor.json").write_bytes(canonical_json_bytes(descriptor))
        write_sha256sums(stage, file_set_hashes(stage))
        exact_files = sorted(file_set_hashes(stage))
        archive_path = self.workspace / "artifacts" / "compiler-execution-evidence.zip"
        archive_sha = deterministic_zip(stage, archive_path, exact_files)
        security_receipt = inspect_archive(archive_path, ArchivePolicy(
            expected_files=frozenset(exact_files),
            receipt_schemas={
                "compiler_receipt.json": "gold_v2_runner_compiler_receipt.v1",
                "archive_descriptor.json": "gold_v2_runner_archive_descriptor.v1",
            },
            expected_archive_sha256=archive_sha,
            forbidden_suffixes=frozenset({".env", ".pem", ".key", ".p12"}),
        ))
        self.receipt["compiler"] = {
            "compiler_artifact_path": artifact_path,
            "compiler_artifact_sha256": first_hashes[artifact_path],
            "archive_path": str(archive_path.relative_to(self.workspace)),
            "archive_sha256": archive_sha,
            "security_receipt": security_receipt,
        }
        self._stage("compile", reproducibility="PASS", independent_exact_checkouts=True, archive_security="PASS")

    def _pre_render_evidence(self) -> None:
        root = self.workspace / "artifacts" / "pre-render-evidence"
        root.mkdir(parents=True)
        for name in ("runtime_discovery", "runtime_typecheck", "runtime_tests", "audio_timing_validate", "quality_materialize"):
            self._run_named(name, evidence_dir=str(root))
        self._run_named("dom_evidence", evidence_dir=str(root))
        self.receipt["still_render_started"] = True
        self._run_named("still_evidence", evidence_dir=str(root))
        queue = build_human_review_queue(self.manifest["human_review_gates"])
        (root / "human_review_queue.json").write_bytes(canonical_json_bytes(queue))
        observed = file_set_hashes(root)
        expected = [*self.manifest["expected_outputs"]["pre_render_files"], "human_review_queue.json"]
        require_exact_file_set(observed, expected, "PRE_RENDER_EXACT_FILE_SET_MISMATCH")
        self.receipt["human_review_queue"] = {
            "path": "artifacts/pre-render-evidence/human_review_queue.json",
            "sha256": sha256_file(root / "human_review_queue.json"),
            "result": queue["result"],
            "automatic_aesthetic_pass": False,
        }
        self.receipt["pre_render_artifact"] = self._package_directory(
            root,
            archive_name="pre-render-evidence.zip",
            artifact_kind="PRE_RENDER_EVIDENCE",
            acceptance_state=self.manifest["acceptance_state"],
            receipt_schemas={"human_review_queue.json": "gold_v2_runner_human_review_queue.v1"},
        )
        self._stage("pre_render_evidence", human_review=queue["result"], archive_security="PASS")

    def _verify_receipt_binding(self, name: str) -> None:
        binding = self.manifest[name]
        repo = self.repos["production"]
        path = repo / binding["path"]
        if not path.is_file() or path.is_symlink():
            raise RunnerError(f"{name.upper()}_MISSING")
        if sha256_file(path) != binding["sha256"] or git_blob_sha(repo, binding["path"]) != binding["git_blob_sha"]:
            raise RunnerError(f"{name.upper()}_IDENTITY_MISMATCH")
        data = load_json(path)
        if data.get("result") != "PASS":
            raise RunnerError(f"{name.upper()}_PASS_REQUIRED")

    def _render(self) -> None:
        self._verify_receipt_binding("quality_receipt")
        self._verify_receipt_binding("coordinator_receipt")
        root = self.workspace / "artifacts" / "render"
        root.mkdir(parents=True)
        self.receipt["video_render_started"] = True
        self._run_named("video_render", render_dir=str(root))
        expected = self.manifest["expected_outputs"]
        receipt_relative = expected["render_receipt"]
        receipt_path = root / receipt_relative
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise RunnerError("RENDER_RECEIPT_MISSING")
        render_receipt = load_json(receipt_path)
        if render_receipt.get("schema_version") != expected["render_receipt_schema_version"]:
            raise RunnerError("RENDER_RECEIPT_SCHEMA_MISMATCH")
        if render_receipt.get("composition_id") != self.manifest["composition_id"]:
            raise RunnerError("RENDER_COMPOSITION_MISMATCH")
        if render_receipt.get("duration_ms") != self.manifest["duration_ms"]:
            raise RunnerError("RENDER_DURATION_MISMATCH")
        observed = file_set_hashes(root)
        require_exact_file_set(observed, expected["render_files"], "RENDER_EXACT_FILE_SET_MISMATCH")
        self.receipt["acceptance_state"] = self.manifest["acceptance_state"]
        self.receipt["render"] = {
            "composition_id": self.manifest["composition_id"],
            "duration_ms": self.manifest["duration_ms"],
            "file_sha256": observed,
        }
        self.receipt["render_artifact"] = self._package_directory(
            root,
            archive_name="render-release.zip",
            artifact_kind="PRODUCTION_RENDER" if self.manifest["artifact_class"] == "PRODUCTION" else "PREVIEW_RENDER",
            acceptance_state=self.manifest["acceptance_state"],
            receipt_schemas={receipt_relative: expected["render_receipt_schema_version"]},
        )
        self._stage("render", archive_security="PASS")
