#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/private_executor_fixture.py"


class PrivateExecutorFixtureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.request = self.root / "request.json"
        self.request.write_text(json.dumps({
            "schema_version": "PRIVATE_EXECUTOR_REQUEST_v1",
            "request_id": "req-fixture-001",
            "package_request_id": "pkg-fixture-001",
            "station_id": "fixture_station",
            "attempt_id": "attempt-001",
            "executor_class": "fixture",
            "input_manifest_pointer": "private://fixture/input.json",
            "input_hash": "a" * 64,
            "command_profile_id": "FIXTURE_PROFILE_V1",
            "runtime_lock_id": "fixture-runtime-lock-v1",
            "resource_limits": {"cpu": 1, "memory_mb": 128},
            "timeout_seconds": 30,
            "output_artifact_types": ["fixture_artifact"],
            "idempotency_key": "fixture-idempotency-key-0001",
            "resume_token_optional": None,
            "cleanup_policy": "always"
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_fixture(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), str(self.request), str(self.root / "work"), *extra],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_retry_resume_restore_and_idempotency(self) -> None:
        failed = self.run_fixture("--inject-retryable-failure")
        self.assertEqual(failed.returncode, 75)
        failure_receipt = json.loads(failed.stdout)
        self.assertEqual(failure_receipt["failure_class"], "STATION_RETRYABLE_FAILURE")
        self.assertTrue(failure_receipt["retryable"])
        self.assertFalse(failure_receipt["private_content_public_exposure"])

        resumed = self.run_fixture()
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        receipt = json.loads(resumed.stdout)
        self.assertEqual(receipt["result"], "PASS")
        self.assertTrue(receipt["sanitized_metrics"]["restore_sha_match"])
        self.assertEqual(receipt["output_artifacts"][0]["restore_status"], "PASS")
        self.assertTrue(receipt["output_artifacts"][0]["private_storage_pointer"].startswith("private://"))

        repeated = self.run_fixture()
        repeated_receipt = json.loads(repeated.stdout)
        self.assertTrue(repeated_receipt["sanitized_metrics"]["completed_station_reused"])
        self.assertEqual(
            repeated_receipt["output_artifacts"][0]["sha256"],
            receipt["output_artifacts"][0]["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
