from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/gold_s01_pre_render_v1.py"
spec = importlib.util.spec_from_file_location("gold_s01_pre_render_v1", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class GoldS01PreRenderContractTest(unittest.TestCase):
    def manifest(self):
        h1 = "1" * 40
        h = "2" * 64
        value = {key: h for key in module.REQUIRED_MANIFEST_KEYS}
        value.update({
            "schema_version": "gold_s01_two_minute_pre_render_input.v1",
            "oc_head": module.EXPECTED["oc_head"],
            "oc_blob": module.EXPECTED["oc_blob"],
            "source_repo": "TheGor-365/ai-course-source-library",
            "source_branch": "worker/source",
            "source_head": h1,
            "source_receipt_path": "receipts/source.json",
            "production_repo": "TheGor-365/ai-course-production-system",
            "production_branch": "worker/production",
            "production_head": h1,
            "production_receipt_path": "receipts/production.json",
            "compiler_output_dir": "compiled",
            "component_evidence_path": "evidence/component.json",
            "caption_input_receipt_path": "inputs/caption_input_receipt.json",
            "A3483_release": "gold-s01-a3483-input-v1",
            "A3483_sha": module.EXPECTED["a3483_sha"],
            "accepted_timing_sha": module.EXPECTED["accepted_timing_sha"],
            "caption_json_sha": module.EXPECTED["caption_json_sha"],
            "caption_artifact_id": 123,
            "two_minute_render_authorized": False,
            "full_render_authorized": False,
            "qualifying_media_run_started": False,
            "provisional_field_count": 0,
            "no_fake_green": True,
        })
        return value

    def test_exact_manifest_passes(self):
        self.assertEqual([], module.validate_manifest(self.manifest()))

    def test_provisional_value_fails(self):
        value = self.manifest()
        value["source_branch"] = "UNRESOLVED"
        self.assertIn("PROVISIONAL_OR_UNRESOLVED_VALUE", module.validate_manifest(value))

    def test_render_authorization_fails_closed(self):
        value = self.manifest()
        value["two_minute_render_authorized"] = True
        self.assertIn("TWO_MINUTE_RENDER_AUTHORIZED", module.validate_manifest(value))

    def test_vtt_monotonicity_and_count(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.vtt"
            cues = ["WEBVTT", ""]
            for index in range(13):
                start = index * 1000
                end = start + 900
                cues.extend([
                    str(index + 1),
                    f"00:00:{start // 1000:02d}.{start % 1000:03d} --> 00:00:{end // 1000:02d}.{end % 1000:03d}",
                    f"caption {index}",
                    "",
                ])
            path.write_text("\n".join(cues), encoding="utf-8")
            self.assertEqual(13, module.validate_vtt(path)["cue_count"])


if __name__ == "__main__":
    unittest.main()
