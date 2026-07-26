#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

EXPECTED_REPO = "TheGor-365/ai-course-production-system"
EXPECTED_BRANCH = "repair/gold-s01-visual-runtime-v2"
EXPECTED_SHA = "ae8dafcc3e5634f07d51b9b0dea07410bd867702"
EXPECTED_TESTS = 42
ALLOWED_FILES = {
    "runtime_binding_v1.json", "timing_binding_v1.json", "runtime_identity_v2.json",
    "resolved_ir_identity_v2.json", "no_render_manifest_v2.json",
    "private_render_request_v2.json", "runner_handoff_v2.json",
    "quality_handoff_v2.json", "handoff_v2.json", "package_manifest_v2.json",
}


def run(command: Sequence[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(list(command), cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    combined = completed.stdout + completed.stderr
    if completed.returncode:
        raise RuntimeError(f"COMMAND_FAILED:{command[0]}:{completed.returncode}")
    return combined


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--private-repo", required=True)
    parser.add_argument("--private-branch", required=True)
    parser.add_argument("--private-sha", required=True)
    parser.add_argument("--emit-file", required=True, choices=sorted(ALLOWED_FILES))
    args = parser.parse_args()
    if (args.private_repo, args.private_branch, args.private_sha) != (EXPECTED_REPO, EXPECTED_BRANCH, EXPECTED_SHA):
        raise RuntimeError("FIXED_TARGET_MISMATCH")
    root = Path(args.private_dir)
    if run(["git", "rev-parse", "HEAD"], root).strip() != EXPECTED_SHA:
        raise RuntimeError("CHECKOUT_SHA_MISMATCH")
    if run(["git", "status", "--porcelain"], root).strip():
        raise RuntimeError("CHECKOUT_DIRTY")

    env = os.environ.copy()
    env["PYTHONPATH"] = "11_tools/render_factory"
    test_output = run([
        sys.executable, "-m", "unittest", "discover",
        "-s", "11_tools/render_factory/gold_s01_visual_v2/tests",
        "-p", "test_*.py",
    ], root, env)
    if f"Ran {EXPECTED_TESTS} tests" not in test_output:
        raise RuntimeError("TEST_COUNT_MISMATCH")

    remotion = root / "11_tools/render_factory/remotion"
    run(["npm", "ci"], remotion)
    run(["npm", "run", "typecheck"], remotion)

    script = """
import base64, sys, tempfile
from pathlib import Path
from gold_s01_visual_v2.compiler import build_active_package, write_active_package
from gold_s01_visual_v2.package_v2 import DERIVATION_ORDER, canonical_file_text, make_pending_timing_binding, make_runtime_binding
head=sys.argv[1]
name=sys.argv[2]
runtime=make_runtime_binding(head)
timing=make_pending_timing_binding()
package=build_active_package(runtime,timing)
with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
    write_active_package(first,runtime,timing)
    write_active_package(second,runtime,timing)
    for item in DERIVATION_ORDER:
        if (Path(first)/item).read_bytes() != (Path(second)/item).read_bytes():
            raise SystemExit('REBUILD_DRIFT:'+item)
content=canonical_file_text(package[name]).encode('utf-8')
print('document_b64='+base64.b64encode(content).decode())
print('document_size='+str(len(content)))
print('document_name='+name)
print('runtime_binding_sha256='+package['runtime_binding_v1.json']['runtime_binding_sha256'])
print('timing_binding_sha256='+package['timing_binding_v1.json']['timing_binding_sha256'])
print('no_render_manifest_sha256='+package['no_render_manifest_v2.json']['no_render_manifest_sha256'])
print('visual_input_fingerprint='+package['no_render_manifest_v2.json']['visual_input_fingerprint'])
print('private_render_request_sha256='+package['private_render_request_v2.json']['request_sha256'])
print('package_manifest_sha256='+package['package_manifest_v2.json']['package_manifest_sha256'])
"""
    output = run([sys.executable, "-c", script, EXPECTED_SHA, args.emit_file], root, env)
    print("result=DOCUMENT_READY")
    print(f"private_sha={EXPECTED_SHA}")
    print(f"test_count={EXPECTED_TESTS}")
    print("typescript_typecheck=PASS")
    print("clean_rebuilds_byte_identical=true")
    print(output, end="")
    print("timing_bound=false")
    print("final_render_authorized=false")
    print("media_rendered=false")
    print("no_fake_green=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
