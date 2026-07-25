from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/alignment_model_provisioning_v1.py"
PROFILE = ROOT / "config/alignment_model_profile_v1.json"


class AlignmentModelProvisioningTests(unittest.TestCase):
    def run_cmd(self, *args: str, expected: int = 0) -> str:
        completed = subprocess.run(
            list(args),
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, expected, completed.stdout)
        return completed.stdout

    def test_locked_profile(self) -> None:
        profile = json.loads(PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(profile["profile_id"], "ALIGNMENT_MODEL_RU_WAV2VEC2_V1")
        self.assertEqual(profile["model_revision"], "2329100508896c6d9b157019803ab5601e6f3406")
        self.assertFalse(profile["arbitrary_model_repo_allowed"])
        self.assertFalse(profile["arbitrary_revision_allowed"])
        self.assertTrue(profile["resume_required"])
        self.assertFalse(profile["public_artifacts_allowed"])

    def test_interrupt_resume_checksum_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "source.bin"
            destination = temp / "destination.bin"
            receipt1 = temp / "receipt1.json"
            receipt2 = temp / "receipt2.json"
            receipt3 = temp / "receipt3.json"
            source.write_bytes((b"alignment-model-fixture-v1\n" * 60000))
            expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()

            first = self.run_cmd(
                sys.executable,
                str(SCRIPT),
                "resume-copy-fixture",
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--receipt",
                str(receipt1),
                "--expected-sha256",
                expected_sha,
                "--interrupt-after-bytes",
                "131072",
                expected=75,
            )
            self.assertIn("result=RETRYABLE_FAILURE", first)
            first_receipt = json.loads(receipt1.read_text(encoding="utf-8"))
            self.assertEqual(first_receipt["failure_class"], "DOWNLOAD_INTERRUPTED")
            self.assertGreater(destination.stat().st_size, 0)
            partial_size = destination.stat().st_size

            second = self.run_cmd(
                sys.executable,
                str(SCRIPT),
                "resume-copy-fixture",
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--receipt",
                str(receipt2),
                "--expected-sha256",
                expected_sha,
            )
            self.assertIn("result=PASS", second)
            self.assertNotIn(str(destination), second)
            second_receipt = json.loads(receipt2.read_text(encoding="utf-8"))
            self.assertEqual(second_receipt["resume_offset"], partial_size)
            self.assertEqual(second_receipt["sha256"], expected_sha)
            self.assertEqual(destination.read_bytes(), source.read_bytes())

            third = self.run_cmd(
                sys.executable,
                str(SCRIPT),
                "resume-copy-fixture",
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--receipt",
                str(receipt3),
                "--expected-sha256",
                expected_sha,
            )
            third_receipt = json.loads(receipt3.read_text(encoding="utf-8"))
            self.assertEqual(third_receipt["bytes_transferred_this_attempt"], 0)
            self.assertEqual(third_receipt["resume_offset"], source.stat().st_size)
            self.assertEqual(third_receipt["sha256"], expected_sha)

    def test_corrupt_partial_prefix_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            source = temp / "source.bin"
            destination = temp / "destination.bin"
            receipt = temp / "receipt.json"
            source.write_bytes(b"correct-source")
            destination.write_bytes(b"wrong")
            output = self.run_cmd(
                sys.executable,
                str(SCRIPT),
                "resume-copy-fixture",
                "--source",
                str(source),
                "--destination",
                str(destination),
                "--receipt",
                str(receipt),
                expected=2,
            )
            self.assertIn("result=TERMINAL_FAILURE", output)
            self.assertIn("partial_prefix_mismatch", output)


if __name__ == "__main__":
    unittest.main()
