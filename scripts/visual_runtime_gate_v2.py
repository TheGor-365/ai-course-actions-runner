#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

EXPECTED_PRIVATE_REPO = "TheGor-365/ai-course-production-system"
EXPECTED_PRIVATE_BRANCH = "launch/factory-5d-visual-runtime"
EXPECTED_PRIVATE_SHA = "fea41b12ea731393dce13799a315262ba91aa7dc"
EXPECTED_SOURCE_SHA = "f2a6ed754a8a18b0b9e17bfa6f65b32007f50232"
EXPECTED_TEST_COUNT = 55
EVIDENCE = Path(
    "03_modules/M1/L01/04_render_migration/launch_5d/visual_runtime_v1/"
    "actual_content_semantics_snapshot_v9_evidence_s01_v2.json"
)
MAIN_VALIDATOR = Path("04_validators/render/validate_visual_runtime_v1.py")
TIMING_VALIDATOR = Path("04_validators/render/validate_visual_runtime_timing_adapter_v1.py")
BRIDGE_VALIDATOR = Path("04_validators/render/validate_visual_runtime_production_bridge_v1.py")


class GateError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("json_unreadable", f"{path.as_posix()}:{type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise GateError("json_root_not_object", path.as_posix())
    return value


def parse_last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise GateError("validator_summary_missing", sha256_bytes(text.encode("utf-8")))


def require(record: Mapping[str, Any], key: str, expected: Any, code: str) -> None:
    observed = record.get(key)
    if observed != expected:
        raise GateError(code, f"{key}:{observed!r}!={expected!r}")


def validate_evidence(value: Mapping[str, Any]) -> None:
    require(
        value,
        "status",
        "YELLOW_IMMUTABLE_SNAPSHOT_V9_CONNECTED_OWNER_PACK_BUILDER_READY_PRIVATE_EXECUTION_BLOCKED",
        "evidence_status_mismatch",
    )
    source = value.get("source_authority")
    adapter = value.get("adapter_result")
    builder = value.get("owner_review_pack_builder")
    validation = value.get("validation")
    non_claims = value.get("non_claims")
    if not all(isinstance(item, dict) for item in (source, adapter, builder, validation, non_claims)):
        raise GateError("evidence_sections_missing", "source/adapter/builder/validation/non_claims")

    require(source, "immutable_snapshot_sha", EXPECTED_SOURCE_SHA, "source_sha_mismatch")
    require(source, "semantic_units", 13, "semantic_units_mismatch")
    require(source, "shotir_source_inputs", 26, "source_inputs_mismatch")
    require(source, "source_snapshot_exact_gate_green", False, "adapter_source_gate_flag_mismatch")
    require(source, "source_validator_green", False, "adapter_source_validator_flag_mismatch")
    external = source.get("external_exact_gate_evidence")
    if not isinstance(external, dict):
        raise GateError("external_source_gate_missing", "external_exact_gate_evidence")
    require(external, "run_id", 30160089285, "external_source_run_mismatch")
    require(external, "result", "PASS", "external_source_result_mismatch")
    require(external, "exact_source_sha", EXPECTED_SOURCE_SHA, "external_source_sha_mismatch")

    require(adapter, "source_head_binding", "IMMUTABLE_SNAPSHOT", "adapter_binding_mismatch")
    require(adapter, "semantic_unit_count", 13, "adapter_units_mismatch")
    require(adapter, "resolved_shot_count", 26, "adapter_shots_mismatch")
    require(adapter, "visible_source_ids", 0, "visible_ids_mismatch")
    require(adapter, "manual_timing_fabricated", False, "manual_timing_claim")
    require(adapter, "render_executed", False, "render_claim")

    require(builder, "tests_authored", 4, "owner_builder_test_count_mismatch")
    require(builder, "expected_still_count", 17, "owner_builder_still_count_mismatch")
    for key in ("contact_sheet", "full_resolution_archive", "sanitized_manifest", "sha256_ledger", "opaque_delivery_pointer_required"):
        require(builder, key, True, "owner_builder_capability_mismatch")
    for key in ("rerender_performed", "private_artifact_bytes_available_to_current_executor", "owner_delivery_channel_available", "execution_complete", "human_visual_qc_green"):
        require(builder, key, False, "owner_builder_false_boundary_mismatch")
    require(builder, "human_decision", None, "human_decision_must_be_unset")

    require(validation, "combined_expected_test_count", EXPECTED_TEST_COUNT, "expected_test_count_mismatch")
    require(validation, "owner_review_pack_tests_authored", 4, "owner_test_count_mismatch")
    require(validation, "private_actions_job_steps", 0, "private_actions_steps_mismatch")
    require(validation, "clean_checkout_green", False, "premature_clean_green")
    require(validation, "github_actions_green", False, "premature_actions_green")

    for key in (
        "source_pull_request_accepted",
        "source_clean_execution_green",
        "private_review_pack_executed",
        "human_visual_qc_green",
        "accepted_timing_available",
        "cross_scene_clip_created",
        "ru_preview_created",
        "render_green",
        "production_green",
        "release_green",
    ):
        require(non_claims, key, False, f"non_claim_{key}_mismatch")
    require(value, "no_fake_green", True, "no_fake_green_missing")


def run_validator(private_dir: Path, relative: Path) -> tuple[dict[str, Any], str, str]:
    target = private_dir / relative
    if not target.is_file():
        raise GateError("validator_missing", relative.as_posix())
    completed = subprocess.run(
        [sys.executable, relative.as_posix()],
        cwd=private_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    out_hash = sha256_bytes(completed.stdout.encode("utf-8"))
    err_hash = sha256_bytes(completed.stderr.encode("utf-8"))
    if completed.returncode != 0:
        raise GateError("validator_failed", f"{relative.name}:rc={completed.returncode}:out={out_hash}:err={err_hash}")
    return parse_last_json(completed.stdout), out_hash, err_hash


def validate_summaries(main: Mapping[str, Any], timing: Mapping[str, Any], bridge: Mapping[str, Any]) -> None:
    expected_main = {
        "status": "PASS_CONTENT_SNAPSHOT_V9_NO_RENDER",
        "test_count": EXPECTED_TEST_COUNT,
        "shot_count": 26,
        "scene_count": 13,
        "actual_content_semantics_source_head_binding": "IMMUTABLE_SNAPSHOT",
        "private_review_pack_executed": False,
        "render_executed": False,
        "render_green_claimed": False,
        "no_fake_green": True,
    }
    for key, expected in expected_main.items():
        require(main, key, expected, "main_summary_mismatch")
    require(timing, "status", "PASS_TIMING_ADAPTER_NO_RENDER", "timing_status_mismatch")
    require(timing, "test_count", 9, "timing_test_count_mismatch")
    require(timing, "render_executed", False, "timing_render_claim")
    require(bridge, "status", "PASS_PRODUCTION_BRIDGE_NO_NEW_RENDER", "bridge_status_mismatch")
    require(bridge, "test_count", 7, "bridge_test_count_mismatch")
    require(bridge, "existing_still_artifact_count", 17, "bridge_still_count_mismatch")
    require(bridge, "existing_still_machine_qc_green", True, "bridge_machine_qc_mismatch")
    require(bridge, "existing_still_human_qc_green", False, "bridge_human_qc_mismatch")
    require(bridge, "rerender_required", False, "bridge_rerender_mismatch")


def observed_head(private_dir: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(private_dir), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise GateError("git_head_unreadable", sha256_bytes(result.stderr.encode("utf-8")))
    return result.stdout.strip()


def execute(private_dir: Path, repo: str, branch: str, sha: str) -> int:
    require({"repo": repo}, "repo", EXPECTED_PRIVATE_REPO, "private_repo_mismatch")
    require({"branch": branch}, "branch", EXPECTED_PRIVATE_BRANCH, "private_branch_mismatch")
    require({"sha": sha}, "sha", EXPECTED_PRIVATE_SHA, "private_sha_argument_mismatch")
    if not (private_dir / ".git").is_dir():
        raise GateError("private_checkout_missing", str(private_dir))
    if observed_head(private_dir) != EXPECTED_PRIVATE_SHA:
        raise GateError("private_checkout_sha_mismatch", observed_head(private_dir))

    evidence = load_json(private_dir / EVIDENCE)
    validate_evidence(evidence)
    main, main_out, main_err = run_validator(private_dir, MAIN_VALIDATOR)
    timing, timing_out, timing_err = run_validator(private_dir, TIMING_VALIDATOR)
    bridge, bridge_out, bridge_err = run_validator(private_dir, BRIDGE_VALIDATOR)
    validate_summaries(main, timing, bridge)

    print("gate_id=VISUAL_RUNTIME_OWNER_PACK_BUILDER_GATE")
    print(f"private_sha={EXPECTED_PRIVATE_SHA}")
    print(f"source_snapshot_sha={EXPECTED_SOURCE_SHA}")
    print(f"combined_test_count={main['test_count']}")
    print("owner_review_pack_test_count=4")
    print(f"shot_count={main['shot_count']}")
    print(f"scene_count={main['scene_count']}")
    print(f"timing_test_count={timing['test_count']}")
    print(f"production_bridge_test_count={bridge['test_count']}")
    print("existing_private_still_count=17")
    print("existing_still_machine_qc_green=true")
    print("rerender_performed=false")
    print("private_review_pack_executed=false")
    print("owner_delivery_channel_available=false")
    print("accepted_timing_available=false")
    print("cross_scene_clip_created=false")
    print("ru_preview_created=false")
    print("human_visual_qc_green=false")
    print(f"deterministic_compile_sha256={main['deterministic_compile_sha256']}")
    print(f"production_bridge_sha256={bridge['bridge_sha256']}")
    print(f"main_stdout_sha256={main_out}")
    print(f"main_stderr_sha256={main_err}")
    print(f"timing_stdout_sha256={timing_out}")
    print(f"timing_stderr_sha256={timing_err}")
    print(f"bridge_stdout_sha256={bridge_out}")
    print(f"bridge_stderr_sha256={bridge_err}")
    print("private_content_public_exposure=false")
    print("public_media_artifacts_created=false")
    print("result=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--private-repo", required=True)
    parser.add_argument("--private-branch", required=True)
    parser.add_argument("--private-sha", required=True)
    args = parser.parse_args()
    try:
        return execute(Path(args.private_dir), args.private_repo, args.private_branch, args.private_sha)
    except GateError as exc:
        print("gate_id=VISUAL_RUNTIME_OWNER_PACK_BUILDER_GATE")
        print("result=FAIL")
        print(f"error_code={exc.code}")
        print(f"error_detail_sha256={sha256_bytes(exc.detail.encode('utf-8'))}")
        print("private_content_public_exposure=false")
        print("public_media_artifacts_created=false")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
