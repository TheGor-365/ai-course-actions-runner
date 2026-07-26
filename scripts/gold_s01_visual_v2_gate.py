#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
from typing import Any, Mapping, Sequence

EXPECTED_REPO = "TheGor-365/ai-course-production-system"
EXPECTED_BRANCH = "repair/gold-s01-production-composition-pilot-v1"
EXPECTED_SHA = "36fcfcc2dcb2e7251869f8be46f414a16586838a"
EXPECTED_PR = 354
EXPECTED_RUNTIME_HEAD = "ae8dafcc3e5634f07d51b9b0dea07410bd867702"
EXPECTED_LEGACY_TESTS = 49
EXPECTED_PRODUCTION_TESTS = 17
EXPECTED_NO_RENDER = "636f37d628ac8c56d9c8241a928ca395e95c65060da257c082dcc632a595b920"
EXPECTED_BASE_FINGERPRINT = "7e8ca777786698b5d52bb951594aac069b1977482be64a7229a5c7ba246b5e6a"
EXPECTED_PACKAGE = "dbb860fa0c3aebbd43879a5ffb80814d4adc92614eac63af394df11033192abd"
EXPECTED_LEGACY_REQUEST = "631efacdd23d9ca7fa2b8a07ef3e5a8292d176c7949b35427e7f4c4f4af7d720"
EXPECTED_PRODUCTION_MANIFEST = "1dccf4c521bd375ea5b7c68e97ac11bc506a04d0e48aab3f5ba33622903be63f"
EXPECTED_PRODUCTION_FINGERPRINT = "6983fb0ba08ca621c553804abbebfcc372b9d68e68176c2a8efaff62676f6b97"
PILOT_ID, FULL_ID = "GoldS01HybridPilot60s", "GoldS01HybridFull15m"

class GateError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}:{detail}"); self.code = code; self.detail = detail

