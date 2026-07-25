from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from visual_runtime_gate_v2 import (  # noqa: E402
    EXPECTED_SOURCE_SHA,
    EXPECTED_TEST_COUNT,
    GateError,
    parse_last_json,
    validate_evidence,
    validate_summaries,
)


def evidence() -> dict:
    return {
        "status": "YELLOW_IMMUTABLE_SNAPSHOT_V9_CONNECTED_OWNER_PACK_BUILDER_READY_PRIVATE_EXECUTION_BLOCKED",
        "source_authority": {
            "immutable_snapshot_sha": EXPECTED_SOURCE_SHA,
            "semantic_units": 13,
            "shotir_source_inputs": 26,
            "source_snapshot_exact_gate_green": False,
            "source_validator_green": False,
            "external_exact_gate_evidence": {
                "run_id": 30160089285,
                "result": "PASS",
                "exact_source_sha": EXPECTED_SOURCE_SHA,
            },
        },
        "adapter_result": {
            "source_head_binding": "IMMUTABLE_SNAPSHOT",
            "semantic_unit_count": 13,
            "resolved_shot_count": 26,
            "visible_source_ids": 0,
            "manual_timing_fabricated": False,
            "render_executed": False,
        },
        "owner_review_pack_builder": {
            "tests_authored": 4,
            "expected_still_count": 17,
            "contact_sheet": True,
            "full_resolution_archive": True,
            "sanitized_manifest": True,
            "sha256_ledger": True,
            "opaque_delivery_pointer_required": True,
            "rerender_performed": False,
            "private_artifact_bytes_available_to_current_executor": False,
            "owner_delivery_channel_available": False,
            "execution_complete": False,
            "human_decision": None,
            "human_visual_qc_green": False,
        },
        "validation": {
            "combined_expected_test_count": EXPECTED_TEST_COUNT,
            "owner_review_pack_tests_authored": 4,
            "private_actions_job_steps": 0,
            "clean_checkout_green": False,
            "github_actions_green": False,
        },
        "non_claims": {
            "source_pull_request_accepted": False,
            "source_clean_execution_green": False,
            "private_review_pack_executed": False,
            "human_visual_qc_green": False,
            "accepted_timing_available": False,
            "cross_scene_clip_created": False,
            "ru_preview_created": False,
            "render_green": False,
            "production_green": False,
            "release_green": False,
        },
        "no_fake_green": True,
    }


def summaries() -> tuple[dict, dict, dict]:
    main = {
        "status": "PASS_CONTENT_SNAPSHOT_V9_NO_RENDER",
        "test_count": EXPECTED_TEST_COUNT,
        "shot_count": 26,
        "scene_count": 13,
        "actual_content_semantics_source_head_binding": "IMMUTABLE_SNAPSHOT",
        "private_review_pack_executed": False,
        "render_executed": False,
        "render_green_claimed": False,
        "no_fake_green": True,
        "deterministic_compile_sha256": "a" * 64,
    }
    timing = {"status": "PASS_TIMING_ADAPTER_NO_RENDER", "test_count": 9, "render_executed": False}
    bridge = {
        "status": "PASS_PRODUCTION_BRIDGE_NO_NEW_RENDER",
        "test_count": 7,
        "existing_still_artifact_count": 17,
        "existing_still_machine_qc_green": True,
        "existing_still_human_qc_green": False,
        "rerender_required": False,
        "bridge_sha256": "b" * 64,
    }
    return main, timing, bridge


class VisualRuntimeGateV2Tests(unittest.TestCase):
    def test_good_evidence_and_summaries_pass(self) -> None:
        validate_evidence(evidence())
        validate_summaries(*summaries())

    def test_wrong_private_test_count_fails(self) -> None:
        value = evidence()
        value["validation"]["combined_expected_test_count"] -= 1
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("expected_test_count_mismatch", raised.exception.code)

    def test_owner_builder_execution_claim_fails(self) -> None:
        value = evidence()
        value["owner_review_pack_builder"]["execution_complete"] = True
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("owner_builder_false_boundary_mismatch", raised.exception.code)

    def test_human_green_claim_fails(self) -> None:
        value = evidence()
        value["non_claims"]["human_visual_qc_green"] = True
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("non_claim_human_visual_qc_green_mismatch", raised.exception.code)

    def test_accepted_timing_claim_fails(self) -> None:
        value = evidence()
        value["non_claims"]["accepted_timing_available"] = True
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("non_claim_accepted_timing_available_mismatch", raised.exception.code)

    def test_rerender_claim_fails(self) -> None:
        value = evidence()
        value["owner_review_pack_builder"]["rerender_performed"] = True
        with self.assertRaises(GateError) as raised:
            validate_evidence(value)
        self.assertEqual("owner_builder_false_boundary_mismatch", raised.exception.code)

    def test_summary_count_drift_fails(self) -> None:
        main, timing, bridge = summaries()
        main["test_count"] -= 1
        with self.assertRaises(GateError) as raised:
            validate_summaries(main, timing, bridge)
        self.assertEqual("main_summary_mismatch", raised.exception.code)

    def test_parse_last_json_uses_last_object(self) -> None:
        expected = {"result": "PASS"}
        text = json.dumps({"ignored": True}) + "\n" + json.dumps(expected)
        self.assertEqual(expected, parse_last_json(text))


if __name__ == "__main__":
    unittest.main()
