from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ContentSemanticsGateTests(unittest.TestCase):
    def run_cmd(
        self,
        *args: str,
        cwd: Path | None = None,
        expected: int = 0,
    ) -> str:
        completed = subprocess.run(
            list(args),
            cwd=cwd or ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(completed.returncode, expected, completed.stdout)
        return completed.stdout

    def init_repo(self, path: Path) -> None:
        path.mkdir()
        self.run_cmd("git", "init", "-q", cwd=path)
        self.run_cmd("git", "config", "user.email", "fixture@example.invalid", cwd=path)
        self.run_cmd("git", "config", "user.name", "Fixture", cwd=path)

    def commit(self, path: Path) -> None:
        self.run_cmd("git", "add", ".", cwd=path)
        self.run_cmd("git", "commit", "-q", "-m", "fixture", cwd=path)

    def test_content_semantics_gate_positive_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "private"
            self.init_repo(repo)
            base = repo / "Module 1/Lesson 1/launch_5d/content_semantics"
            base.mkdir(parents=True)
            canonical = repo / (
                "Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/"
                "02_voiceover"
            )
            canonical.mkdir(parents=True)
            (canonical / "voiceover_segments_ru.json").write_text("{}", encoding="utf-8")

            handoff = {
                "s01_reference_contract": {
                    "semantic_units": 13,
                    "shot_intents": 26,
                    "semantic_slots": 13,
                    "shotir_source_inputs": 26,
                },
                "s02_blind_contract": {
                    "canonical_source_beats": 12,
                    "normalized_factory_shot_intents": 12,
                },
            }
            (base / "HANDOFF_v1.json").write_text(json.dumps(handoff), encoding="utf-8")
            request = {"request": "fixture"}
            (base / "M1-L01-S02_immutable_blind_request_v1.json").write_text(
                json.dumps(request, sort_keys=True), encoding="utf-8"
            )
            for name in (
                "M1-L01-S02_factory_request_v1.json",
                "M1-L01-S02_factory_source_manifest_v1.json",
                "S01_audio_authority_mapping_v1.json",
                "audio_authority_connector_attestation_v1.json",
                "shotir_freeze_reconciliation_v1.json",
                "factory_core_reconciliation_v1.json",
                "connector_preflight_attestation_v1.json",
            ):
                (base / name).write_text("{}", encoding="utf-8")

            no_op = 'print("PASS")\n'
            for name in (
                "validate_content_semantics.py",
                "validate_policy_bindings.py",
                "validate_factory_request_bridge.py",
                "validate_audio_authority_mapping.py",
                "validate_factory_core_reconciliation.py",
                "validate_shotir_freeze_reconciliation.py",
                "validate_ru_caption_source.py",
                "test_validate_content_semantics.py",
                "test_build_content_semantics_handoff_v2.py",
            ):
                (base / name).write_text(no_op, encoding="utf-8")

            (base / "build_content_semantics_handoff_v2.py").write_text(
                "import argparse,json,pathlib\n"
                "p=argparse.ArgumentParser();p.add_argument('--repo-root');p.add_argument('--out-dir');a=p.parse_args()\n"
                "o=pathlib.Path(a.out_dir);o.mkdir(exist_ok=True)\n"
                "pkg={'semantic_units':[{}]*13,'shot_intents':[{}]*26,'semantic_slots':[{}]*13,'shotir_source_inputs':[{}]*26,'production_green_claimed':False}\n"
                "(o/'M1-L01-S01_content_semantics_v1.json').write_text(json.dumps(pkg))\n"
                "src=pathlib.Path('Module 1/Lesson 1/launch_5d/content_semantics/M1-L01-S02_immutable_blind_request_v1.json')\n"
                "(o/src.name).write_bytes(src.read_bytes())\n",
                encoding="utf-8",
            )
            (base / "build_ru_caption_source.py").write_text(
                "import argparse,json,pathlib\n"
                "p=argparse.ArgumentParser();p.add_argument('--repo-root');p.add_argument('--out-dir');a=p.parse_args()\n"
                "o=pathlib.Path(a.out_dir);o.mkdir(exist_ok=True)\n"
                "(o/'M1-L01-S01_ru_caption_source_v1.json').write_text(json.dumps({'caption_blocks':[{}]*13,'production_green_claimed':False}))\n",
                encoding="utf-8",
            )
            self.commit(repo)

            output = self.run_cmd(
                "bash",
                str(ROOT / "scripts/run_manifest_gate.sh"),
                "CONTENT_SEMANTICS_LAUNCH_GATE",
                str(repo),
                "TheGor-365/ai-course-source-library",
            )
            self.assertIn("result=PASS", output)
            self.assertIn("semantic_units=13", output)
            self.assertIn("caption_blocks=13", output)
            self.assertIn("private_content_printed=false", output)
            self.assertIn("artifacts_created=false", output)

    def test_content_semantics_gate_wrong_repo_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "private"
            self.init_repo(repo)
            (repo / "fixture.txt").write_text("fixture", encoding="utf-8")
            self.commit(repo)
            output = self.run_cmd(
                "bash",
                str(ROOT / "scripts/run_manifest_gate.sh"),
                "CONTENT_SEMANTICS_LAUNCH_GATE",
                str(repo),
                "TheGor-365/ai-course-production-system",
                expected=2,
            )
            self.assertIn("gate_manifest_rejected", output)


if __name__ == "__main__":
    unittest.main()
