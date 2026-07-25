from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_cross_repo_sync_v1.py"
EXPECTED = ROOT / "config/factory_sync_epoch_v1.json"


class CrossRepoSyncTests(unittest.TestCase):
    def run_validator(self, observed: Path, expected_code: int = 0) -> str:
        completed = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                "--expected",
                str(EXPECTED),
                "--observed",
                str(observed),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, expected_code, completed.stdout)
        return completed.stdout

    def write_temp(self, value: dict) -> Path:
        handle = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False)
        json.dump(value, handle)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_exact_epoch_passes(self) -> None:
        output = self.run_validator(EXPECTED)
        self.assertIn("CROSS_REPO_SYNC_VALID=true", output)
        self.assertIn("INTEGRATION_REPOSITORY_COUNT=3", output)

    def test_integration_head_drift_fails(self) -> None:
        value = json.loads(EXPECTED.read_text(encoding="utf-8"))
        value["integration_heads"]["TheGor-365/ai-course-production-system"]["sha"] = "f" * 40
        output = self.run_validator(self.write_temp(value), expected_code=1)
        self.assertIn("FAILURE_CLASS=CROSS_REPO_DRIFT", output)
        self.assertIn("integration:TheGor-365/ai-course-production-system", output)

    def test_upstream_head_drift_fails(self) -> None:
        value = json.loads(EXPECTED.read_text(encoding="utf-8"))
        value["active_upstream_heads"]["content-semantics"]["sha"] = "e" * 40
        output = self.run_validator(self.write_temp(value), expected_code=1)
        self.assertIn("upstream:content-semantics", output)

    def test_invalid_sha_contract_fails_closed(self) -> None:
        value = json.loads(EXPECTED.read_text(encoding="utf-8"))
        value["integration_heads"]["TheGor-365/ai-course-actions-runner"]["sha"] = "short"
        output = self.run_validator(self.write_temp(value), expected_code=2)
        self.assertIn("FAILURE_CLASS=CROSS_REPO_SYNC_CONTRACT_INVALID", output)


if __name__ == "__main__":
    unittest.main()
