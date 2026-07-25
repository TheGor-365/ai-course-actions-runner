from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("private_owner_delivery", ROOT / "scripts/private_owner_delivery_v1.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def git(*args: str, cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


class PrivateOwnerDeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.checkout = self.root / "production"
        self.checkout.mkdir()
        git("init", "-q", cwd=self.checkout)
        git("config", "user.email", "test@example.invalid", cwd=self.checkout)
        git("config", "user.name", "Test", cwd=self.checkout)
        self.manifest_path = self.checkout / "private/review.json"
        self.manifest_path.parent.mkdir(parents=True)
        private_root = self.root / "private-root"
        still_root = private_root / "M1/L01/S01/ru/A3502/stills_v01"
        still_root.mkdir(parents=True)
        items = []
        for index in range(17):
            filename = f"STILL-{index+1:03d}.png"
            path = still_root / filename
            data = (f"still-{index}" * 20).encode()
            path.write_bytes(data)
            items.append({
                "still_id": f"STILL-{index+1:03d}", "filename": filename,
                "private_path": f"/not/used/{filename}", "frame": index,
                "scene_id": f"scene-{index+1}", "component": "Fixture", "purpose": "test",
                "sha256": MODULE.sha256_file(path), "size_bytes": len(data), "width": 1, "height": 1,
            })
        manifest = {
            "status": "PENDING_EXPLICIT_HUMAN_VISUAL_QC", "machine_qc_green": True,
            "automatic_human_qc_green": False, "short_clip_allowed": False,
            "full_video_allowed": False, "video_allowed": False,
            "artifact_count": 17, "review_items": items,
        }
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        git("add", ".", cwd=self.checkout)
        git("commit", "-qm", "fixture", cwd=self.checkout)
        head = git("rev-parse", "HEAD", cwd=self.checkout)
        blob = git("hash-object", str(self.manifest_path), cwd=self.checkout)
        self.private_root = private_root
        self.request = {
            "schema_version": "PrivateOwnerDeliveryRequest_v1",
            "request_id": "owner-delivery-test-v1", "package_id": "M1_L01_S01_RU",
            "channel_id": "owner-m1-l01-s01-review-v1",
            "profile_id": "OWNER_DELIVERY_EXISTING_STILLS_V1",
            "execution_authorized": True, "authorization_owner": "human-owner",
            "authorized_outputs": ["contact_sheet", "still_archive"],
            "authorized_inputs": {
                "production_repository": "TheGor-365/ai-course-production-system",
                "production_branch": "fixture", "production_sha": head,
                "input_manifest_repository_path": "private/review.json",
                "input_manifest_git_blob_sha": blob,
                "source_repository": "TheGor-365/ai-course-source-library",
                "source_snapshot_branch": "snapshot-v9", "source_snapshot_sha": "1" * 40,
                "visual_runtime_head": "2" * 40, "audio_timing_head": None,
                "accepted_timing_contract_sha256": None, "required_input_count": 17,
            },
            "private_artifact_relative_root": "M1/L01/S01/ru/A3502/stills_v01",
            "idempotency_key": "owner-delivery-test-v1-idempotency",
            "public_workflow_execution_allowed": False,
            "public_artifact_upload_allowed": False,
            "private_content_public_exposure": False, "no_fake_green": True,
        }

    def tearDown(self):
        self.tmp.cleanup()

    def fake_assembler(self, request, checkout, manifest_path, manifest, items, staging):
        staging.mkdir(parents=True, exist_ok=True)
        contact = staging / "contact.png"
        archive = staging / "archive.tar"
        contact.write_bytes(b"contact-sheet-real-private-bytes")
        archive.write_bytes(b"still-archive-real-private-bytes")
        return {"contact_sheet": contact, "still_archive": archive}

    def test_request_and_exact_checkout(self):
        MODULE.validate_request(self.request)
        observed = MODULE.validate_exact_checkout(self.request, self.checkout)
        self.assertEqual(observed, self.manifest_path)

    def test_public_workflow_and_video_scope_fail_closed(self):
        broken = copy.deepcopy(self.request)
        broken["public_workflow_execution_allowed"] = True
        with self.assertRaisesRegex(MODULE.DeliveryError, "PUBLIC_EXECUTION_FORBIDDEN"):
            MODULE.validate_request(broken)
        broken = copy.deepcopy(self.request)
        broken["authorized_outputs"] = ["cross_scene_clip"]
        with self.assertRaisesRegex(MODULE.DeliveryError, "PROFILE_OUTPUT_MISMATCH"):
            MODULE.validate_request(broken)

    def test_registration_restore_and_sanitized_manifest(self):
        receipts = self.root / "receipts"
        registration, restore, manifest = MODULE.execute_request(
            self.request, self.checkout, self.private_root, receipts, assembler=self.fake_assembler,
            clock=lambda: "2026-07-25T00:00:00Z",
        )
        self.assertEqual(registration["artifact_count"], 2)
        self.assertEqual(restore["verified_artifact_count"], 2)
        self.assertEqual({item["restore_status"] for item in registration["artifacts"]}, {"PASS"})
        serialized = json.dumps(manifest)
        self.assertNotIn(str(self.private_root), serialized)
        self.assertNotIn("/home/", serialized)
        self.assertFalse(manifest["automatic_human_qc_green"])
        self.assertTrue((receipts / "owner_delivery_manifest_for_git_v1.json").is_file())

    def test_injected_failure_resume_is_idempotent(self):
        receipts = self.root / "receipts"
        with self.assertRaises(MODULE.RetryableDeliveryError) as caught:
            MODULE.execute_request(
                self.request, self.checkout, self.private_root, receipts,
                inject_failure_after_registration=1, assembler=self.fake_assembler,
            )
        registration, restore, _manifest = MODULE.execute_request(
            self.request, self.checkout, self.private_root, receipts,
            resume_token=caught.exception.resume_token, assembler=self.fake_assembler,
        )
        self.assertEqual(registration["artifact_count"], 2)
        self.assertEqual(restore["restore_status"], "PASS")
        state_files = list((self.private_root / "owner_delivery_state").glob("*.json"))
        state = json.loads(state_files[0].read_text())
        self.assertTrue(state["completed"])
        self.assertGreaterEqual(state["skipped_existing_registrations"], 1)

    def test_tampered_input_and_dirty_checkout_rejected(self):
        still = self.private_root / "M1/L01/S01/ru/A3502/stills_v01/STILL-001.png"
        still.write_bytes(b"tampered")
        manifest = MODULE.load_json(self.manifest_path)
        with self.assertRaisesRegex(MODULE.DeliveryError, "PRIVATE_ARTIFACT_(SIZE|HASH)_MISMATCH"):
            MODULE.validate_still_manifest(self.request, manifest, self.private_root)
        (self.checkout / "dirty.txt").write_text("dirty")
        with self.assertRaisesRegex(MODULE.DeliveryError, "PRIVATE_CHECKOUT_DIRTY"):
            MODULE.validate_exact_checkout(self.request, self.checkout)

    def test_media_profile_requires_accepted_timing_and_exact_sources(self):
        request = copy.deepcopy(self.request)
        request["profile_id"] = "OWNER_DELIVERY_EXISTING_MEDIA_V1"
        request["authorized_outputs"] = ["cross_scene_clip", "RU_preview"]
        with self.assertRaisesRegex(MODULE.DeliveryError, "ACCEPTED_TIMING_REQUIRED"):
            MODULE.validate_request(request)
        request["authorized_inputs"]["audio_timing_head"] = "3" * 40
        request["authorized_inputs"]["accepted_timing_contract_sha256"] = "4" * 64
        request["source_artifacts"] = [
            {"artifact_type": "cross_scene_clip", "relative_path": "media/clip.mp4", "sha256": "5" * 64, "size_bytes": 10},
            {"artifact_type": "RU_preview", "relative_path": "media/preview.mp4", "sha256": "6" * 64, "size_bytes": 20},
        ]
        MODULE.validate_request(request)


if __name__ == "__main__":
    unittest.main()
