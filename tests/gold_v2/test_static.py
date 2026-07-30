from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.gold_v2.artifacts import build_human_review_queue

ROOT = Path(__file__).resolve().parents[2]


class StaticContractTests(unittest.TestCase):
    def test_workflow_is_call_only(self):
        text=(ROOT/".github/workflows/gold-v2-diamond-15min.yml").read_text()
        self.assertIn("workflow_call:",text)
        for forbidden in ("workflow_dispatch:","pull_request:","schedule:","github.ref","github.head_ref"):
            self.assertNotIn(forbidden,text)

    def test_workflow_invokes_one_entrypoint(self):
        text=(ROOT/".github/workflows/gold-v2-diamond-15min.yml").read_text()
        self.assertEqual(1,text.count("python3 scripts/gold_v2/runner.py"))
        self.assertIn("permissions:\n  contents: read",text)

    def test_workflow_actions_are_exact_sha_pinned(self):
        text=(ROOT/".github/workflows/gold-v2-diamond-15min.yml").read_text()
        refs=re.findall(r"uses:\s+([^\s#]+)", text)
        self.assertEqual(3, len(refs))
        for ref in refs:
            self.assertRegex(ref, r"^[^@]+@[0-9a-f]{40}$")

    def test_workflow_exact_self_ref_and_external_workspace(self):
        text=(ROOT/".github/workflows/gold-v2-diamond-15min.yml").read_text()
        self.assertIn("job.workflow_sha", text)
        self.assertIn("$RUNNER_TEMP/gold-v2-input", text)
        self.assertIn("$RUNNER_TEMP/gold-v2-run", text)

    def test_negative_fixture_catalog_complete(self):
        data=json.loads((ROOT/"tests/gold_v2/fixtures/negative_fixture_catalog.v1.json").read_text())
        required={
            "unauthorized_compile","unauthorized_evidence","unauthorized_render","stale_control_head",
            "wrong_source_head","wrong_compiler_artifact","missing_runtime_head","missing_sha256sums",
            "extra_archive_file","traversal","symlink","secret","private_payload","provisional_head",
            "preview_mislabeled_as_production","branch_name_authority_inference","mutable_action_ref",
            "single_use_race","missing_pre_render_exact_file_set","production_nonaccepted_state",
        }
        self.assertEqual(required,{item["id"] for item in data["cases"]})

    def test_human_review_never_auto_passes(self):
        queue=build_human_review_queue([{"gate_id":"g","frame":1,"scene_event":"s:e","expected":"x","observed":"y","reviewer_action":"review"}])
        self.assertFalse(queue["automatic_aesthetic_pass"])
        self.assertEqual("REVIEW_REQUIRED",queue["items"][0]["status"])

    def test_preview_label_literal_documented(self):
        text=(ROOT/"scripts/gold_v2/README.md").read_text()
        self.assertIn("NON_ACCEPTED_RECORDING_CANDIDATE",text)
        self.assertIn("execution/evidence layer",text)


if __name__ == "__main__": unittest.main()
