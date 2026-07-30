from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.gold_v2.common import RunnerError
from scripts.gold_v2.pipeline import GoldV2Pipeline
from helpers import base_manifest, rebind_oc, write_manifest


class PipelineTests(unittest.TestCase):
    def run_fixture(self, mode: str):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        manifest, _ = base_manifest(root, mode)
        manifest_path = root / "authorization.json"; write_manifest(manifest_path, manifest)
        workspace = root / "workspace"
        receipt_path = GoldV2Pipeline(manifest_path=manifest_path, mode=mode, workspace=workspace, execution_runner_head=manifest["runner_head"]).run()
        return json.loads(receipt_path.read_text()), workspace

    def test_validate_only_positive(self):
        receipt, workspace = self.run_fixture("validate-only")
        self.assertEqual("PASS", receipt["result"])
        self.assertFalse(receipt["still_render_started"])
        self.assertFalse(receipt["video_render_started"])
        self.assertTrue((workspace / "release_receipt.json").is_file())

    def test_compile_positive_two_identical_runs(self):
        receipt, workspace = self.run_fixture("compile")
        self.assertEqual("PASS", receipt["result"])
        self.assertEqual("PASS", receipt["compiler"]["security_receipt"]["result"])
        self.assertTrue((workspace / "artifacts/compiler-execution-evidence.zip").is_file())
        stages = {row["stage"]: row for row in receipt["stages"]}
        self.assertEqual("PASS", stages["compile"]["reproducibility"])

    def test_stale_control_head_blocks(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); manifest,repos=base_manifest(root)
        (repos["control"] / "new.txt").write_text("drift\n")
        subprocess.run(["git","add","."],cwd=repos["control"],check=True)
        subprocess.run(["git","commit","--quiet","-m","drift"],cwd=repos["control"],check=True)
        path=root/"authorization.json"; write_manifest(path,manifest)
        with self.assertRaisesRegex(RunnerError,"STALE_CONTROL_HEAD"):
            GoldV2Pipeline(manifest_path=path,mode="validate-only",workspace=root/"workspace",execution_runner_head=manifest["runner_head"]).run()

    def test_wrong_source_package_hash_blocks(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); manifest,repos=base_manifest(root)
        manifest["source_package_sha256"]="0"*64; rebind_oc(manifest, repos)
        path=root/"authorization.json"; write_manifest(path,manifest)
        with self.assertRaisesRegex(RunnerError,"SOURCE_PACKAGE_SHA256_MISMATCH"):
            GoldV2Pipeline(manifest_path=path,mode="validate-only",workspace=root/"workspace",execution_runner_head=manifest["runner_head"]).run()

    def test_wrong_compiler_artifact_blocks(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); manifest,repos=base_manifest(root,"compile")
        manifest["compiler_artifact_sha256"]="0"*64; rebind_oc(manifest, repos)
        path=root/"authorization.json"; write_manifest(path,manifest)
        with self.assertRaisesRegex(RunnerError,"COMPILER_ARTIFACT_SHA256_MISMATCH"):
            GoldV2Pipeline(manifest_path=path,mode="compile",workspace=root/"workspace",execution_runner_head=manifest["runner_head"]).run()

    def test_single_use_requires_ledger(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); manifest,repos=base_manifest(root)
        manifest.pop("expires_at_utc"); manifest["single_use_id"]="single-1"; rebind_oc(manifest, repos)
        path=root/"authorization.json"; write_manifest(path,manifest)
        with self.assertRaisesRegex(RunnerError,"SINGLE_USE_LEDGER_REQUIRED"):
            GoldV2Pipeline(manifest_path=path,mode="validate-only",workspace=root/"workspace",execution_runner_head=manifest["runner_head"]).run()

    def test_single_use_second_run_blocks(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root=Path(tmp.name); manifest,repos=base_manifest(root)
        manifest.pop("expires_at_utc"); manifest["single_use_id"]="single-2"; rebind_oc(manifest, repos)
        path=root/"authorization.json"; write_manifest(path,manifest); ledger=root/"ledger"
        GoldV2Pipeline(manifest_path=path,mode="validate-only",workspace=root/"run-1",single_use_ledger=ledger,execution_runner_head=manifest["runner_head"]).run()
        with self.assertRaisesRegex(RunnerError,"AUTHORIZATION_SINGLE_USE_ALREADY_CONSUMED"):
            GoldV2Pipeline(manifest_path=path,mode="validate-only",workspace=root/"run-2",single_use_ledger=ledger,execution_runner_head=manifest["runner_head"]).run()


if __name__ == "__main__": unittest.main()
