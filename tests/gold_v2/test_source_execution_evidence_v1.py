from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/gold_v2/source_execution_evidence_v1.py"
SPEC = importlib.util.spec_from_file_location("source_execution_evidence_v1", SCRIPT)
assert SPEC and SPEC.loader
worker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker
SPEC.loader.exec_module(worker)


class SourceExecutionEvidenceTests(unittest.TestCase):
    def test_frozen_exact_identities(self):
        self.assertEqual(worker.RUNNER_REPO, "TheGor-365/ai-course-actions-runner")
        self.assertEqual(worker.TARGET_BRANCH, "worker/gold-v2-source-execution-evidence-v1")
        self.assertEqual(worker.SOURCE_REPO, "TheGor-365/ai-course-source-library")
        self.assertEqual(worker.SOURCE_PR, 66)
        self.assertEqual(worker.SOURCE_HEAD, "ab38ac36a786cdb93fc15263fadf391ce62368d5")
        self.assertEqual(len(worker.POSITIVE), 6)
        self.assertEqual(len(worker.EXTRA), 4)

    def test_missing_private_token_is_exact_blocker(self):
        with self.assertRaises(worker.Gate) as caught:
            worker.token({})
        self.assertEqual(caught.exception.code, "MISSING_READ_ONLY_PRIVATE_REPO_TOKEN")

    def test_secret_name_priority_never_exposes_value(self):
        environment = {"SOURCE_REPO_READ_TOKEN": "alpha", "REPO_READ_TOKEN": "beta"}
        self.assertEqual(worker.token_names(environment), ["SOURCE_REPO_READ_TOKEN", "REPO_READ_TOKEN"])
        self.assertEqual(worker.token(environment), ("SOURCE_REPO_READ_TOKEN", "alpha"))

    def test_receipt_parser_uses_terminal_json(self):
        self.assertEqual(worker.parsed('diagnostic\n{"result":"PASS","count":12}\n'), {"result": "PASS", "count": 12})
        self.assertEqual(worker.parsed("no json"), {})

    def test_canonical_json_is_stable(self):
        first = worker.canon({"b": 2, "a": 1})
        second = worker.canon({"a": 1, "b": 2})
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())

    def test_deterministic_archive_bytes(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "b.json").write_text('{"b":2}\n', encoding="utf-8")
            (evidence / "a.json").write_text('{"a":1}\n', encoding="utf-8")
            first = root / "first.zip"
            second = root / "second.zip"
            self.assertEqual(worker.archive(evidence, first), worker.archive(evidence, second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as opened:
                self.assertEqual(opened.namelist(), ["a.json", "b.json"])
                self.assertTrue(all(row.date_time == (1980, 1, 1, 0, 0, 0) for row in opened.infolist()))

    def test_transport_credentials_are_scrubbed_before_validators(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('command_env.pop(name, None)', source)
        self.assertIn('"ACTIONS_READ_TOKEN"', source)
        self.assertNotIn("git push", source)
        self.assertNotIn("workflow_dispatch", source)
        self.assertNotIn("render", source.lower().replace("media_render_started", ""))

    def test_workflow_is_branch_limited_and_pinned(self):
        workflow = SCRIPT.parents[2] / ".github/workflows/gold-v2-source-execution-evidence-v1.yml"
        text = workflow.read_text(encoding="utf-8")
        self.assertIn("worker/gold-v2-source-execution-evidence-v1", text)
        self.assertIn("permissions:\n  contents: read\n  actions: read", text)
        self.assertNotIn("workflow_dispatch", text)
        self.assertNotIn("pull_request:", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683", text)
        self.assertIn("actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", text)
        self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02", text)
        self.assertIn("if-no-files-found: error", text)

    def test_base_receipt_semantics_are_fail_closed(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"independent_verifier_pass_claimed": False', source)
        self.assertIn('"source_writes": 0', source)
        self.assertIn('"production_writes": 0', source)
        self.assertIn('"no_fake_green": True', source)


if __name__ == "__main__":
    unittest.main()
