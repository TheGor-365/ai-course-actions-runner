#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

VALIDATOR = Path("04_validators/launch_5d/validate_public_runner_receipt_v1.py")
TEST = Path("04_validators/launch_5d/test_validate_public_runner_receipt_v1.py")
RECEIPT = Path("05_orchestration/launch_5d/runner_infrastructure/receipts/content_semantics_snapshot_v7_run_30158861162.json")
EXPECTED_RUNNER_SHA = "197a3833e31a4638a304ad3de8e10c34d5506b2e"
EXPECTED_PRIVATE_SHA = "0bbe50ba192c6b627f055b9ce0fa7dd4d9b5f902"
EXPECTED_GATE = "CONTENT_SEMANTICS_LAUNCH_GATE"
EXPECTED_CONTEXT = "public-runner/launch-5d/content-semantics-day2"


def run_fixed(name: str, command: list[str], cwd: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=120,
    )
    if completed.returncode == 0:
        return
    print("gate_id=PRODUCTION_RUNNER_EVIDENCE_CONSUMER_GATE")
    print("result=FAIL")
    print("error_class=production_consumer_validation_failure")
    print("failed_step=" + name)
    print("diagnostic_hash=" + hashlib.sha256(completed.stdout.encode()).hexdigest())
    print("private_content_printed=false")
    raise SystemExit(1)


def main() -> int:
    private = Path(sys.argv[1]).resolve() if len(sys.argv) == 2 else None
    if private is None or not (private / ".git").is_dir():
        print("gate_id=PRODUCTION_RUNNER_EVIDENCE_CONSUMER_GATE")
        print("result=FAIL")
        print("error_class=policy")
        print("error_code=private_checkout_missing")
        print("private_content_printed=false")
        return 2
    required = [VALIDATOR, TEST, RECEIPT]
    missing = [str(path) for path in required if not (private / path).is_file()]
    if missing:
        print("gate_id=PRODUCTION_RUNNER_EVIDENCE_CONSUMER_GATE")
        print("result=FAIL")
        print("error_class=missing_required_file")
        print("missing_count=" + str(len(missing)))
        print("missing_set_hash=" + hashlib.sha256("\n".join(missing).encode()).hexdigest())
        print("private_content_printed=false")
        return 1
    run_fixed("py_compile", [sys.executable, "-m", "py_compile", str(VALIDATOR), str(TEST)], private)
    run_fixed("consumer_unit_tests", [sys.executable, "-m", "unittest", str(TEST), "-v"], private)
    run_fixed(
        "actual_receipt_validation",
        [
            sys.executable,
            str(VALIDATOR),
            "--receipt",
            str(RECEIPT),
            "--expected-runner-sha",
            EXPECTED_RUNNER_SHA,
            "--expected-private-sha",
            EXPECTED_PRIVATE_SHA,
            "--expected-gate-id",
            EXPECTED_GATE,
            "--expected-status-context",
            EXPECTED_CONTEXT,
            "--require-pass",
        ],
        private,
    )
    print("gate_id=PRODUCTION_RUNNER_EVIDENCE_CONSUMER_GATE")
    print("consumer_unit_tests=5")
    print("actual_receipt_valid=true")
    print("actual_runner_sha=" + EXPECTED_RUNNER_SHA)
    print("actual_private_sha=" + EXPECTED_PRIVATE_SHA)
    print("private_content_printed=false")
    print("public_media_artifacts_created=false")
    print("production_green_claimed=false")
    print("result=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
