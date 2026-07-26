import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gold_s01_visual_v2_gate import (
    EXPECTED_BASE_FINGERPRINT,
    EXPECTED_BRANCH,
    EXPECTED_NO_RENDER,
    EXPECTED_PRODUCTION_FINGERPRINT,
    EXPECTED_PRODUCTION_MANIFEST,
    EXPECTED_PRODUCTION_TESTS,
    EXPECTED_SHA,
    GateError,
    last_json,
    require,
)

class GoldS01ProductionGateTests(unittest.TestCase):
    def good(self):
        return {
            "status": "PASS_GOLD_S01_PRODUCTION_COMPOSITION_NO_RENDER",
            "test_count": EXPECTED_PRODUCTION_TESTS,
            "production_input_fingerprint": EXPECTED_PRODUCTION_FINGERPRINT,
            "visual_execution_authorized": True,
            "final_render_authorized": True,
            "provisional_fields": 0,
            "no_fake_green": True,
        }

    def test_fixed_exact_identities(self):
        self.assertEqual("repair/gold-s01-production-composition-pilot-v1", EXPECTED_BRANCH)
        self.assertEqual(40, len(EXPECTED_SHA))
        self.assertEqual(17, EXPECTED_PRODUCTION_TESTS)
        for value in (EXPECTED_NO_RENDER, EXPECTED_BASE_FINGERPRINT, EXPECTED_PRODUCTION_MANIFEST, EXPECTED_PRODUCTION_FINGERPRINT):
            self.assertEqual(64, len(value))

    def test_expected_summary_passes(self):
        value = self.good(); require(value, value, "PRODUCTION")

    def test_fingerprint_drift_fails(self):
        expected = self.good(); observed = dict(expected)
        observed["production_input_fingerprint"] = "0" * 64
        with self.assertRaises(GateError): require(observed, expected, "PRODUCTION")

    def test_authorization_regression_fails(self):
        expected = self.good(); observed = dict(expected)
        observed["final_render_authorized"] = False
        with self.assertRaises(GateError): require(observed, expected, "PRODUCTION")

    def test_provisional_regression_fails(self):
        expected = self.good(); observed = dict(expected)
        observed["provisional_fields"] = 1
        with self.assertRaises(GateError): require(observed, expected, "PRODUCTION")

    def test_last_json_uses_final_object(self):
        self.assertEqual({"x": 1}, last_json("diagnostic\n" + json.dumps({"x": 1})))

if __name__ == "__main__":
    unittest.main()
