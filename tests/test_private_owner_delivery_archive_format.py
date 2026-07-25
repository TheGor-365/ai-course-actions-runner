from __future__ import annotations

import importlib.util
import sys
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


class PrivateOwnerDeliveryArchiveFormatTest(unittest.TestCase):
    def test_visual_archive_keeps_zip_extension(self):
        self.assertEqual(
            WRAPPER.exact_artifact_filename(
                "still_archive", Path("full_resolution_stills_v1.zip")
            ),
            "full_resolution_stills_v1.zip",
        )

    def test_non_zip_still_archive_is_rejected(self):
        with self.assertRaisesRegex(CORE.DeliveryError, "STILL_ARCHIVE_FORMAT_MISMATCH"):
            WRAPPER.exact_artifact_filename(
                "still_archive", Path("stills_full_resolution_v1.tar")
            )

    def test_other_artifact_names_remain_stable(self):
        self.assertEqual(
            WRAPPER.exact_artifact_filename(
                "contact_sheet", Path("contact_sheet_5x4_v1.png")
            ),
            "contact_sheet_5x4_v1.png",
        )


if __name__ == "__main__":
    unittest.main()
