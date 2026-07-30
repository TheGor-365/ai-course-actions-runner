#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

from .authority import validate_manifest
from .common import (
    MODE_RANK, RunnerError, canonical_json_bytes, consume_single_use, load_json,
    safe_error_code, scan_sensitive, scrub_transport_environment, sha256_bytes, sha256_file,
)
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

    def _fresh_checkout(self, key: str, destination: Path, lease_name: str) -> Path:
        if key == "compiler":
            repository, head, ancestor = (
                self.manifest["production_repository"], self.manifest["compiler_head"],
                self.manifest.get("compiler_required_ancestor"),
            )
        elif key == "runtime":
            repository, head, ancestor = (
                self.manifest["production_repository"], self.manifest["runtime_head"],
                self.manifest.get("runtime_required_ancestor"),
            )
        else:
            raise RunnerError(f"FRESH_CHECKOUT_KEY_INVALID:{key}")
        lease = checkout_exact(self._repo_url(repository), head, destination, required_ancestor=ancestor)
        self.receipt.setdefault("exact_head_leases", {})[lease_name] = lease
        return destination

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
        scrub_transport_environment()
        self._stage("exact_head_checkouts", repository_count=len(self.repos), transport_credentials_scrubbed=True)

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
            raise RunnerError("OC_AUTHORIZATION_BINDING_MISSING")
        self._stage("live_control", document_id=self.manifest["oc_document_id"], authorization_payload_sha256=self.manifest["authorization_payload_sha256"])

    def _verify_source_identity(self) -> None:
        package = self.repos["source"] / self.manifest["source_package_path"]
        if not package.is_file() or package.is_symlink():
            raise RunnerError("SOURCE_PACKAGE_MISSING")
        digest = sha256_file(package)
        blob = git_blob_sha(self.repos["source"], self.manifest["source_package_path"])
        if digest != self.manifest["source_package_sha256"]:
            raise RunnerError("SOURCE_PACKAGE_SHA256_MISMATCH")
        if blob != self.manifest["source_package_git_blob_sha"]:
            raise RunnerError("SOURCE_PACKAGE_GIT_BLOB_SHA_MISMATCH")
        self.receipt["source_package"] = {
            "path": self.manifest["source_package_path"], "sha256": digest, "git_blob_sha": blob,
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

    def _run_named(self, name: str, *, receipt_key: str | None = None, log_name: str | None = None, **values: str) -> dict[str, Any]:
        command = self.manifest["commands"][name]
        log_relative = f"logs/{log_name or name}.log"
        raw = run_command(command, self.repos, self._command_values(**values), self.workspace / log_relative)
        normalized = {
            "repo": raw["repo"],
            "argv_template": list(command["argv"]),
            "exit_code": raw["exit_code"],
            "log_path": log_relative,
            "log_sha256": raw["log_sha256"],
        }
        self.receipt.setdefault("command_receipts", {})[receipt_key or name] = normalized
        return normalized

    def _validate_only(self) -> None:
        for name in ("source_materialize", "source_validate", "shared_id_validate", "schema_validate", "archive_prereq_validate"):
            self._run_named(name)
            for repo in set(self.repos.values()):
                assert_clean(repo)
        self._stage("validate_only")

    def _write_receipt(self, name: str) -> Path:
        payload = canonical_json_bytes(self.receipt)
        self.receipt["receipt_payload_sha256"] = sha256_bytes(payload)
        path = self.workspace / name
        data = canonical_json_bytes(self.receipt)
        scan_sensitive(name, data)
        path.write_bytes(data)
        return path

    def _finalize(self) -> Path:
        for repo in set(self.repos.values()):
            assert_clean(repo)
        self.receipt["result"] = "PASS"
        self.receipt["provenance"] = {
            "manifest_id": self.manifest["manifest_id"],
            "authorization_payload_sha256": self.manifest["authorization_payload_sha256"],
            "control_head": self.manifest["control_head"],
            "source_head": self.manifest["source_head"],
            "shared_source_head": self.manifest["shared_source_head"],
            "production_head": self.manifest["production_head"],
            "runner_head": self.manifest["runner_head"],
        }
        return self._write_receipt("release_receipt.json")

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
            self.receipt["authorization_payload_sha256"] = self.manifest["authorization_payload_sha256"]
            self.receipt["acceptance_state"] = self.manifest["acceptance_state"]
            self._checkout_repositories()
            self._verify_oc()
            if self.manifest.get("single_use_id"):
                if self.single_use_ledger is None:
                    raise RunnerError("SINGLE_USE_LEDGER_REQUIRED")
                consume_single_use(self.manifest["single_use_id"], self.single_use_ledger)
                self._stage("single_use_authorization_consumed")
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
            self.receipt["error_code"] = safe_error_code(exc)
            self._write_receipt("blocked_receipt.json")
            raise
