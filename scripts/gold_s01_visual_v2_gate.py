#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

EXPECTED_REPO = "TheGor-365/ai-course-production-system"
EXPECTED_BRANCH = "repair/gold-s01-visual-runtime-v2"
EXPECTED_SHA = "a4943794f19af0c761be56fbcc8d3906add01b17"
EXPECTED_PR = 349
EXPECTED_RUNTIME_HEAD = "ae8dafcc3e5634f07d51b9b0dea07410bd867702"
EXPECTED_TESTS = 42
EXPECTED_NO_RENDER = "9d8a7cee6a53b28721c48af520220176afb8ad3995f1ee9184072aeb0a99b73a"
EXPECTED_FINGERPRINT = "847c4971b5660501e1d10e884c47f129c1ea73a7dcd854613bcb14a5ca299018"
EXPECTED_PACKAGE = "1d7612e00dd6316d8353403fa3da396e2f0e67986ca8d5cf349f3aff78740f7e"
EXPECTED_REQUEST = "51f0e7f1d3c5cb9f4ca5c0ac9a43df2fbfb88dd763f503f8fc661e1df5ca89b4"


class GateError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}:{detail}")
        self.code = code
        self.detail = detail


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def run(command: Sequence[str], cwd: Path, code: str, env: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(list(command), cwd=cwd, env=dict(env) if env else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode:
        raise GateError(code, f"rc={completed.returncode}:out={hash_text(completed.stdout)}:err={hash_text(completed.stderr)}")
    return completed.stdout


def last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise GateError("SUMMARY_MISSING", hash_text(text))


def require(summary: Mapping[str, Any], expected: Mapping[str, Any], stage: str) -> None:
    mismatches = [f"{key}:{summary.get(key)!r}!={value!r}" for key, value in expected.items() if summary.get(key) != value]
    if mismatches:
        raise GateError(f"{stage}_SUMMARY_MISMATCH", ";".join(mismatches))


def execute(private_dir: Path, repo: str, branch: str, sha: str) -> dict[str, Any]:
    if (repo, branch, sha) != (EXPECTED_REPO, EXPECTED_BRANCH, EXPECTED_SHA):
        raise GateError("FIXED_TARGET_MISMATCH", f"{repo}:{branch}:{sha}")
    if not (private_dir / ".git").is_dir():
        raise GateError("CHECKOUT_MISSING", str(private_dir))
    if run(["git", "rev-parse", "HEAD"], private_dir, "GIT_HEAD_FAILED").strip() != EXPECTED_SHA:
        raise GateError("CHECKOUT_SHA_MISMATCH", "HEAD")
    if run(["git", "status", "--porcelain"], private_dir, "GIT_STATUS_FAILED").strip():
        raise GateError("CHECKOUT_DIRTY", "true")

    python_files = [
        "11_tools/render_factory/gold_s01_visual_v2/__init__.py",
        "11_tools/render_factory/gold_s01_visual_v2/blueprint.py",
        "11_tools/render_factory/gold_s01_visual_v2/core.py",
        "11_tools/render_factory/gold_s01_visual_v2/ir.py",
        "11_tools/render_factory/gold_s01_visual_v2/qc.py",
        "11_tools/render_factory/gold_s01_visual_v2/handoffs.py",
        "11_tools/render_factory/gold_s01_visual_v2/compiler.py",
        "11_tools/render_factory/gold_s01_visual_v2/package_v2.py",
        "11_tools/render_factory/gold_s01_visual_v2/tests/test_gold_s01_visual_v2.py",
        "11_tools/render_factory/gold_s01_visual_v2/tests/test_package_v2.py",
        "04_validators/render/validate_gold_s01_visual_v2.py",
        "04_validators/render/validate_gold_s01_visual_v2_package.py",
        "04_validators/render/validate_gold_s01_visual_v2_reproducibility.py",
    ]
    run([sys.executable, "-m", "py_compile", *python_files], private_dir, "PYTHON_COMPILE_FAILED")
    env = os.environ.copy()
    env["PYTHONPATH"] = "11_tools/render_factory"

    no_render = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2.py"], private_dir, "NO_RENDER_VALIDATOR_FAILED", env))
    require(no_render, {
        "status": "PASS_GOLD_S01_VISUAL_V2_NO_RENDER",
        "test_count": EXPECTED_TESTS,
        "semantic_units": 13,
        "shot_ir_count": 26,
        "scene_ir_count": 26,
        "assets_materialized": 18,
        "unresolved_assets": 0,
        "visual_runtime_head": EXPECTED_RUNTIME_HEAD,
        "no_render_manifest_sha256": EXPECTED_NO_RENDER,
        "visual_input_fingerprint": EXPECTED_FINGERPRINT,
        "package_manifest_sha256": EXPECTED_PACKAGE,
        "private_render_request_status": "READY_BLOCKED_ONLY_BY_ACCEPTED_TIMING",
        "timing_bound": False,
        "caption_binding_complete": False,
        "package_rebuild_stable": True,
        "final_render_authorized": False,
        "no_fake_green": True,
    }, "NO_RENDER")

    package = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2_package.py"], private_dir, "PACKAGE_VALIDATOR_FAILED", env))
    require(package, {
        "status": "PASS_GOLD_S01_COMMITTED_PACKAGE_V2",
        "shot_ir_count": 26,
        "scene_ir_count": 26,
        "asset_count": 18,
        "active_document_count": 10,
        "visual_runtime_head": EXPECTED_RUNTIME_HEAD,
        "no_render_manifest_sha256": EXPECTED_NO_RENDER,
        "visual_input_fingerprint": EXPECTED_FINGERPRINT,
        "package_manifest_sha256": EXPECTED_PACKAGE,
        "private_render_request_sha256": EXPECTED_REQUEST,
        "private_render_request_status": "READY_BLOCKED_ONLY_BY_ACCEPTED_TIMING",
        "timing_bound": False,
        "committed_package_byte_identical": True,
        "package_rebuild_stable": True,
        "stale_embedded_hash_rejected": True,
        "final_render_authorized": False,
        "no_fake_green": True,
    }, "PACKAGE")

    reproducibility = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2_reproducibility.py"], private_dir, "REPRODUCIBILITY_VALIDATOR_FAILED", env))
    require(reproducibility, {
        "status": "PASS_GOLD_S01_REPRODUCIBILITY",
        "active_document_count": 10,
        "clean_rebuilds_byte_identical": True,
        "committed_package_byte_identical": True,
        "no_fake_green": True,
    }, "REPRODUCIBILITY")

    remotion = private_dir / "11_tools/render_factory/remotion"
    run(["npm", "ci"], remotion, "NPM_CI_FAILED")
    run(["npm", "run", "typecheck"], remotion, "TYPESCRIPT_TYPECHECK_FAILED")

    forbidden = [path.name for path in (private_dir / "03_modules/M1/L01/04_render_migration/gold_s01_visual_v2").rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".mp4", ".wav", ".mov", ".webm"}]
    if forbidden:
        raise GateError("MEDIA_BINARY_IN_GIT", ",".join(forbidden))

    return {
        "result": "PASS",
        "private_sha": EXPECTED_SHA,
        "visual_runtime_head": EXPECTED_RUNTIME_HEAD,
        "test_count": EXPECTED_TESTS,
        "semantic_units": 13,
        "shot_ir_count": 26,
        "scene_ir_count": 26,
        "assets_materialized": 18,
        "active_document_count": 10,
        "no_render_manifest_sha256": EXPECTED_NO_RENDER,
        "visual_input_fingerprint": EXPECTED_FINGERPRINT,
        "package_manifest_sha256": EXPECTED_PACKAGE,
        "private_render_request_sha256": EXPECTED_REQUEST,
        "typescript_typecheck": "PASS",
        "committed_package": "PASS_BYTE_IDENTICAL",
        "clean_rebuilds_byte_identical": True,
        "stale_embedded_hash_rejected": True,
        "timing_bound": False,
        "final_render_authorized": False,
        "media_rendered": False,
        "human_final_preview_accepted": False,
        "public_media_artifacts_created": False,
        "private_content_public_exposure": False,
        "no_fake_green": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--private-repo", required=True)
    parser.add_argument("--private-branch", required=True)
    parser.add_argument("--private-sha", required=True)
    args = parser.parse_args()
    try:
        result = execute(Path(args.private_dir), args.private_repo, args.private_branch, args.private_sha)
    except GateError as exc:
        print(f"result=FAIL\nerror_code={exc.code}\ndiagnostic_hash={hash_text(exc.detail)}\nno_fake_green=true")
        return 1
    for key, value in result.items():
        print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
