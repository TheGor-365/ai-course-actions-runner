from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from scripts.gold_s01_canonical_pre_render_v2 import (
    CANONICAL_WORKFLOW,
    EVENT_PROBES,
    EXPECTED_ACCEPTED_DURATION_MS,
    REQUIRED_EVIDENCE_FRAMES,
    REQUIRED_QC,
    caption_blocks,
    scan_workflow_authority,
    verify_captions,
    verify_component_receipt,
    verify_manifest_dict,
)

H40 = "a" * 40
H64 = "b" * 64
CAPTION_ARTIFACT_ID = 42


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


def timestamp(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def write_fixture(root: Path, *, key: str = "caption_blocks", count: int = 13, final_end: int = EXPECTED_ACCEPTED_DURATION_MS) -> argparse.Namespace:
    blocks = []
    for index in range(count):
        start = index * 1000
        end = final_end if index == count - 1 else start + 900
        blocks.append({
            "caption_block_id": f"S01-CAP-{index + 1:03d}",
            "start_ms": start,
            "end_ms": end,
            "text": f"caption {index + 1}",
        })
    caption = {key: blocks}
    timing = {"audio_duration_ms": EXPECTED_ACCEPTED_DURATION_MS, "final_ru_captions": deepcopy(blocks)}
    vtt = ["WEBVTT", ""]
    for item in blocks:
        vtt.extend([
            item["caption_block_id"],
            f"{timestamp(item['start_ms'])} --> {timestamp(item['end_ms'])}",
            item["text"],
            "",
        ])
    files = {
        "s01_ru_accepted_timing_contract_v01.json": json.dumps(timing, sort_keys=True).encode(),
        "s01_ru_final_captions_v01.json": json.dumps(caption, sort_keys=True).encode(),
        "s01_ru_final_captions_v01.vtt": "\n".join(vtt).encode(),
    }
    timing_sha = hashlib.sha256(files["s01_ru_accepted_timing_contract_v01.json"]).hexdigest()
    json_sha = hashlib.sha256(files["s01_ru_final_captions_v01.json"]).hexdigest()
    vtt_sha = hashlib.sha256(files["s01_ru_final_captions_v01.vtt"]).hexdigest()
    recovery = {
        "accepted_audio_execution_head": H40,
        "accepted_timing_sha256": timing_sha,
        "audio_duration_ms": EXPECTED_ACCEPTED_DURATION_MS,
        "caption_json_sha256": json_sha,
        "caption_vtt_sha256": vtt_sha,
        "editorial_mutation_performed": False,
        "final_caption_end_ms": EXPECTED_ACCEPTED_DURATION_MS,
        "json_vtt_timing_identity": True,
        "regeneration_performed": False,
        "segmentation_mutated": False,
        "timing_mutation_performed": False,
    }
    files["caption_recovery_receipt.json"] = json.dumps(recovery, sort_keys=True).encode()
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    (root / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(raw).hexdigest()}  {name}\n" for name, raw in files.items()),
        encoding="utf-8",
    )
    return argparse.Namespace(
        root=str(root),
        accepted_audio_head=H40,
        timing_sha256=timing_sha,
        caption_json_sha256=json_sha,
        caption_vtt_sha256=vtt_sha,
        receipt=None,
    )


def inventory() -> dict:
    return {
        "schema_version": "canonical_gold_s01_workflow_inventory.v3",
        "repository": "TheGor-365/ai-course-actions-runner",
        "observed_predecessor_pr": 22,
        "observed_predecessor_head": "8f9ae635209021bf09a1f9dc17b40aacc391af0f",
        "successor_work_order": "RWO-GOLD-S01-RUNNER-CAPTION-AUTHORITY-REPAIR-001",
        "successor_issue": "production#382",
        "successor_branch": "worker/m1-l01-s01-runner-release-readiness-v1",
        "canonical_workflow": CANONICAL_WORKFLOW,
        "exact_live_head_verified_at_runtime": True,
        "self_referential_containing_commit_forbidden": True,
        "inventory": [],
    }


def frame_record(frame: int) -> dict:
    digest = hashlib.sha256(str(frame).encode()).hexdigest()
    return {
        "frame": frame,
        "composition_id": "GoldS01PremiumFirst120s",
        "production_runtime_head": "c" * 40,
        "frame_sha256": digest,
        "standard_deviation": 0.1,
        "generic_asset_grid_count": 0,
        "primary_focus_bounds": {"x": 1, "y": 2, "width": 3, "height": 4},
        "caption_bounds": {"x": 5, "y": 6, "width": 7, "height": 8},
        "internal_id_leak": False,
        "debug_metadata_leak": False,
        "camera_preset_id": "camera",
        "lens_profile_id": "lens",
        "lighting_rig_id": "light",
        "material_profile_ids": ["material"],
        "texture_profile_ids": ["texture"],
        "ambient_life_ids": ["ambient"],
        "caption_active": False,
        "event_ids": [],
        "asset_ids": ["asset"],
    }


