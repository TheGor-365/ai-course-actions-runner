import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gold_s01_visual_v2_gate import (
    EXPECTED_FINGERPRINT,
    EXPECTED_NO_RENDER,
    EXPECTED_PACKAGE,
    EXPECTED_REQUEST,
    EXPECTED_RUNTIME_HEAD,
    EXPECTED_SHA,
    EXPECTED_TESTS,
    GateError,
    last_json,
    require,
)


class GoldS01VisualV2GateTests(unittest.TestCase):
    def good(self):
        return {
            "status": "PASS_GOLD_S01_VISUAL_V2_NO_RENDER",
            "test_count": EXPECTED_TESTS,
            "semantic_units": 13,
            "shot_ir_count": 26,
            "scene_ir_count": 26,
            "assets_materialized": 18,
            "unresolved_assets": 0,
            "visual_runtime_head": EXPECTED_RUNTIME_HEAD,
            "no_render_manifest_sha256": EXPECTED_NO_RENDER,
            "visual_input_fingerprint": EXPECTED_FINGERPRINT,
            "package_manifest_sha256": EXPECTED_PACKAGE,
            "private_render_request_status": "READY_BLOCKED_ONLY_BY_ACCEPTED_TIMING",
            "timing_bound": False,
            "caption_binding_complete": False,
            "package_rebuild_stable": True,
            "final_render_authorized": False,
            "no_fake_green": True,
        }

    def test_fixed_exact_identities(self):
        self.assertEqual(40, len(EXPECTED_SHA))
        self.assertEqual(40, len(EXPECTED_RUNTIME_HEAD))
        self.assertEqual(42, EXPECTED_TESTS)
        for value in (EXPECTED_NO_RENDER, EXPECTED_FINGERPRINT, EXPECTED_PACKAGE, EXPECTED_REQUEST):
            self.assertEqual(64, len(value))

    def test_expected_summary_passes(self):
        good = self.good()
        require(good, good, "NO_RENDER")

    def test_hash_drift_fails(self):
        expected = self.good()
        observed = dict(expected)
        observed["no_render_manifest_sha256"] = "0" * 64
        with self.assertRaises(GateError):
            require(observed, expected, "NO_RENDER")

    def test_green_promotion_fails(self):
        expected = self.good()
        observed = dict(expected)
        observed["final_render_authorized"] = True
        with self.assertRaises(GateError):
            require(observed, expected, "NO_RENDER")

    def test_last_json_uses_final_object(self):
        self.assertEqual({"x": 1}, last_json("diagnostic\n" + json.dumps({"x": 1})))


if __name__ == "__main__":
    unittest.main()
