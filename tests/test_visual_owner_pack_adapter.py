from __future__ import annotations

import importlib.util
import json
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

ADAPTER_SPEC = importlib.util.spec_from_file_location(
    "visual_owner_pack_adapter_v1", SCRIPTS / "visual_owner_pack_adapter_v1.py"
)
ADAPTER = importlib.util.module_from_spec(ADAPTER_SPEC)
assert ADAPTER_SPEC.loader is not None
ADAPTER_SPEC.loader.exec_module(ADAPTER)


class VisualOwnerPackAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.checkout = self.root / "production"
        self.checkout.mkdir()
        self.staging = self.root / "staging"
        self.source_head = "1" * 40
        self.visual_content_head = "2" * 40
        self.runtime_head = "3" * 40
        self.request = {
            "channel_id": "owner-channel-v1",
            "package_id": "M1_L01_S01_RU",
            "authorized_inputs": {
                "source_snapshot_sha": self.source_head,
                "visual_content_head": self.visual_content_head,
                "visual_runtime_head": self.runtime_head,
                "production_sha": self.runtime_head,
            },
        }
        self.items = []
        manifest_items = []
        source = self.root / "source"
        source.mkdir()
        for index in range(17):
            path = source / f"STILL-{index+1:03d}.png"
            path.write_bytes(f"png-{index}".encode())
            item = {
                "filename": path.name,
                "resolved_private_path": str(path),
            }
            self.items.append(item)
            manifest_items.append({"filename": path.name, "private_path": "/not/used"})
        self.manifest = {"review_items": manifest_items}

    def tearDown(self):
        self.tmp.cleanup()

    def fake_builder(
        self,
        runtime_request,
        package_root,
        *,
        source_head,
        visual_content_head,
        delivery_pointer,
        execute,
    ):
        package_root = Path(package_root)
        package_root.mkdir(parents=True)
        files = {
            "contact_sheet_5x4_v1.png": b"contact-sheet",
            "full_resolution_stills_v1.zip": b"archive",
            "owner_review_index_v1.html": b"<html>owner</html>",
            "SHA256SUMS.txt": b"checksums",
            "owner_review_pack_receipt_v1.json": b"{}",
        }
        manifest = {
            "human_visual_qc_green": False,
            "cross_scene_clip": "BLOCKED_UNTIL_ACCEPTED_TIMING",
            "ru_preview": "BLOCKED_UNTIL_ACCEPTED_TIMING",
        }
        (package_root / "owner_review_manifest_v1.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        for name, data in files.items():
            (package_root / name).write_bytes(data)
        return {
            "status": "PRIVATE_OWNER_REVIEW_PACK_CREATED_HUMAN_DECISION_PENDING",
            "still_count": 17,
            "human_visual_qc_green": False,
            "source_head": source_head,
            "visual_content_head": visual_content_head,
            "owner_delivery_pointer": delivery_pointer,
            "contact_sheet_sha256": CORE.sha256_file(package_root / "contact_sheet_5x4_v1.png"),
            "full_resolution_archive_sha256": CORE.sha256_file(package_root / "full_resolution_stills_v1.zip"),
            "manifest_sha256": CORE.sha256_file(package_root / "owner_review_manifest_v1.json"),
            "sha256sums_sha256": CORE.sha256_file(package_root / "SHA256SUMS.txt"),
        }

    def test_exact_visual_builder_outputs_are_selected(self):
        outputs = ADAPTER.assemble_owner_pack(
            self.request,
            self.checkout,
            self.root / "manifest.json",
            self.manifest,
            self.items,
            self.staging,
            builder=self.fake_builder,
        )
        self.assertEqual(set(outputs), {"contact_sheet", "still_archive"})
        self.assertEqual(outputs["contact_sheet"].name, "contact_sheet_5x4_v1.png")
        self.assertEqual(outputs["still_archive"].name, "full_resolution_stills_v1.zip")

    def test_visual_runtime_and_content_heads_fail_closed(self):
        broken = dict(self.request)
        broken["authorized_inputs"] = dict(self.request["authorized_inputs"])
        broken["authorized_inputs"]["visual_runtime_head"] = "4" * 40
        with self.assertRaisesRegex(CORE.DeliveryError, "VISUAL_RUNTIME_HEAD_MISMATCH"):
            ADAPTER.assemble_owner_pack(
                broken,
                self.checkout,
                self.root / "manifest.json",
                self.manifest,
                self.items,
                self.staging,
                builder=self.fake_builder,
            )
        broken = dict(self.request)
        broken["authorized_inputs"] = dict(self.request["authorized_inputs"])
        broken["authorized_inputs"].pop("visual_content_head")
        with self.assertRaisesRegex(CORE.DeliveryError, "VISUAL_CONTENT_HEAD_REQUIRED"):
            ADAPTER.assemble_owner_pack(
                broken,
                self.checkout,
                self.root / "manifest.json",
                self.manifest,
                self.items,
                self.staging,
                builder=self.fake_builder,
            )


if __name__ == "__main__":
    unittest.main()
