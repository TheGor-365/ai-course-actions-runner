from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "canonical_gold_s01_minute_proofs_v2.py"
SPEC = importlib.util.spec_from_file_location("minute_proofs", MODULE_PATH)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class CanonicalMinuteProofsV2Test(unittest.TestCase):
    def test_provisional_manifest_is_blocked(self) -> None:
        data = json.loads(
            (Path(__file__).resolve().parents[1] / "config" / "canonical_gold_s01_exact_inputs_v2.json").read_text()
        )
        with self.assertRaisesRegex(M.ProofError, "UPSTREAM_INPUTS_PROVISIONAL"):
            M.validate_exact_manifest(data)

    def test_pilot_b_scoring_prefers_effects_then_count_then_earliest(self) -> None:
        events = [
            {"start_ms": 0, "end_ms": 1000, "effect": "code_typewriter"},
            {"start_ms": 10000, "end_ms": 11000, "effect": "operator_pulse"},
            {"start_ms": 20000, "end_ms": 21000, "effect": "token_glow"},
            {"start_ms": 70000, "end_ms": 71000, "effect": "line_focus"},
            {"start_ms": 80000, "end_ms": 81000, "effect": "execution_path"},
        ]
        self.assertGreater(M.score_window(events, 0), M.score_window(events, 20000))

    def test_vtt_parser_rejects_non_webvtt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.srt"
            path.write_text("1\n00:00:00,000 --> 00:00:01,000\nDraft\n")
            with self.assertRaisesRegex(M.ProofError, "ACCEPTED_CAPTION_VTT_INVALID"):
                M.parse_vtt(path)

    def test_artifact_sanitizer_rejects_duplicate_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.mp4").write_bytes(b"a")
            (root / "b.mp4").write_bytes(b"b")
            args = type("Args", (), {"artifact_dir": str(root)})
            with self.assertRaisesRegex(M.ProofError, "CANONICAL_MP4_COUNT_INVALID"):
                M.sanitize_artifact(args)


if __name__ == "__main__":
    unittest.main()
