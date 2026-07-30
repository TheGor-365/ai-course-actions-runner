from __future__ import annotations

import json
import multiprocessing
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.gold_v2.authority import validate_manifest
from scripts.gold_v2.common import RunnerError, consume_single_use
from scripts.gold_v2.pipeline import GoldV2Pipeline
from helpers import base_manifest, rebind_oc, seal, write_manifest


def claim_worker(identity: str, ledger: str, queue) -> None:
    try:
        consume_single_use(identity, Path(ledger))
        queue.put("PASS")
    except RunnerError as exc:
        queue.put(str(exc).split(":", 1)[0])


class AuthorityHardeningTests(unittest.TestCase):
    def fixture(self, mode="validate-only"):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        manifest, _ = base_manifest(Path(tmp.name), mode)
        return manifest

    def test_unknown_command_rejected(self):
        manifest = self.fixture(); manifest["commands"]["branch_name_authorized"] = {"repo": "production", "argv": ["true"]}; seal(manifest)
        with self.assertRaisesRegex(RunnerError, "COMMAND_SET_INVALID"):
            validate_manifest(manifest, "validate-only")

    def test_missing_pre_render_exact_file_set_rejected(self):
        manifest = self.fixture("pre-render-evidence"); del manifest["expected_outputs"]["pre_render_files"]; seal(manifest)
        with self.assertRaisesRegex(RunnerError, "EXPECTED_OUTPUT_SET_KEYS_INVALID"):
            validate_manifest(manifest, "pre-render-evidence")

    def test_render_receipt_must_be_in_exact_file_set(self):
        manifest = self.fixture("render"); manifest["expected_outputs"]["render_files"] = ["video.mp4"]; seal(manifest)
        with self.assertRaisesRegex(RunnerError, "RENDER_RECEIPT_NOT_IN_EXPECTED_FILE_SET"):
            validate_manifest(manifest, "render")

    def test_production_class_cannot_be_nonaccepted(self):
        manifest = self.fixture("render"); manifest["acceptance_state"] = "NON_ACCEPTED_RECORDING_CANDIDATE"; seal(manifest)
        with self.assertRaisesRegex(RunnerError, "PRODUCTION_ACCEPTANCE_STATE_INVALID"):
            validate_manifest(manifest, "render")

    def test_evidence_cannot_be_accepted(self):
        manifest = self.fixture(); manifest["acceptance_state"] = "ACCEPTED"; seal(manifest)
        with self.assertRaisesRegex(RunnerError, "EVIDENCE_ACCEPTANCE_STATE_INVALID"):
            validate_manifest(manifest, "validate-only")

    def test_source_package_blob_shape_required(self):
        manifest = self.fixture(); manifest["source_package_git_blob_sha"] = "main"; seal(manifest)
        with self.assertRaisesRegex(RunnerError, "SOURCE_PACKAGE_GIT_BLOB_SHA_INVALID"):
            validate_manifest(manifest, "validate-only")


