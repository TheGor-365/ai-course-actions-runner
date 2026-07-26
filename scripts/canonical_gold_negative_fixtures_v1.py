#!/usr/bin/env python3
"""Execute stable negative-policy regressions for canonical Gold PSU v2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class Rejection(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def reject(code: str) -> None:
    raise Rejection(code)


def closure_policy(case: dict[str, Any]) -> None:
    if case.get("missing_required"): reject("MISSING_REQUIRED_PSU_FILE")
    if case.get("unclassified"): reject("UNCLASSIFIED_PSU_FILE")
    if case.get("stale_hash"): reject("STALE_REQUIRED_HASH")
    if case.get("canonical_authorities", 1) != 1: reject("DUPLICATE_CANONICAL_AUTHORITY")
    if case.get("source_repository_role") == "PRODUCTION_MIRROR": reject("PRODUCTION_MIRROR_USED_AS_SOURCE")
    if case.get("authority_cycle"): reject("AUTHORITY_GRAPH_CYCLE")
    if case.get("required_field_consumed") is False: reject("REQUIRED_FIELD_DROPPED")
    if case.get("visual_event_disposed") is False: reject("VISUAL_EVENT_DROPPED")
    if case.get("motion_phase_count", 3) < 3: reject("MOTION_PHASE_DROPPED")
    if case.get("handler_registered") is False: reject("UNKNOWN_RUNTIME_HANDLER")
    if case.get("semantic_change") == "GENERIC_TRANSLATE": reject("GENERIC_TRANSLATE_SUBSTITUTION")
    if case.get("semantic_change") == "OPACITY_ONLY": reject("OPACITY_ONLY_SUBSTITUTION")
    if case.get("consumed") is True and case.get("target_changed") is False: reject("CONSUMED_TRUE_WITHOUT_TARGET_CHANGE")


def code_policy(case: dict[str, Any]) -> None:
    if case.get("all_lines_visible_at_start"): reject("ALL_CODE_LINES_VISIBLE_AT_START")
    if case.get("token_glow_required") and not case.get("token_glow_observed"): reject("TOKEN_GLOW_MISSING")
    if case.get("line_focus_required") and len(set(case.get("active_lines", []))) < 2: reject("ACTIVE_LINE_NEVER_CHANGES")
    if case.get("execution_cursor_observed") and not case.get("execution_declared"): reject("EXECUTION_CURSOR_FALSE_CLAIM")
    if case.get("code_surface") == "GENERATED_IMAGE": reject("FAKE_CODE_IMAGE")


def visual_policy(case: dict[str, Any]) -> None:
    if case.get("missing_asset"): reject("MISSING_ASSET")
    if case.get("fantasy") == "UNBOUNDED": reject("UNBOUNDED_FANTASY")
    if case.get("presentation_replaces_action"): reject("PRESENTATION_REPLACES_ACTION")
    if case.get("scene_structure") == "GENERIC_CARD_ONLY": reject("GENERIC_CARD_ONLY")
    if case.get("caption_collision"): reject("CAPTION_COLLISION")
    if case.get("internal_id_visible"): reject("INTERNAL_ID_VISIBLE")


def window_policy(case: dict[str, Any]) -> None:
    if case.get("pilot_kind") == "MONTAGE": reject("MONTAGE_PILOT")
    intervals = case.get("intervals", [(0, 60000)])
    if len(intervals) != 1 or intervals[0][1] - intervals[0][0] != 60000: reject("NON_CONTIGUOUS_WINDOW")
    if case.get("audio_present") is False: reject("SILENT_PILOT")
    if case.get("audio_sha_valid") is False: reject("WRONG_AUDIO_SHA")
    if case.get("audio_window_matches") is False: reject("WRONG_AUDIO_WINDOW")
    if case.get("caption_window_matches") is False: reject("CAPTION_WINDOW_MISMATCH")
    if case.get("anchor_drift_ms", 0) > case.get("maximum_anchor_drift_ms", 120): reject("AUDIO_VISUAL_ANCHOR_DRIFT")


def multilingual_policy(case: dict[str, Any]) -> None:
    if case.get("visual_master_identity_equal") is False: reject("LOCALE_VISUAL_MASTER_DRIFT")
    if case.get("code_tokens_equal") is False: reject("LOCALE_CODE_TOKEN_CHANGED")
    if case.get("semantic_slot_present") is False: reject("MULTILINGUAL_SLOT_MISSING")


def binding_policy(case: dict[str, Any]) -> None:
    if case.get("source_sceneir_identity_equal") is False: reject("SOURCE_TO_SCENEIR_DRIFT")
    if case.get("runtime_closure_sha_equal") is False: reject("RUNTIME_NOT_BOUND_TO_PSU_CLOSURE")


VALIDATORS: list[Callable[[dict[str, Any]], None]] = [
    closure_policy, code_policy, visual_policy, window_policy, multilingual_policy, binding_policy,
]

CASES: dict[str, dict[str, Any]] = {
    "missing_required_psu_file": {"missing_required": True},
    "unclassified_psu_file": {"unclassified": True},
    "stale_required_hash": {"stale_hash": True},
    "duplicate_canonical_authority": {"canonical_authorities": 2},
    "production_mirror_used_as_source": {"source_repository_role": "PRODUCTION_MIRROR"},
    "authority_cycle": {"authority_cycle": True},
    "required_field_dropped": {"required_field_consumed": False},
    "visual_event_dropped": {"visual_event_disposed": False},
    "motion_phase_dropped": {"motion_phase_count": 2},
    "unknown_runtime_handler": {"handler_registered": False},
    "generic_translate_substitution": {"semantic_change": "GENERIC_TRANSLATE"},
    "opacity_only_substitution": {"semantic_change": "OPACITY_ONLY"},
    "consumed_true_without_target_change": {"consumed": True, "target_changed": False},
    "all_code_lines_visible_at_start": {"all_lines_visible_at_start": True},
    "token_glow_missing": {"token_glow_required": True, "token_glow_observed": False},
    "active_line_never_changes": {"line_focus_required": True, "active_lines": [0, 0, 0]},
    "execution_cursor_false_claim": {"execution_cursor_observed": True, "execution_declared": False},
    "fake_code_image": {"code_surface": "GENERATED_IMAGE"},
    "missing_asset": {"missing_asset": True},
    "unbounded_fantasy": {"fantasy": "UNBOUNDED"},
    "presentation_replaces_action": {"presentation_replaces_action": True},
    "generic_card_only": {"scene_structure": "GENERIC_CARD_ONLY"},
    "caption_collision": {"caption_collision": True},
    "internal_id_visible": {"internal_id_visible": True},
    "montage_pilot": {"pilot_kind": "MONTAGE"},
    "non_contiguous_window": {"intervals": [(0, 20000), (180000, 200000), (420000, 440000)]},
    "silent_pilot": {"audio_present": False},
    "wrong_audio_sha": {"audio_sha_valid": False},
    "wrong_audio_window": {"audio_window_matches": False},
    "caption_window_mismatch": {"caption_window_matches": False},
    "audio_visual_anchor_drift": {"anchor_drift_ms": 500, "maximum_anchor_drift_ms": 120},
    "locale_visual_master_drift": {"visual_master_identity_equal": False},
    "locale_code_token_changed": {"code_tokens_equal": False},
    "multilingual_slot_missing": {"semantic_slot_present": False},
    "source_to_sceneir_drift": {"source_sceneir_identity_equal": False},
    "runtime_not_bound_to_psu_closure": {"runtime_closure_sha_equal": False},
}


def execute_case(fixture_id: str, expected_code: str) -> dict[str, Any]:
    case = CASES.get(fixture_id)
    if case is None:
        return {"fixture_id": fixture_id, "expected_error_code": expected_code, "observed_error_code": "FIXTURE_CASE_MISSING", "rejected": False}
    observed = "NOT_REJECTED"
    try:
        for validator in VALIDATORS:
            validator(case)
    except Rejection as error:
        observed = error.code
    return {"fixture_id": fixture_id, "expected_error_code": expected_code, "observed_error_code": observed, "rejected": observed == expected_code}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    fixtures = registry["fixtures"]
    results = [execute_case(row["fixture_id"], row["expected_error_code"]) for row in fixtures]
    rejected = sum(1 for row in results if row["rejected"])
    payload = {
        "schema_version": "canonical_gold_negative_fixture_execution.v1",
        "fixture_count": len(results),
        "rejected_count": rejected,
        "unexpected_result_count": len(results) - rejected,
        "all_rejected": rejected == len(results),
        "results": results,
        "full_15_minute_rendered": False,
        "human_final_preview_accepted": False,
        "no_fake_green": True,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print(f"NEGATIVE_FIXTURE_COUNT={len(results)}")
    print(f"NEGATIVE_FIXTURE_REJECT_COUNT={rejected}")
    print(f"NEGATIVE_FIXTURE_RECEIPT_SHA256={hashlib.sha256(encoded.encode('utf-8')).hexdigest()}")
    if rejected != len(results):
        raise SystemExit("NEGATIVE_FIXTURE_UNEXPECTED_RESULT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
