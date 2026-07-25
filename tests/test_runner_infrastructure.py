from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RunnerInfrastructureTests(unittest.TestCase):
    maxDiff = None

    def run_cmd(self, *args: str, cwd: Path | None = None, expected: int = 0) -> subprocess.CompletedProcess:
        result = subprocess.run(
            list(args), cwd=cwd or ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
        )
        self.assertEqual(result.returncode, expected, result.stdout)
        return result

    def make_private_repo(self, temp: Path) -> Path:
        repo = temp / "private"
        repo.mkdir()
        self.run_cmd("git", "init", "-q", cwd=repo)
        self.run_cmd("git", "config", "user.email", "fixture@example.invalid", cwd=repo)
        self.run_cmd("git", "config", "user.name", "Fixture", cwd=repo)
        (repo / "00_control").mkdir()
        (repo / "00_control/FACTORY_5_DAY_LAUNCH_PLAN_v01.md").write_text(
            "FACTORY_ID=AI_COURSE_FACTORY\n"
            "STATUS=ACTIVE_LAUNCH_SPRINT\n"
            "NO_FAKE_GREEN=true\n"
            "RUNNER_REPO=TheGor-365/ai-course-actions-runner\n",
            encoding="utf-8",
        )
        (repo / "00_control/FACTORY_OPERATION_CENTER.md").write_text(
            "FACTORY_ID=AI_COURSE_FACTORY\n"
            "NO_FAKE_GREEN=true\n"
            "PUBLIC_RUNNER_MEDIA=false\n"
            "PRIVATE_EXECUTOR_REQUIRED=true\n",
            encoding="utf-8",
        )
        self.run_cmd("git", "add", ".", cwd=repo)
        self.run_cmd("git", "commit", "-q", "-m", "fixture", cwd=repo)
        return repo

    def test_contract_self_validator(self) -> None:
        out = self.run_cmd(sys.executable, "scripts/runner_infrastructure_v1.py", "validate-contract").stdout
        self.assertIn("result=PASS", out)
        self.assertIn("manifest_gate_count=6", out)

    def test_launch_control_plane_gate_positive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_private_repo(Path(td))
            out = self.run_cmd(
                "bash", str(ROOT / "scripts/run_manifest_gate.sh"),
                "FACTORY_LAUNCH_CONTROL_PLANE_GATE", str(repo),
                "TheGor-365/ai-course-production-system",
                cwd=ROOT,
            ).stdout
            self.assertIn("result=PASS", out)
            self.assertIn("control_file_count=2", out)
            self.assertIn("private_content_public_exposure=false", out)
            self.assertIn("artifacts_created=false", out)
            self.assertNotIn("RUNNER_REPO=", out)

    def test_unknown_gate_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_private_repo(Path(td))
            out = self.run_cmd(
                "bash", str(ROOT / "scripts/run_manifest_gate.sh"),
                "ARBITRARY_SHELL", str(repo),
                "TheGor-365/ai-course-production-system",
                cwd=ROOT, expected=2,
            ).stdout
            self.assertIn("gate_manifest_rejected", out)

    def test_gate_repo_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = self.make_private_repo(Path(td))
            out = self.run_cmd(
                "bash", str(ROOT / "scripts/run_manifest_gate.sh"),
                "FACTORY_LAUNCH_CONTROL_PLANE_GATE", str(repo),
                "TheGor-365/ai-course-source-library",
                cwd=ROOT, expected=2,
            ).stdout
            self.assertIn("gate_manifest_rejected", out)

    def test_private_executor_retry_resume_restore_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            state_dir = temp / "state"
            artifact_dir = temp / "artifacts"
            receipt1 = temp / "receipt1.json"
            receipt2 = temp / "receipt2.json"
            receipt3 = temp / "receipt3.json"
            req1 = temp / "request1.json"
            req1_data = {
                "schema_version":"1.0","request_id":"fixture-request-001-attempt-1",
                "package_request_id":"fixture-package-001","station_id":"fixture-artifact",
                "attempt_id":"attempt-1",
                "executor_class":"locked_private_Linux_host_or_self_hosted_private_runner",
                "input_manifest_pointer":"private-manifest://fixture/package-001",
                "input_hash":"a"*64,"command_profile_id":"FIXTURE_ARTIFACT_V1",
                "runtime_lock_id":"fixture-runtime-v1",
                "resource_limits":{"cpu_count":1,"memory_mb":128,"disk_mb":16},
                "timeout_seconds":10,"output_artifact_types":["fixture_text"],
                "idempotency_key":"fixture-package-001:fixture-artifact:v1",
                "resume_token_optional":None,"cleanup_policy":"fixture_cleanup_v1"
            }
            req1.write_text(json.dumps(req1_data), encoding="utf-8")

            first = self.run_cmd(
                sys.executable, "scripts/runner_infrastructure_v1.py", "execute-fixture",
                "--request", str(req1),
                "--state-dir", str(state_dir),
                "--artifact-dir", str(artifact_dir),
                "--receipt", str(receipt1),
                "--inject-failure-once",
                expected=75,
            )
            self.assertIn("result=RETRYABLE_FAILURE", first.stdout)
            failure = json.loads(receipt1.read_text(encoding="utf-8"))
            token = failure["resume_token_optional"]
            self.assertTrue(token)

            req2_data = dict(req1_data); req2_data.update({"request_id":"fixture-request-001-attempt-2","attempt_id":"attempt-2"})
            req2_data["resume_token_optional"] = token
            req2 = temp / "request2.json"
            req2.write_text(json.dumps(req2_data), encoding="utf-8")

            second = self.run_cmd(
                sys.executable, "scripts/runner_infrastructure_v1.py", "execute-fixture",
                "--request", str(req2),
                "--state-dir", str(state_dir),
                "--artifact-dir", str(artifact_dir),
                "--receipt", str(receipt2),
                "--inject-failure-once",
            )
            self.assertIn("result=PASS", second.stdout)
            self.assertNotIn("private-artifact://", second.stdout)
            passed = json.loads(receipt2.read_text(encoding="utf-8"))
            artifact = passed["output_artifacts"][0]
            self.assertEqual(artifact["restore_status"], "PASS")
            self.assertEqual(passed["sanitized_metrics"]["prepare_count"], 1)
            self.assertEqual(passed["sanitized_metrics"]["materialize_count"], 1)
            self.assertEqual(passed["sanitized_metrics"]["backup_restore_count"], 1)

            third = self.run_cmd(
                sys.executable, "scripts/runner_infrastructure_v1.py", "execute-fixture",
                "--request", str(req2),
                "--state-dir", str(state_dir),
                "--artifact-dir", str(artifact_dir),
                "--receipt", str(receipt3),
            )
            replay = json.loads(receipt3.read_text(encoding="utf-8"))
            self.assertEqual(replay["output_artifacts"][0]["sha256"], artifact["sha256"])
            self.assertEqual(replay["sanitized_metrics"]["prepare_count"], 1)
            self.assertEqual(replay["sanitized_metrics"]["materialize_count"], 1)
            self.assertEqual(replay["sanitized_metrics"]["backup_restore_count"], 1)

    def test_invalid_resume_token_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            req1 = temp / "request1.json"
            req1_data = {
                "schema_version":"1.0","request_id":"fixture-request-001-attempt-1",
                "package_request_id":"fixture-package-001","station_id":"fixture-artifact",
                "attempt_id":"attempt-1",
                "executor_class":"locked_private_Linux_host_or_self_hosted_private_runner",
                "input_manifest_pointer":"private-manifest://fixture/package-001",
                "input_hash":"a"*64,"command_profile_id":"FIXTURE_ARTIFACT_V1",
                "runtime_lock_id":"fixture-runtime-v1",
                "resource_limits":{"cpu_count":1,"memory_mb":128,"disk_mb":16},
                "timeout_seconds":10,"output_artifact_types":["fixture_text"],
                "idempotency_key":"fixture-package-001:fixture-artifact:v1",
                "resume_token_optional":None,"cleanup_policy":"fixture_cleanup_v1"
            }
            req1.write_text(json.dumps(req1_data), encoding="utf-8")
            state_dir = temp / "state"
            artifact_dir = temp / "artifacts"
            self.run_cmd(
                sys.executable, "scripts/runner_infrastructure_v1.py", "execute-fixture",
                "--request", str(req1),
                "--state-dir", str(state_dir),
                "--artifact-dir", str(artifact_dir),
                "--receipt", str(temp / "failure.json"),
                "--inject-failure-once", expected=75,
            )
            req2 = dict(req1_data)
            req2.update({"request_id":"fixture-request-001-attempt-2","attempt_id":"attempt-2","resume_token_optional":"wrong-token"})
            req2_path = temp / "wrong.json"
            req2_path.write_text(json.dumps(req2), encoding="utf-8")
            out = self.run_cmd(
                sys.executable, "scripts/runner_infrastructure_v1.py", "execute-fixture",
                "--request", str(req2_path),
                "--state-dir", str(state_dir),
                "--artifact-dir", str(artifact_dir),
                "--receipt", str(temp / "wrong-receipt.json"),
                expected=2,
            ).stdout
            self.assertIn("result=TERMINAL_FAILURE", out)
            self.assertIn("private_content_public_exposure=false", out)


if __name__ == "__main__":
    unittest.main()
