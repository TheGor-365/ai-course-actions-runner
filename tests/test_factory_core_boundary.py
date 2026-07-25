import copy, importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("factory_core_boundary",ROOT/"scripts/validate_factory_core_boundary.py")
MODULE=importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(MODULE)

class FactoryCoreBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.receipt=json.loads((ROOT/"fixtures/factory_core/s01_day3_private_executor_receipt.json").read_text())
    def rehash(self,value):
        value["receipt_hash"]=MODULE.canonical_hash({k:v for k,v in value.items() if k!="receipt_hash"})
        return value
    def test_fixture_receipt_is_compatible(self): MODULE.validate_receipt(self.receipt)
    def test_tamper_is_rejected_by_hash(self):
        broken=copy.deepcopy(self.receipt); broken["executor_version"]="tampered"
        with self.assertRaisesRegex(MODULE.ValidationError,"receipt_hash_mismatch"): MODULE.validate_receipt(broken)
    def test_fixture_cannot_claim_real_media(self):
        broken=copy.deepcopy(self.receipt); broken["media_executed"]=True; self.rehash(broken)
        with self.assertRaisesRegex(MODULE.ValidationError,"fixture_truth_boundary"): MODULE.validate_receipt(broken)
    def test_raw_private_path_is_rejected(self):
        broken=copy.deepcopy(self.receipt); broken["artifacts"][0]["private_pointer_or_repository_path"]="/home/gor/private/file.mp4"; self.rehash(broken)
        with self.assertRaisesRegex(MODULE.ValidationError,"artifact_pointer"): MODULE.validate_receipt(broken)
    def test_success_requires_visual_master_and_preview(self):
        broken=copy.deepcopy(self.receipt); broken["artifacts"]=broken["artifacts"][:1]; self.rehash(broken)
        with self.assertRaisesRegex(MODULE.ValidationError,"success_artifacts"): MODULE.validate_receipt(broken)
    def test_duplicate_artifact_type_rejected(self):
        broken=copy.deepcopy(self.receipt); broken["artifacts"][1]["artifact_type"]="visual_master"; self.rehash(broken)
        with self.assertRaisesRegex(MODULE.ValidationError,"artifact_type"): MODULE.validate_receipt(broken)

if __name__=="__main__": unittest.main()
