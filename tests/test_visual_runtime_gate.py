from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from visual_runtime_gate_v1 import (  # noqa: E402
    EXPECTED_COMBINED_TEST_COUNT,
    EXPECTED_DAY5_AUDIT_HASH,
    EXPECTED_HANDOFF_V3_HASH,
    EXPECTED_SOURCE_SNAPSHOT_BRANCH,
    EXPECTED_SOURCE_SNAPSHOT_SHA,
    GateError,
    parse_last_json,
    validate_bridge_summary,
    validate_evidence,
    validate_main_summary,
    validate_timing_summary,
)


def good_main() -> dict:
    return {
        "status": "PASS_CONTENT_SNAPSHOT_V9_NO_RENDER",
        "test_count": EXPECTED_COMBINED_TEST_COUNT,
        "shot_count": 26,
        "scene_count": 13,
        "actual_content_semantics_source_inputs_connected": True,
        "actual_content_semantics_source_head_binding": "IMMUTABLE_SNAPSHOT",
        "actual_content_semantics_source_snapshot_branch": EXPECTED_SOURCE_SNAPSHOT_BRANCH,
        "actual_content_semantics_source_snapshot_sha": EXPECTED_SOURCE_SNAPSHOT_SHA,
        "actual_content_semantics_handoff_v3_content_hash": EXPECTED_HANDOFF_V3_HASH,
        "day5_closure_audit_content_hash": EXPECTED_DAY5_AUDIT_HASH,
        "source_snapshot_exact_gate_green": False,
        "source_clean_execution_green": False,
        "private_review_pack_executed": False,
        "private_executor_connected": False,
        "render_executed": False,
        "render_green_claimed": False,
        "no_fake_green": True,
        "deterministic_compile_sha256": "a" * 64,
    }


def good_timing() -> dict:
    return {
        "status": "PASS_TIMING_ADAPTER_NO_RENDER",
        "test_count": 9,
        "expected_shot_bindings": 26,
        "expected_scene_bindings": 13,
        "candidate_and_accepted_statuses_supported": True,
        "fail_closed_gap_overlap_coverage_duration_source": True,
        "render_executed": False,
        "render_green_claimed": False,
        "no_fake_green": True,
    }


def good_bridge() -> dict:
    return {
        "status": "PASS_PRODUCTION_BRIDGE_NO_NEW_RENDER",
        "test_count": 7,
        "composition_id": "M1-L01-S01-0000-1500-v2",
        "sceneir_scene_count": 13,
        "sceneir_shot_count": 26,
        "production_scene_count": 26,
        "duration_ms": 908398,
        "total_frames": 27252,
        "rerender_required": False,
        "existing_still_artifact_count": 17,
        "existing_still_machine_qc_green": True,
        "existing_still_human_qc_green": False,
        "render_executed_by_validator": False,
        "render_green_claimed": False,
        "no_fake_green": True,
        "bridge_sha256": "b" * 64,
    }


def good_evidence() -> dict:
    return {
        "status": "YELLOW_IMMUTABLE_SNAPSHOT_V9_CONNECTED_PUBLIC_RUNNER_PENDING",
        "source_authority": {
            "repository": "TheGor-365/ai-course-source-library",
            "pull_request": 55,
            "immutable_snapshot_branch": EXPECTED_SOURCE_SNAPSHOT_BRANCH,
            "immutable_snapshot_sha": EXPECTED_SOURCE_SNAPSHOT_SHA,
            "rolling_head_snapshot_compare": "IDENTICAL",
            "handoff_v3_content_hash": EXPECTED_HANDOFF_V3_HASH,
            "day5_closure_audit_content_hash": EXPECTED_DAY5_AUDIT_HASH,
            "semantic_units": 13,
            "shotir_source_inputs": 26,
            "source_snapshot_exact_gate_green": False,
            "source_validator_green": False,
        },
        "adapter_result": {
            "source_head_binding": "IMMUTABLE_SNAPSHOT",
            "semantic_unit_count": 13,
            "resolved_shot_count": 26,
            "visible_source_ids": 0,
            "manual_timing_fabricated": False,
            "render_executed": False,
        },
        "validation": {
            "combined_expected_test_count": EXPECTED_COMBINED_TEST_COUNT,
            "private_actions_job_steps": 0,
            "clean_checkout_green": False,
            "github_actions_green": False,
        },
        "non_claims": {
            "source_pull_request_accepted": False,
            "source_clean_execution_green": False,
            "human_visual_qc_green": False,
            "render_green": False,
            "production_green": False,
            "release_green": False,
        },
        "no_fake_green": True,
    }


class VisualRuntimeGateTests(unittest.TestCase):
    def test_good_summaries_and_evidence_pass(self) -> None:
        validate_evidence(good_evidence())
        validate_main_summary(good_main())
        validate_timing_summary(good_timing())
        validate_bridge_summary(good_bridge())

    def test_wrong_combined_test_count_fails(self) -> None:
        value = good_main()
        value["test_count"] = EXPECTED_COMBINED_TEST_COUNT - 1
        with self.assertRaises(GateError) as raised:
            validate_main_summary(value)
        self.assertEqual("main_summary_mismatch", raised.exception.code)

    def test_source_snapshot_sha_drift_fails(self) -> None:
        value = good_evidence()
        value["source_authority"]["immutable_snapshot_sha"] = "0" * 40
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("source_snapshot_sha_mismatch", raised.exception.code)

    def test_render_claim_fails(self) -> None:
        value = good_main()
        value["render_executed"] = True
        with self.assertRaises(GateError) as raised:
            validate_main_summary(value)
        self.assertEqual("main_summary_mismatch", raised.exception.code)

    def test_human_qc_claim_fails(self) -> None:
        value = good_bridge()
        value["existing_still_human_qc_green"] = True
        with self.assertRaises(GateError) as raised:
            validate_bridge_summary(value)
        self.assertEqual("bridge_summary_mismatch", raised.exception.code)

    def test_parse_last_json_uses_final_object(self) -> None:
        payload = good_timing()
        text = "diagnostic line\n" + json.dumps({"ignored": True}) + "\n" + json.dumps(payload)
        self.assertEqual(payload, parse_last_json(text))

    def test_parse_last_json_rejects_missing_summary(self) -> None:
        with self.assertRaises(GateError) as raised:
            parse_last_json("no json here")
        self.assertEqual("validator_summary_missing", raised.exception.code)

    def test_evidence_green_promotion_fails(self) -> None:
        value = copy.deepcopy(good_evidence())
        value["non_claims"]["production_green"] = True
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("non_claim_production_green_mismatch", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
