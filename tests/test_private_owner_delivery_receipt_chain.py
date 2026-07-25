from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

CORE_SPEC = importlib.util.spec_from_file_location(
    "private_owner_delivery_v1", SCRIPTS / "private_owner_delivery_v1.py"
)
CORE = importlib.util.module_from_spec(CORE_SPEC)
assert CORE_SPEC.loader is not None
CORE_SPEC.loader.exec_module(CORE)
sys.modules["private_owner_delivery_v1"] = CORE

WRAPPER_SPEC = importlib.util.spec_from_file_location(
    "run_private_owner_delivery_exact_v1",
    SCRIPTS / "run_private_owner_delivery_exact_v1.py",
)
WRAPPER = importlib.util.module_from_spec(WRAPPER_SPEC)
assert WRAPPER_SPEC.loader is not None
WRAPPER_SPEC.loader.exec_module(WRAPPER)


class ReceiptChainIntegrityTest(unittest.TestCase):
    def test_restore_references_final_registration_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            private_root = Path(temp) / "private"
            receipt_dir = Path(temp) / "receipts"
            request = {
                "channel_id": "owner-test-channel",
                "package_id": "M1_L01_S01_RU",
            }
            registration = {
                "schema_version": "PrivateArtifactRegistrationReceipt_v1",
                "request_id": "request-v1",
                "artifacts": [
                    {
                        "artifact_id": "artifact-1",
                        "artifact_type": "contact_sheet",
                        "sha256": "a" * 64,
                        "size_bytes": 123,
                        "restore_status": "PASS",
                    }
                ],
                "receipt_hash": "",
            }
            registration["receipt_hash"] = CORE.canonical_hash(
                registration, omit={"receipt_hash"}
            )
            restore = {
                "schema_version": "PrivateArtifactRestoreReceipt_v1",
                "request_id": "request-v1",
                "registration_receipt_hash": "0" * 64,
                "restore_status": "PASS",
                "receipt_hash": "0" * 64,
            }
            manifest = {
                "registration_receipt_hash": "0" * 64,
                "restore_receipt_hash": "0" * 64,
            }

            final_registration, final_restore, final_manifest = (
                WRAPPER.finalize_receipt_chain(
                    request,
                    private_root,
                    receipt_dir,
                    registration,
                    restore,
                    manifest,
                )
            )

            self.assertEqual(
                final_restore["registration_receipt_hash"],
                final_registration["receipt_hash"],
            )
            self.assertEqual(
                final_manifest["registration_receipt_hash"],
                final_registration["receipt_hash"],
            )
            self.assertEqual(
                final_manifest["restore_receipt_hash"],
                final_restore["receipt_hash"],
            )
            self.assertEqual(
                final_restore["receipt_hash"],
                CORE.canonical_hash(final_restore, omit={"receipt_hash"}),
            )
            self.assertTrue(
                (receipt_dir / "private_artifact_restore_receipt_v1.json").is_file()
            )
            self.assertTrue(
                (receipt_dir / "owner_delivery_manifest_for_git_v1.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
