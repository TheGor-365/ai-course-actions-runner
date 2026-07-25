#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

EXPECTED_PRIVATE_REPO = "TheGor-365/ai-course-production-system"
EXPECTED_PRIVATE_BRANCH = "launch/factory-5d-visual-runtime"
EXPECTED_PRIVATE_SHA = "22d953e77bf506855ee4113067f6d6c22a5ab308"
EXPECTED_SOURCE_SNAPSHOT_BRANCH = "launch/factory-5d-content-semantics-snapshot-v9"
EXPECTED_SOURCE_SNAPSHOT_SHA = "f2a6ed754a8a18b0b9e17bfa6f65b32007f50232"
EXPECTED_HANDOFF_V3_HASH = "41d28eb650adef004958d3fb4c243b274245191ef508fccf62bed69a6753273d"
EXPECTED_DAY5_AUDIT_HASH = "a6d7c3486e53d8531a756050b5e4ded9af982c197289f455d534b3a6c7c11002"
EXPECTED_COMBINED_TEST_COUNT = 51

MAIN_VALIDATOR = Path("04_validators/render/validate_visual_runtime_v1.py")
TIMING_VALIDATOR = Path("04_validators/render/validate_visual_runtime_timing_adapter_v1.py")
BRIDGE_VALIDATOR = Path("04_validators/render/validate_visual_runtime_production_bridge_v1.py")
EVIDENCE_PATH = Path(
    "03_modules/M1/L01/04_render_migration/launch_5d/visual_runtime_v1/"
    "actual_content_semantics_snapshot_v9_evidence_s01_v2.json"
)


class GateError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError("evidence_json_unreadable", type(exc).__name__) from exc
    if not isinstance(value, dict):
        raise GateError("evidence_root_not_object", path.as_posix())
    return value


def parse_last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise GateError("validator_summary_missing", sha256_bytes(text.encode("utf-8")))


def require_equal(record: Mapping[str, Any], key: str, expected: Any, *, code: str) -> None:
    observed = record.get(key)
    if observed != expected:
        raise GateError(code, f"{key}:{observed!r}!={expected!r}")


def require_false(record: Mapping[str, Any], key: str, *, code: str) -> None:
    require_equal(record, key, False, code=code)


def require_true(record: Mapping[str, Any], key: str, *, code: str) -> None:
    require_equal(record, key, True, code=code)


