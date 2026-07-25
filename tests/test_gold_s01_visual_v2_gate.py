import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gold_s01_visual_v2_gate import (
    EXPECTED_BRANCH, EXPECTED_FINGERPRINT, EXPECTED_NO_RENDER, EXPECTED_REPO,
    EXPECTED_SHA, GateError, last_json, validate_args, validate_summary,
)


class GoldS01VisualV2GateTests(unittest.TestCase):
    def good(self):
        return {
            "shot_ir_count": 26, "scene_ir_count": 26, "semantic_units": 13,
            "test_count": 36, "assets_materialized": 18, "unresolved_assets": 0,
            "representative_qc_pack_ready": True, "private_render_request_ready": True,
            "full_visual_master_rendered": False, "human_final_preview_accepted": False,
            "no_render_manifest_sha256": EXPECTED_NO_RENDER,
            "visual_input_fingerprint": EXPECTED_FINGERPRINT,
            "timing_bound": False, "final_render_authorized": False, "no_fake_green": True,
        }

    def test_exact_arguments_pass(self):
        validate_args(EXPECTED_REPO, EXPECTED_BRANCH, EXPECTED_SHA)

    def test_sha_drift_fails(self):
        with self.assertRaises(GateError):
            validate_args(EXPECTED_REPO, EXPECTED_BRANCH, "0" * 40)

    def test_expected_summary_passes(self):
        validate_summary(self.good())

    def test_green_promotion_fails(self):
        value = self.good(); value["final_render_authorized"] = True
        with self.assertRaises(GateError):
            validate_summary(value)

    def test_last_json_uses_final_object(self):
        self.assertEqual({"x": 1}, last_json("diagnostic\n" + json.dumps({"x": 1})))


if __name__ == "__main__":
    unittest.main()