def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def run(command: Sequence[str], cwd: Path, code: str, env: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(list(command), cwd=cwd, env=dict(env) if env else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, shell=False)
    if completed.returncode:
        raise GateError(code, f"rc={completed.returncode}:out={digest(completed.stdout)}:err={digest(completed.stderr)}")
    return completed.stdout

def last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        try: value = json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(value, dict): return value
    raise GateError("SUMMARY_MISSING", digest(text))

def require(summary: Mapping[str, Any], expected: Mapping[str, Any], stage: str) -> None:
    drift = [f"{key}:{summary.get(key)!r}!={value!r}" for key, value in expected.items() if summary.get(key) != value]
    if drift: raise GateError(f"{stage}_SUMMARY_MISMATCH", ";".join(drift))

def execute(private_dir: Path, repo: str, branch: str, sha: str) -> dict[str, Any]:
    if (repo, branch, sha) != (EXPECTED_REPO, EXPECTED_BRANCH, EXPECTED_SHA):
        raise GateError("FIXED_TARGET_MISMATCH", f"{repo}:{branch}:{sha}")
    if not (private_dir / ".git").is_dir(): raise GateError("CHECKOUT_MISSING", str(private_dir))
    if run(["git", "rev-parse", "HEAD"], private_dir, "GIT_HEAD_FAILED").strip() != EXPECTED_SHA:
        raise GateError("CHECKOUT_SHA_MISMATCH", "HEAD")
    if run(["git", "status", "--porcelain"], private_dir, "GIT_STATUS_FAILED").strip():
        raise GateError("CHECKOUT_DIRTY", "true")

    env = os.environ.copy(); env["PYTHONPATH"] = "11_tools/render_factory"
    legacy = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2.py"], private_dir, "LEGACY_NO_RENDER_FAILED", env))
    require(legacy, {
        "status": "PASS_GOLD_S01_VISUAL_V2_NO_RENDER", "test_count": EXPECTED_LEGACY_TESTS,
        "scene_ir_count": 26, "visual_runtime_head": EXPECTED_RUNTIME_HEAD,
        "no_render_manifest_sha256": EXPECTED_NO_RENDER,
        "visual_input_fingerprint": EXPECTED_BASE_FINGERPRINT,
        "package_manifest_sha256": EXPECTED_PACKAGE,
        "timing_bound": True, "caption_binding_complete": True,
        "final_render_authorized": False, "no_fake_green": True,
    }, "LEGACY")

    package = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2_package.py"], private_dir, "LEGACY_PACKAGE_FAILED", env))
    require(package, {
        "status": "PASS_GOLD_S01_COMMITTED_PACKAGE_V2",
        "private_render_request_sha256": EXPECTED_LEGACY_REQUEST,
        "package_manifest_sha256": EXPECTED_PACKAGE,
        "committed_package_byte_identical": True,
        "package_rebuild_stable": True, "no_fake_green": True,
    }, "PACKAGE")

    production = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_production_composition.py"], private_dir, "PRODUCTION_NO_RENDER_FAILED", env))
    require(production, {
        "status": "PASS_GOLD_S01_PRODUCTION_COMPOSITION_NO_RENDER",
        "test_count": EXPECTED_PRODUCTION_TESTS,
        "pilot_composition_id": PILOT_ID, "pilot_duration_in_frames": 1800,
        "pilot_duration_exact": True, "full_composition_id": FULL_ID,
        "full_duration_in_frames": 27252, "full_duration_exact": True,
        "scene_coverage": "26/26", "fixed_production_adapter_present": True,
        "production_input_fingerprint": EXPECTED_PRODUCTION_FINGERPRINT,
        "visual_execution_authorized": True, "final_render_authorized": True,
        "provisional_fields": 0, "no_fake_green": True,
    }, "PRODUCTION")

    run([sys.executable, "-m", "unittest", "discover", "-s", "11_tools/render_factory/gold_s01_visual_v2/tests", "-p", "test_production_composition.py"], private_dir, "PRODUCTION_TESTS_FAILED", env)
    remotion = private_dir / "11_tools/render_factory/remotion"
    run(["npm", "ci"], remotion, "NPM_CI_FAILED")
    run(["npm", "run", "typecheck"], remotion, "TYPESCRIPT_TYPECHECK_FAILED")
    listed = run([(remotion / "node_modules/.bin/remotion").as_posix(), "compositions", "src/goldS01VisualV2/productionRoot.tsx"], remotion, "COMPOSITION_DISCOVERY_FAILED")
    if PILOT_ID not in listed or FULL_ID not in listed: raise GateError("COMPOSITION_IDS_MISSING", digest(listed))

    manifest = json.loads((private_dir / "03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/production_composition_manifest_v1.json").read_text())
    if manifest.get("production_composition_manifest_sha256") != EXPECTED_PRODUCTION_MANIFEST:
        raise GateError("PRODUCTION_MANIFEST_MISMATCH", repr(manifest.get("production_composition_manifest_sha256")))
    forbidden = [path.name for path in (private_dir / "03_modules/M1/L01/04_render_migration/gold_s01_visual_v2").rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".mp4", ".wav", ".mov", ".webm"}]
    if forbidden: raise GateError("MEDIA_BINARY_IN_GIT", ",".join(forbidden))

    return {
        "result": "PASS", "private_sha": EXPECTED_SHA, "private_pr": EXPECTED_PR,
        "visual_runtime_head": EXPECTED_RUNTIME_HEAD,
        "legacy_test_count": EXPECTED_LEGACY_TESTS,
        "production_test_count": EXPECTED_PRODUCTION_TESTS,
        "scene_ir_count": 26, "scene_coverage": "26/26",
        "no_render_manifest_sha256": EXPECTED_NO_RENDER,
        "base_visual_input_fingerprint": EXPECTED_BASE_FINGERPRINT,
        "production_composition_manifest_sha256": EXPECTED_PRODUCTION_MANIFEST,
        "production_input_fingerprint": EXPECTED_PRODUCTION_FINGERPRINT,
        "pilot_composition_id": PILOT_ID, "pilot_duration_in_frames": 1800,
        "full_composition_id": FULL_ID, "full_duration_in_frames": 27252,
        "fixed_production_adapter_present": True,
        "visual_execution_authorized": True, "final_render_authorized": True,
        "typescript_typecheck": "PASS", "composition_discovery": "PASS",
        "media_rendered": False, "human_final_preview_accepted": False,
        "public_media_artifacts_created": False, "no_fake_green": True,
    }

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--private-repo", required=True)
    parser.add_argument("--private-branch", required=True)
    parser.add_argument("--private-sha", required=True)
    args = parser.parse_args()
    try: result = execute(Path(args.private_dir), args.private_repo, args.private_branch, args.private_sha)
    except GateError as exc:
        print(f"result=FAIL\nerror_code={exc.code}\ndiagnostic_hash={digest(exc.detail)}\nno_fake_green=true"); return 1
    for key, value in result.items(): print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
