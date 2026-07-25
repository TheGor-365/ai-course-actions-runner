#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys
from pathlib import Path
from typing import Any, Mapping, Sequence
EXPECTED_REPO = "TheGor-365/ai-course-production-system"
EXPECTED_BRANCH = "repair/gold-s01-visual-runtime-v2"
EXPECTED_SHA = "42d9a351f4085639fc0c0813ee9cef31cdbc0b37"
EXPECTED_PR = 349
EXPECTED_NO_RENDER = "e71157aa5cf3d43281fb274ebad41fbc082716e94bc37f9ef534ae5d42b5d109"
EXPECTED_FINGERPRINT = "5d6d4c194b363571a504ef35a3bd00d767fcd53241dd6cb683ae36867a3253f4"
class GateError(ValueError):
    def __init__(self, code: str, detail: str, metadata: Mapping[str, Any] | None = None) -> None:
        super().__init__(f"{code}:{detail}"); self.code = code; self.detail = detail; self.metadata = dict(metadata or {})
def hash_text(text: str) -> str: return hashlib.sha256(text.encode()).hexdigest()
def run(cmd: Sequence[str], cwd: Path, code: str = "COMMAND_FAILED", env: Mapping[str, str] | None = None) -> str:
    done = subprocess.run(list(cmd), cwd=cwd, env=dict(env) if env else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if done.returncode:
        raise GateError(code, f"rc={done.returncode}:out={hash_text(done.stdout)}:err={hash_text(done.stderr)}")
    return done.stdout
def last_json(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        try: value = json.loads(line)
        except json.JSONDecodeError: continue
        if isinstance(value, dict): return value
    raise GateError("SUMMARY_MISSING", hash_text(text))
def validate_summary(summary: Mapping[str, Any], package: bool = False, metadata: Mapping[str, Any] | None = None) -> None:
    expected = {"shot_ir_count": 26, "scene_ir_count": 26, "no_render_manifest_sha256": EXPECTED_NO_RENDER, "visual_input_fingerprint": EXPECTED_FINGERPRINT, "timing_bound": False, "final_render_authorized": False, "no_fake_green": True}
    if not package:
        expected.update({"semantic_units": 13, "test_count": 36, "assets_materialized": 18, "unresolved_assets": 0, "representative_qc_pack_ready": True, "private_render_request_ready": True, "full_visual_master_rendered": False, "human_final_preview_accepted": False})
    mismatches = [f"{key}:{summary.get(key)!r}!={value!r}" for key, value in expected.items() if summary.get(key) != value]
    if mismatches:
        raise GateError("SUMMARY_MISMATCH", ";".join(mismatches), metadata)
def validate_args(repo: str, branch: str, sha: str) -> None:
    if repo != EXPECTED_REPO: raise GateError("REPO_MISMATCH", repo)
    if branch != EXPECTED_BRANCH: raise GateError("BRANCH_MISMATCH", branch)
    if sha != EXPECTED_SHA: raise GateError("SHA_MISMATCH", sha)
def execute(private_dir: Path, repo: str, branch: str, sha: str) -> dict[str, Any]:
    validate_args(repo, branch, sha)
    if not (private_dir / ".git").is_dir(): raise GateError("CHECKOUT_MISSING", str(private_dir))
    observed = run(["git", "rev-parse", "HEAD"], private_dir, "GIT_HEAD_FAILED").strip()
    if observed != EXPECTED_SHA: raise GateError("CHECKOUT_SHA_MISMATCH", observed)
    if run(["git", "status", "--porcelain"], private_dir, "GIT_STATUS_FAILED").strip(): raise GateError("CHECKOUT_DIRTY", "true")
    run([sys.executable, "-m", "py_compile", "11_tools/render_factory/gold_s01_visual_v2/__init__.py", "11_tools/render_factory/gold_s01_visual_v2/blueprint.py", "11_tools/render_factory/gold_s01_visual_v2/core.py", "11_tools/render_factory/gold_s01_visual_v2/ir.py", "11_tools/render_factory/gold_s01_visual_v2/qc.py", "11_tools/render_factory/gold_s01_visual_v2/handoffs.py", "11_tools/render_factory/gold_s01_visual_v2/compiler.py", "11_tools/render_factory/gold_s01_visual_v2/tests/test_gold_s01_visual_v2.py", "04_validators/render/validate_gold_s01_visual_v2.py", "04_validators/render/validate_gold_s01_visual_v2_package.py"], private_dir, "PYTHON_COMPILE_FAILED")
    env = os.environ.copy(); env["PYTHONPATH"] = "11_tools/render_factory"
    metadata_script = """
import json
from gold_s01_visual_v2.compiler import build_all
d=build_all(); n=d['no_render_manifest_v1.json']; i=n['content_addressed_inputs']
print(json.dumps({
 'no_render_manifest_sha256':n['no_render_manifest_sha256'],
 'visual_input_fingerprint':n['visual_input_fingerprint'],
 'asset_registry_sha256':d['asset_registry_v1.json']['asset_registry_sha256'],
 'shot_ir_sha256':d['resolved_shot_ir_v1.json']['resolved_shot_ir_sha256'],
 'scene_ir_sha256':d['resolved_scene_ir_v1.json']['resolved_scene_ir_sha256'],
 'private_render_request_sha256':d['private_render_request_v1.json']['request_sha256'],
 'component_source_sha256':i['component_source_sha256'],
 'runtime_source_sha256':i['runtime_source_sha256'],
 'representative_source_sha256':i['representative_composition_source_sha256']
},sort_keys=True))
"""
    metadata = last_json(run([sys.executable, "-c", metadata_script], private_dir, "METADATA_COLLECTION_FAILED", env))
    no_render = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2.py"], private_dir, "NO_RENDER_VALIDATOR_FAILED", env)); validate_summary(no_render, metadata=metadata)
    package = last_json(run([sys.executable, "04_validators/render/validate_gold_s01_visual_v2_package.py"], private_dir, "PACKAGE_VALIDATOR_FAILED", env)); validate_summary(package, package=True, metadata=metadata)
    remotion = private_dir / "11_tools/render_factory/remotion"
    run(["npm", "ci"], remotion, "NPM_CI_FAILED")
    run(["npm", "run", "typecheck"], remotion, "TYPESCRIPT_TYPECHECK_FAILED")
    forbidden = [path.name for path in (private_dir / "03_modules/M1/L01/04_render_migration/gold_s01_visual_v2").rglob("*") if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".mp4", ".wav", ".mov", ".webm"}]
    if forbidden: raise GateError("MEDIA_BINARY_IN_GIT", ",".join(forbidden))
    return {"result": "PASS", "private_sha": EXPECTED_SHA, "test_count": 36, "semantic_units": 13, "shot_ir_count": 26, "scene_ir_count": 26, "assets_materialized": 18, "no_render_manifest_sha256": EXPECTED_NO_RENDER, "visual_input_fingerprint": EXPECTED_FINGERPRINT, "typescript_typecheck": "PASS", "committed_package": "PASS", "timing_bound": False, "final_render_authorized": False, "media_rendered": False, "human_final_preview_accepted": False, "public_media_artifacts_created": False, "private_content_public_exposure": False, "no_fake_green": True}
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--private-dir", required=True); parser.add_argument("--private-repo", required=True); parser.add_argument("--private-branch", required=True); parser.add_argument("--private-sha", required=True); args = parser.parse_args(argv)
    try: result = execute(Path(args.private_dir), args.private_repo, args.private_branch, args.private_sha)
    except GateError as exc:
        safe_detail = exc.detail.replace("\n", " ").replace("\r", " ")[:500]
        print(f"result=FAIL\nerror_code={exc.code}\nerror_detail={safe_detail}\ndiagnostic_hash={hash_text(exc.detail)}")
        for key, value in sorted(exc.metadata.items()): print(f"actual_{key}={value}")
        print("no_fake_green=true"); return 1
    for key, value in result.items(): print(f"{key}={str(value).lower() if isinstance(value, bool) else value}")
    return 0
if __name__ == "__main__": raise SystemExit(main())
