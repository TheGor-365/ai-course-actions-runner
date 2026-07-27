from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.gold_s01_canonical_pre_render_v2 import (
    REQUIRED_EVIDENCE_FRAMES,
    verify_component_receipt,
    verify_manifest_dict,
)

H40 = "a" * 40
H64 = "b" * 64


def manifest() -> dict:
    return {
        "schema_version": "gold_s01_pre_render_manifest.v2",
        "work_order_id": "RWO-GOLD-PSU-FINAL-EXACT-REPAIR-001",
        "oc_head": H40,
        "oc_blob_sha": H64,
        "source_repository": "TheGor-365/ai-course-source-library",
        "source_branch": "source",
        "source_head": H40,
        "source_exact_run": 1,
        "source_exact_artifact_id": 2,
        "source_exact_artifact_sha256": H64,
        "production_repository": "TheGor-365/ai-course-production-system",
        "production_branch": "production",
        "production_compile_head": H40,
        "production_runtime_head": "c" * 40,
        "compiler_run": 3,
        "compiler_job": 4,
        "compiler_artifact_id": 5,
        "compiler_artifact_sha256": H64,
        "compiler_output_file_hashes": {"receipt.json": H64},
        "quality_repository": "TheGor-365/ai-course-production-system",
        "quality_branch": "quality",
        "quality_evidence_head": "d" * 40,
        "runner_repository": "TheGor-365/ai-course-actions-runner",
        "runner_branch": "runner",
        "runner_workflow_head": "e" * 40,
        "accepted_audio_execution_head": "f" * 40,
        "A3483_sha256": H64,
        "caption_carrier_head": "1" * 40,
        "caption_json_sha256": H64,
        "caption_vtt_sha256": H64,
        "caption_artifact_id": 6,
        "caption_artifact_sha256": H64,
        "component_evidence_artifact_id": 7,
        "component_evidence_artifact_sha256": H64,
        "composition_id": "GoldS01PremiumFirst120s",
        "entrypoint": "src/goldS01VisualV2/PremiumRootV3.tsx",
        "fps": 30,
        "duration_in_frames": 3600,
        "width": 1920,
        "height": 1080,
        "timeline_start_frame": 0,
        "timeline_end_frame_exclusive": 3600,
        "provisional_field_count": 0,
        "media_render_started": False,
        "two_minute_render_authorized": False,
        "full_15_minute_render_authorized": False,
        "no_fake_green": True,
    }


class ManifestTests(unittest.TestCase):
    def test_split_compile_runtime_heads_are_valid(self) -> None:
        result = verify_manifest_dict(manifest())
        self.assertNotEqual(
            result["production_compile_head"],
            result["production_runtime_head"],
        )

    def test_provisional_manifest_is_rejected(self) -> None:
        value = manifest()
        value["provisional_field_count"] = 1
        with self.assertRaises(SystemExit):
            verify_manifest_dict(value)

    def test_manifest_self_reference_is_rejected(self) -> None:
        value = manifest()
        value["manifest_carrier_head"] = H40
        with self.assertRaises(SystemExit):
            verify_manifest_dict(value)

    def test_render_authorization_is_rejected(self) -> None:
        value = manifest()
        value["two_minute_render_authorized"] = True
        with self.assertRaises(SystemExit):
            verify_manifest_dict(value)


class ComponentReceiptTests(unittest.TestCase):
    def test_exact_frame_set_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "component.json"
            payload = {
                "schema_version": "gold_s01_component_evidence.v2",
                "frames": [
                    {
                        "frame": frame,
                        "composition_id": "GoldS01PremiumFirst120s",
                        "production_runtime_head": H40,
                        "frame_sha256": hashlib.sha256(str(frame).encode()).hexdigest(),
                        "generic_asset_grid_count": 0,
                    }
                    for frame in REQUIRED_EVIDENCE_FRAMES
                ],
                "qc": {
                    "FRAME_ZERO_LAYOUT": "PASS",
                    "SCENE_CONTINUITY": "PASS",
                    "PRIMARY_FOCUS_BOUNDS": "PASS",
                    "CAPTION_CLEARANCE": "PASS",
                    "CONTACT_SHADOW_EVIDENCE": "PASS",
                    "DEPTH_LAYER_EVIDENCE": "PASS",
                    "EVENT_TARGET_DELTA": "PASS",
                    "NO_GENERIC_GRID": "PASS",
                    "NO_BLANK_FRAME": "PASS",
                },
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            args = type("Args", (), {
                "receipt_path": str(path),
                "output": None,
            })()
            result = verify_component_receipt(args)
            self.assertEqual(result["frame_count"], 27)


if __name__ == "__main__":
    unittest.main()
