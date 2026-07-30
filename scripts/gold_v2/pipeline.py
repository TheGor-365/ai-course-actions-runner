#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authority import validate_manifest
from .common import MODE_RANK, RunnerError, canonical_json_bytes, consume_single_use, load_json, scan_sensitive, sha256_file
from .gitops import assert_clean, checkout_exact, git_blob_sha, run_command, verify_bound_file, verify_remote_branch_tip
from .stages import StageMixin


class GoldV2Pipeline(StageMixin):
    def __init__(self, *, manifest_path: Path, mode: str, workspace: Path, single_use_ledger: Path | None = None, execution_runner_head: str | None = None) -> None:
        self.manifest_path = manifest_path.resolve()
        self.mode = mode
        self.workspace = workspace.resolve()
        self.single_use_ledger = single_use_ledger.resolve() if single_use_ledger else None
        self.execution_runner_head = execution_runner_head
        self.manifest: dict[str, Any] = {}
        self.repos: dict[str, Path] = {}
        self.receipt: dict[str, Any] = {
            "schema_version": "gold_v2_runner_release_receipt.v1",
            "result": "BLOCKED",
            "mode": mode,
            "acceptance_state": "UNACCEPTED_EXECUTION_EVIDENCE",
            "workflow_dispatched": False,
            "still_render_started": False,
            "video_render_started": False,
            "main_merge_performed": False,
            "production_authority_duplicated": False,
            "no_fake_green": True,
            "stages": [],
        }

    def _stage(self, name: str, result: str = "PASS", **extra: Any) -> None:
        self.receipt["stages"].append({"stage": name, "result": result, **extra})

    @staticmethod
    def _repo_url(repository: str) -> str:
        if repository.startswith(("/", "file://", "https://", "ssh://", "git@")):
            return repository
        return f"https://github.com/{repository}.git"

    def _checkout(self, key: str, repository: str, head: str, ancestor: str | None = None) -> None:
        path = self.workspace / "repos" / key
        receipt = checkout_exact(self._repo_url(repository), head, path, required_ancestor=ancestor)
        self.repos[key] = path
        self.receipt.setdefault("exact_head_leases", {})[key] = receipt

    def _checkout_repositories(self) -> None:
        self._checkout("control", self.manifest["control_repository"], self.manifest["control_head"])
        verify_remote_branch_tip(self.repos["control"], self.manifest["control_branch"], self.manifest["control_head"])
        for key, repo_field, head_field, ancestor_field in (
            ("source", "source_repository", "source_head", "source_required_ancestor"),
            ("shared_source", "shared_source_repository", "shared_source_head", "shared_source_required_ancestor"),
            ("production", "production_repository", "production_head", "production_required_ancestor"),
            ("runner", "runner_repository", "runner_head", "runner_required_ancestor"),
        ):
            self._checkout(key, self.manifest[repo_field], self.manifest[head_field], self.manifest.get(ancestor_field))
        if MODE_RANK[self.mode] >= MODE_RANK["compile"]:
            if self.manifest["compiler_head"] == self.manifest["production_head"]:
                self.repos["compiler"] = self.repos["production"]
            else:
                self._checkout("compiler", self.manifest["production_repository"], self.manifest["compiler_head"], self.manifest.get("compiler_required_ancestor"))
        if MODE_RANK[self.mode] >= MODE_RANK["pre-render-evidence"]:
            if self.manifest["runtime_head"] == self.manifest["production_head"]:
                self.repos["runtime"] = self.repos["production"]
            else:
                self._checkout("runtime", self.manifest["production_repository"], self.manifest["runtime_head"], self.manifest.get("runtime_required_ancestor"))
        self._stage("exact_head_checkouts", repository_count=len(self.repos))

    def _verify_oc(self) -> None:
        repo = self.repos["control"]
        path = repo / self.manifest["control_path"]
        if not path.is_file():
            raise RunnerError("CONTROL_DOCUMENT_MISSING")
        if git_blob_sha(repo, self.manifest["control_path"]) != self.manifest["oc_blob_sha"]:
            raise RunnerError("CONTROL_BLOB_SHA_MISMATCH")
        text = path.read_text(encoding="utf-8")
        markers = (
            f"DOCUMENT_ID={self.manifest['oc_document_id']}",
            f"RUNNER_AUTHORIZATION_MANIFEST_ID={self.manifest['manifest_id']}",
            f"RUNNER_AUTHORIZED_MODE={self.manifest['mode']}",
            f"RUNNER_AUTHORIZATION_PAYLOAD_SHA256={self.manifest['authorization_payload_sha256']}",
        )
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise RunnerError(f"OC_AUTHORIZATION_BINDING_MISSING:{missing}")
        self._stage("live_control", document_id=self.manifest["oc_document_id"], authorization_payload_sha256=self.manifest["authorization_payload_sha256"])

    def _verify_source_identity(self) -> None:
        package = self.repos["source"] / self.manifest["source_package_path"]
        if not package.is_file():
            raise RunnerError("SOURCE_PACKAGE_MISSING")
        digest = sha256_file(package)
        if digest != self.manifest["source_package_sha256"]:
            raise RunnerError("SOURCE_PACKAGE_SHA256_MISMATCH")
        self.receipt["source_package"] = {
            "path": self.manifest["source_package_path"],
            "sha256": digest,
            "git_blob_sha": git_blob_sha(self.repos["source"], self.manifest["source_package_path"]),
        }
        self._stage("source_package_identity")

    def _verify_bindings(self) -> None:
        observed: list[dict[str, Any]] = []
        values = [*self.manifest["bindings"], *self.manifest["schema_bindings"], *self.manifest.get("accepted_media_bindings", [])]
        for binding in values:
            key = binding["repo"]
            if key not in self.repos:
                raise RunnerError(f"BINDING_REPOSITORY_NOT_CHECKED_OUT:{key}")
            observed.append({"repo": key, **verify_bound_file(self.repos[key], binding)})
        self.receipt["verified_bindings"] = observed
        self._stage("shared_id_and_schema_bindings", binding_count=len(observed))

    def _command_values(self, **extra: str) -> dict[str, str]:
        values = {f"{key}_repo": str(path) for key, path in self.repos.items()}
        values.update({
            "workspace": str(self.workspace),
            "source_package": str(self.repos["source"] / self.manifest["source_package_path"]),
            "manifest": str(self.manifest_path),
        })
        values.update(extra)
        return values

    def _run_named(self, name: str, **values: str) -> dict[str, Any]:
        receipt = run_command(self.manifest["commands"][name], self.repos, self._command_values(**values), self.workspace / "logs" / f"{name}.log")
        self.receipt.setdefault("command_receipts", {})[name] = receipt
        return receipt

    def _validate_only(self) -> None:
        for name in ("source_materialize", "source_validate", "shared_id_validate", "schema_validate", "archive_prereq_validate"):
            self._run_named(name)
            for repo in set(self.repos.values()):
                assert_clean(repo)
        self._stage("validate_only")

    def _finalize(self) -> Path:
        for repo in set(self.repos.values()):
            assert_clean(repo)
        self.receipt["result"] = "PASS"
        self.receipt["provenance"] = {
            "manifest_id": self.manifest["manifest_id"],
            "control_head": self.manifest["control_head"],
            "source_head": self.manifest["source_head"],
            "shared_source_head": self.manifest["shared_source_head"],
            "production_head": self.manifest["production_head"],
            "runner_head": self.manifest["runner_head"],
        }
        self.receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        path = self.workspace / "release_receipt.json"
        path.write_bytes(canonical_json_bytes(self.receipt))
        scan_sensitive("release_receipt.json", path.read_bytes())
        return path

    def run(self) -> Path:
        if self.workspace.exists():
            raise RunnerError("WORKSPACE_ALREADY_EXISTS")
        self.workspace.mkdir(parents=True)
        try:
            self.manifest = validate_manifest(load_json(self.manifest_path), self.mode)
            if self.execution_runner_head is not None and self.execution_runner_head != self.manifest["runner_head"]:
                raise RunnerError("EXECUTION_RUNNER_HEAD_MISMATCH")
            self.receipt["execution_runner_head"] = self.execution_runner_head
            self.receipt["manifest_id"] = self.manifest["manifest_id"]
            self.receipt["acceptance_state"] = self.manifest["acceptance_state"]
            if self.manifest.get("single_use_id"):
                if self.single_use_ledger is None:
                    raise RunnerError("SINGLE_USE_LEDGER_REQUIRED")
                consume_single_use(self.manifest["single_use_id"], self.single_use_ledger)
            self._checkout_repositories()
            self._verify_oc()
            self._verify_source_identity()
            self._verify_bindings()
            self._validate_only()
            if MODE_RANK[self.mode] >= MODE_RANK["compile"]:
                self._compile()
            if MODE_RANK[self.mode] >= MODE_RANK["pre-render-evidence"]:
                self._pre_render_evidence()
            if self.mode == "render":
                self._render()
            return self._finalize()
        except Exception as exc:
            self.receipt["result"] = "BLOCKED"
            self.receipt["error"] = str(exc)
            self.receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            (self.workspace / "blocked_receipt.json").write_bytes(canonical_json_bytes(self.receipt))
            raise