def validate_evidence(evidence: Mapping[str, Any]) -> None:
    require_equal(
        evidence,
        "status",
        "YELLOW_IMMUTABLE_SNAPSHOT_V9_CONNECTED_PUBLIC_RUNNER_PENDING",
        code="evidence_status_mismatch",
    )
    source = evidence.get("source_authority")
    adapter = evidence.get("adapter_result")
    validation = evidence.get("validation")
    non_claims = evidence.get("non_claims")
    if not all(isinstance(value, dict) for value in (source, adapter, validation, non_claims)):
        raise GateError("evidence_sections_missing", "source/adapter/validation/non_claims")

    require_equal(source, "repository", "TheGor-365/ai-course-source-library", code="source_repo_mismatch")
    require_equal(source, "pull_request", 55, code="source_pr_mismatch")
    require_equal(
        source,
        "immutable_snapshot_branch",
        EXPECTED_SOURCE_SNAPSHOT_BRANCH,
        code="source_snapshot_branch_mismatch",
    )
    require_equal(
        source,
        "immutable_snapshot_sha",
        EXPECTED_SOURCE_SNAPSHOT_SHA,
        code="source_snapshot_sha_mismatch",
    )
    require_equal(source, "rolling_head_snapshot_compare", "IDENTICAL", code="source_compare_mismatch")
    require_equal(source, "handoff_v3_content_hash", EXPECTED_HANDOFF_V3_HASH, code="handoff_hash_mismatch")
    require_equal(
        source,
        "day5_closure_audit_content_hash",
        EXPECTED_DAY5_AUDIT_HASH,
        code="day5_audit_hash_mismatch",
    )
    require_equal(source, "semantic_units", 13, code="semantic_unit_count_mismatch")
    require_equal(source, "shotir_source_inputs", 26, code="source_input_count_mismatch")
    require_false(source, "source_snapshot_exact_gate_green", code="source_gate_false_required")
    require_false(source, "source_validator_green", code="source_validator_false_required")

    require_equal(adapter, "source_head_binding", "IMMUTABLE_SNAPSHOT", code="adapter_binding_mismatch")
    require_equal(adapter, "semantic_unit_count", 13, code="adapter_unit_count_mismatch")
    require_equal(adapter, "resolved_shot_count", 26, code="adapter_shot_count_mismatch")
    require_equal(adapter, "visible_source_ids", 0, code="visible_source_id_mismatch")
    require_false(adapter, "manual_timing_fabricated", code="manual_timing_claim")
    require_false(adapter, "render_executed", code="evidence_render_claim")

    require_equal(
        validation,
        "combined_expected_test_count",
        EXPECTED_COMBINED_TEST_COUNT,
        code="expected_test_count_mismatch",
    )
    require_equal(validation, "private_actions_job_steps", 0, code="private_actions_steps_mismatch")
    require_false(validation, "clean_checkout_green", code="pre_runner_clean_green_claim")
    require_false(validation, "github_actions_green", code="pre_runner_actions_green_claim")

    for key in (
        "source_pull_request_accepted",
        "source_clean_execution_green",
        "human_visual_qc_green",
        "render_green",
        "production_green",
        "release_green",
    ):
        require_false(non_claims, key, code=f"non_claim_{key}_mismatch")
    require_true(evidence, "no_fake_green", code="no_fake_green_missing")