def valid_component() -> dict:
    frames = [frame_record(frame) for frame in REQUIRED_EVIDENCE_FRAMES]
    by_frame = {frame["frame"]: frame for frame in frames}
    for event_id, probe in EVENT_PROBES.items():
        peak = by_frame[probe["peak"]]
        peak.update({
            "event_ids": [event_id],
            "handler_id": f"handler-{event_id}",
            "target_object_id": f"target-{event_id}",
            "target_property": "opacity",
            "semantic_anchor": f"anchor-{event_id}",
            "property_before": 0,
            "property_after": 1,
            "telemetry_complete": True,
            "frame_hashes": {
                position: by_frame[frame_number]["frame_sha256"]
                for position, frame_number in probe.items()
            },
        })
    return {
        "schema_version": "gold_s01_component_evidence.v3",
        "runner_head": H40,
        "caption_artifact_id": CAPTION_ARTIFACT_ID,
        "frames": frames,
        "qc": {key: "PASS" for key in REQUIRED_QC},
        "media_render_started": False,
        "no_fake_green": True,
    }


def verify_payload(payload: dict, *, expected_caption_artifact_id: int = CAPTION_ARTIFACT_ID) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "component.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        args = argparse.Namespace(
            receipt_path=str(path),
            expected_runner_head=H40,
            expected_caption_artifact_id=expected_caption_artifact_id,
            output=None,
        )
        return verify_component_receipt(args)


class CaptionTests(unittest.TestCase):
    def test_canonical_caption_blocks_pass(self) -> None:
        self.assertEqual([{"x": 1}], caption_blocks({"caption_blocks": [{"x": 1}]}))

    def test_exact_caption_authority_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_captions(write_fixture(Path(tmp)))
            self.assertEqual(EXPECTED_ACCEPTED_DURATION_MS, result["accepted_duration_ms"])

    def test_hardcoded_900000_ceiling_absent(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts/gold_s01_canonical_pre_render_v2.py").read_text()
        self.assertIsNone(re.search(r"(?<![A-Za-z_])900_?000(?![A-Za-z_])", source))


class WorkflowTests(unittest.TestCase):
    def test_canonical_single_workflow_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "canonical-gold-s01-minute-proofs.yml").write_text(
                "name: Canonical Gold S01\non:\n  workflow_dispatch:\njobs:\n  static:\n    runs-on: ubuntu-latest\n",
                encoding="utf-8",
            )
            (root / "docs").mkdir()
            inventory_path = root / "docs/inventory.json"
            inventory_path.write_text(json.dumps(inventory()), encoding="utf-8")
            result = scan_workflow_authority(workflows, inventory_path)
            self.assertTrue(result["one_canonical_gold_s01_workflow"])


class ManifestTests(unittest.TestCase):
    def test_split_compile_runtime_heads_are_valid(self) -> None:
        result = verify_manifest_dict(manifest())
        self.assertNotEqual(result["production_compile_head"], result["production_runtime_head"])


class ComponentReceiptV3Tests(unittest.TestCase):
    def test_v2_receipt_rejected(self) -> None:
        payload = valid_component(); payload["schema_version"] = "gold_s01_component_evidence.v2"
        with self.assertRaisesRegex(SystemExit, "COMPONENT_RECEIPT_SCHEMA_MISMATCH"):
            verify_payload(payload)

    def test_27_frame_receipt_rejected(self) -> None:
        payload = valid_component(); payload["frames"].pop()
        with self.assertRaisesRegex(SystemExit, "COMPONENT_FRAME_COUNT_MISMATCH"):
            verify_payload(payload)

    def test_missing_frame_44_rejected(self) -> None:
        payload = valid_component(); payload["frames"] = [f for f in payload["frames"] if f["frame"] != 44]
        with self.assertRaises(SystemExit):
            verify_payload(payload)

    def test_missing_no_internal_debug_ids_rejected(self) -> None:
        payload = valid_component(); payload["qc"].pop("NO_INTERNAL_DEBUG_IDS")
        with self.assertRaisesRegex(SystemExit, "COMPONENT_QC_KEY_SET_MISMATCH"):
            verify_payload(payload)

    def test_missing_runner_head_rejected(self) -> None:
        payload = valid_component(); payload.pop("runner_head")
        with self.assertRaisesRegex(SystemExit, "HEAD_SHA_REQUIRED"):
            verify_payload(payload)

    def test_wrong_caption_artifact_id_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "COMPONENT_CAPTION_ARTIFACT_ID_MISMATCH"):
            verify_payload(valid_component(), expected_caption_artifact_id=99)

    def test_missing_peak_telemetry_rejected(self) -> None:
        payload = valid_component()
        peak = next(frame for frame in payload["frames"] if frame["frame"] == 44)
        peak.pop("handler_id")
        with self.assertRaisesRegex(SystemExit, "COMPONENT_PEAK_TELEMETRY_FIELD_MISSING"):
            verify_payload(payload)

    def test_blank_boundary_rejected(self) -> None:
        payload = valid_component()
        frame_zero = next(frame for frame in payload["frames"] if frame["frame"] == 0)
        frame_zero["standard_deviation"] = 0.005
        with self.assertRaisesRegex(SystemExit, "COMPONENT_BLANK_FRAME_DETECTED"):
            verify_payload(payload)

    def test_valid_v3_28_frame_receipt_passes(self) -> None:
        result = verify_payload(valid_component())
        self.assertEqual(28, result["frame_count"])
        self.assertEqual(10, result["qc_pass_count"])
        self.assertEqual("PASS", result["result"])


if __name__ == "__main__":
    unittest.main()