class PipelineHardeningTests(unittest.TestCase):
    def run_fixture(self, root: Path, mode: str, workspace_name: str):
        manifest, repos = base_manifest(root, mode)
        path = root / "authorization.json"; write_manifest(path, manifest)
        receipt_path = GoldV2Pipeline(
            manifest_path=path, mode=mode, workspace=root / workspace_name,
            execution_runner_head=manifest["runner_head"],
        ).run()
        return manifest, repos, receipt_path

    def test_compile_uses_two_independent_exact_checkouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, _, receipt_path = self.run_fixture(root, "compile", "workspace")
            receipt = json.loads(receipt_path.read_text())
            self.assertIn("compiler_run_1", receipt["exact_head_leases"])
            self.assertIn("compiler_run_2", receipt["exact_head_leases"])
            self.assertTrue(receipt["stages"][-1]["independent_exact_checkouts"])
            self.assertIn("compiler_run_1", receipt["command_receipts"])
            self.assertIn("compiler_run_2", receipt["command_receipts"])

    def test_release_receipt_uses_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); _, _, receipt_path = self.run_fixture(root, "validate-only", "workspace")
            receipt = json.loads(receipt_path.read_text())
            for command in receipt["command_receipts"].values():
                self.assertTrue(command["log_path"].startswith("logs/"))
                self.assertNotIn(str(root), json.dumps(command))

    def test_transport_credentials_scrubbed_before_provider_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, repos = base_manifest(root)
            check = "import os,sys; sys.exit(1 if 'REPO_READ_TOKEN' in os.environ or 'GIT_CONFIG_COUNT' in os.environ else 0)"
            manifest["commands"]["source_validate"] = {"repo": "production", "argv": ["python3", "-c", check]}
            rebind_oc(manifest, repos)
            path = root / "authorization.json"; write_manifest(path, manifest)
            old_token, old_count = os.environ.get("REPO_READ_TOKEN"), os.environ.get("GIT_CONFIG_COUNT")
            os.environ["REPO_READ_TOKEN"] = "github_pat_fixture"
            os.environ["GIT_CONFIG_COUNT"] = "0"
            try:
                receipt = GoldV2Pipeline(manifest_path=path, mode="validate-only", workspace=root/"workspace", execution_runner_head=manifest["runner_head"]).run()
                self.assertTrue(receipt.is_file())
            finally:
                if old_token is not None: os.environ["REPO_READ_TOKEN"] = old_token
                else: os.environ.pop("REPO_READ_TOKEN", None)
                if old_count is not None: os.environ["GIT_CONFIG_COUNT"] = old_count
                else: os.environ.pop("GIT_CONFIG_COUNT", None)

    def test_wrong_source_blob_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, repos = base_manifest(root)
            manifest["source_package_git_blob_sha"] = "0"*40; rebind_oc(manifest, repos)
            path = root/"authorization.json"; write_manifest(path, manifest)
            with self.assertRaisesRegex(RunnerError, "SOURCE_PACKAGE_GIT_BLOB_SHA_MISMATCH"):
                GoldV2Pipeline(manifest_path=path, mode="validate-only", workspace=root/"workspace", execution_runner_head=manifest["runner_head"]).run()
            blocked = json.loads((root/"workspace/blocked_receipt.json").read_text())
            self.assertEqual("SOURCE_PACKAGE_GIT_BLOB_SHA_MISMATCH", blocked["error_code"])
            self.assertNotIn(str(root), json.dumps(blocked))

    def test_invalid_oc_does_not_consume_single_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); manifest, repos = base_manifest(root)
            manifest.pop("expires_at_utc"); manifest["single_use_id"] = "once"; rebind_oc(manifest, repos)
            (repos["control"] / "drift").write_text("x")
            subprocess.run(["git", "add", "."], cwd=repos["control"], check=True)
            subprocess.run(["git", "commit", "--quiet", "-m", "drift"], cwd=repos["control"], check=True)
            path=root/"authorization.json"; write_manifest(path, manifest); ledger=root/"ledger"
            with self.assertRaisesRegex(RunnerError, "STALE_CONTROL_HEAD"):
                GoldV2Pipeline(manifest_path=path, mode="validate-only", workspace=root/"workspace", single_use_ledger=ledger, execution_runner_head=manifest["runner_head"]).run()
            self.assertFalse(ledger.exists())

    def test_single_use_claim_is_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = str(Path(tmp)/"ledger")
            queue = multiprocessing.Queue()
            procs = [multiprocessing.Process(target=claim_worker, args=("one", ledger, queue)) for _ in range(2)]
            for process in procs: process.start()
            for process in procs: process.join(10)
            results = sorted(queue.get(timeout=2) for _ in range(2))
            self.assertEqual(["AUTHORIZATION_SINGLE_USE_ALREADY_CONSUMED", "PASS"], results)


class WorkflowHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[2]
        cls.text = (cls.root/".github/workflows/gold-v2-diamond-15min.yml").read_text()

    def test_actions_are_pinned_to_exact_commits(self):
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", self.text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", self.text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", self.text)
        self.assertNotIn("actions/checkout@v", self.text)
        self.assertNotIn("actions/setup-python@v", self.text)
        self.assertNotIn("actions/upload-artifact@v", self.text)

    def test_workflow_requires_exact_self_ref(self):
        self.assertIn("github.workflow_ref", self.text)
        self.assertIn('reusable workflow must be invoked at the same exact runner SHA', self.text)

    def test_inputs_and_workspace_are_outside_checkout(self):
        self.assertIn('$RUNNER_TEMP/gold-v2-input/authorization.json', self.text)
        self.assertIn('$RUNNER_TEMP/gold-v2-run', self.text)
        self.assertNotIn('.gold-v2-input', self.text)
        self.assertNotIn('.gold-v2-run', self.text)

    def test_workflow_remains_call_only(self):
        self.assertIn("workflow_call:", self.text)
        for forbidden in ("workflow_dispatch:", "pull_request:", "schedule:", "github.ref", "github.head_ref"):
            self.assertNotIn(forbidden, self.text)


if __name__ == "__main__": unittest.main()