def validate_main_summary(summary: Mapping[str, Any]) -> None:
    expected = {
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
    }
    for key, value in expected.items():
        require_equal(summary, key, value, code="main_summary_mismatch")
    digest = summary.get("deterministic_compile_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise GateError("main_compile_hash_invalid", repr(digest))


def validate_timing_summary(summary: Mapping[str, Any]) -> None:
    expected = {
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
    for key, value in expected.items():
        require_equal(summary, key, value, code="timing_summary_mismatch")


def validate_bridge_summary(summary: Mapping[str, Any]) -> None:
    expected = {
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
    }
    for key, value in expected.items():
        require_equal(summary, key, value, code="bridge_summary_mismatch")
    digest = summary.get("bridge_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise GateError("bridge_hash_invalid", repr(digest))


def run_validator(private_dir: Path, relative_path: Path) -> tuple[dict[str, Any], str, str]:
    target = private_dir / relative_path
    if not target.is_file():
        raise GateError("validator_file_missing", relative_path.as_posix())
    completed = subprocess.run(
        [sys.executable, relative_path.as_posix()],
        cwd=private_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_hash = sha256_bytes(completed.stdout.encode("utf-8"))
    stderr_hash = sha256_bytes(completed.stderr.encode("utf-8"))
    if completed.returncode != 0:
        raise GateError(
            "validator_failed",
            f"{relative_path.name}:rc={completed.returncode}:out={stdout_hash}:err={stderr_hash}",
        )
    return parse_last_json(completed.stdout), stdout_hash, stderr_hash


def observed_git_sha(private_dir: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(private_dir), "rev-parse", "HEAD"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise GateError("git_head_unreadable", sha256_bytes(completed.stderr.encode("utf-8")))
    return completed.stdout.strip()


def execute(private_dir: Path, private_repo: str, private_branch: str, private_sha: str) -> int:
    if private_repo != EXPECTED_PRIVATE_REPO:
        raise GateError("private_repo_mismatch", private_repo)
    if private_branch != EXPECTED_PRIVATE_BRANCH:
        raise GateError("private_branch_mismatch", private_branch)
    if private_sha != EXPECTED_PRIVATE_SHA:
        raise GateError("private_sha_argument_mismatch", private_sha)
    if not (private_dir / ".git").is_dir():
        raise GateError("private_checkout_missing", str(private_dir))
    observed_sha = observed_git_sha(private_dir)
    if observed_sha != EXPECTED_PRIVATE_SHA:
        raise GateError("private_checkout_sha_mismatch", observed_sha)

    evidence_file = private_dir / EVIDENCE_PATH
    if not evidence_file.is_file():
        raise GateError("evidence_file_missing", EVIDENCE_PATH.as_posix())
    evidence = load_json(evidence_file)
    validate_evidence(evidence)

    main, main_out_hash, main_err_hash = run_validator(private_dir, MAIN_VALIDATOR)
    validate_main_summary(main)
    timing, timing_out_hash, timing_err_hash = run_validator(private_dir, TIMING_VALIDATOR)
    validate_timing_summary(timing)
    bridge, bridge_out_hash, bridge_err_hash = run_validator(private_dir, BRIDGE_VALIDATOR)
    validate_bridge_summary(bridge)

    evidence_hash = sha256_bytes(canonical_json(evidence))
    print("gate_id=VISUAL_RUNTIME_LAUNCH_GATE")
    print(f"private_repo={EXPECTED_PRIVATE_REPO}")
    print(f"private_branch={EXPECTED_PRIVATE_BRANCH}")
    print(f"private_sha={EXPECTED_PRIVATE_SHA}")
    print(f"source_snapshot_branch={EXPECTED_SOURCE_SNAPSHOT_BRANCH}")
    print(f"source_snapshot_sha={EXPECTED_SOURCE_SNAPSHOT_SHA}")
    print(f"combined_test_count={main['test_count']}")
    print(f"shot_count={main['shot_count']}")
    print(f"scene_count={main['scene_count']}")
    print(f"timing_test_count={timing['test_count']}")
    print(f"production_bridge_test_count={bridge['test_count']}")
    print(f"production_duration_ms={bridge['duration_ms']}")
    print(f"production_total_frames={bridge['total_frames']}")
    print(f"existing_private_still_count={bridge['existing_still_artifact_count']}")
    print("existing_still_machine_qc_green=true")
    print("existing_still_human_qc_green=false")
    print("private_review_pack_executed=false")
    print("render_executed=false")
    print("render_green_claimed=false")
    print("production_green=false")
    print("release_green=false")
    print(f"deterministic_compile_sha256={main['deterministic_compile_sha256']}")
    print(f"production_bridge_sha256={bridge['bridge_sha256']}")
    print(f"evidence_canonical_sha256={evidence_hash}")
    print(f"main_stdout_sha256={main_out_hash}")
    print(f"main_stderr_sha256={main_err_hash}")
    print(f"timing_stdout_sha256={timing_out_hash}")
    print(f"timing_stderr_sha256={timing_err_hash}")
    print(f"bridge_stdout_sha256={bridge_out_hash}")
    print(f"bridge_stderr_sha256={bridge_err_hash}")
    print("private_content_public_exposure=false")
    print("public_media_artifacts_created=false")
    print("artifacts_created=false")
    print("no_fake_green=true")
    print("result=PASS")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fixed exact-SHA visual-runtime no-render gate")
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--private-repo", required=True)
    parser.add_argument("--private-branch", required=True)
    parser.add_argument("--private-sha", required=True)
    args = parser.parse_args(argv)
    try:
        return execute(
            args.private_dir.resolve(),
            args.private_repo,
            args.private_branch,
            args.private_sha,
        )
    except GateError as exc:
        print("gate_id=VISUAL_RUNTIME_LAUNCH_GATE")
        print("result=FAIL")
        print("error_class=visual_runtime_gate")
        print(f"error_code={exc.code}")
        print(f"error_detail_sha256={sha256_bytes(exc.detail.encode('utf-8'))}")
        print("private_content_public_exposure=false")
        print("public_media_artifacts_created=false")
        print("artifacts_created=false")
        print("render_executed=false")
        print("render_green_claimed=false")
        print("no_fake_green=true")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
