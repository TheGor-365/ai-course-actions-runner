from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.gold_s01_canonical_pre_render_v2 import (
    CANONICAL_WORKFLOW,
    EXPECTED_ACCEPTED_DURATION_MS,
    REQUIRED_EVIDENCE_FRAMES,
    caption_blocks,
    scan_workflow_authority,
    verify_captions,
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


def timestamp(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def write_fixture(
    root: Path,
    *,
    key: str = "caption_blocks",
    count: int = 13,
    non_object: bool = False,
    final_end: int = EXPECTED_ACCEPTED_DURATION_MS,
    receipt_audio_duration: int = EXPECTED_ACCEPTED_DURATION_MS,
    receipt_final_end: int = EXPECTED_ACCEPTED_DURATION_MS,
    timing_audio_duration: int = EXPECTED_ACCEPTED_DURATION_MS,
) -> argparse.Namespace:
    blocks: list[object] = []
    for index in range(count):
        start = index * 1000
        end = final_end if index == count - 1 else start + 900
        blocks.append({
            "caption_block_id": f"S01-CAP-{index + 1:03d}",
            "start_ms": start,
            "end_ms": end,
            "text": f"caption {index + 1}",
        })
    if non_object and blocks:
        blocks[0] = "invalid"
    caption = {key: blocks} if key else {"document_id": "missing"}
    timing_blocks = [item.copy() for item in blocks if isinstance(item, dict)]
    timing = {"audio_duration_ms": timing_audio_duration, "final_ru_captions": timing_blocks}
    vtt = ["WEBVTT", ""]
    for item in timing_blocks:
        vtt.extend([
            item["caption_block_id"],
            f"{timestamp(item['start_ms'])} --> {timestamp(item['end_ms'])}",
            item["text"],
            "",
        ])
    recovery = {
        "accepted_audio_execution_head": H40,
        "accepted_timing_sha256": "",
        "audio_duration_ms": receipt_audio_duration,
        "caption_json_sha256": "",
        "caption_vtt_sha256": "",
        "editorial_mutation_performed": False,
        "final_caption_end_ms": receipt_final_end,
        "json_block_count": count,
        "json_vtt_timing_identity": True,
        "regeneration_performed": False,
        "segmentation_mutated": False,
        "timing_mutation_performed": False,
        "vtt_cue_count": count,
    }
    files = {
        "s01_ru_accepted_timing_contract_v01.json": json.dumps(timing, ensure_ascii=False, sort_keys=True).encode(),
        "s01_ru_final_captions_v01.json": json.dumps(caption, ensure_ascii=False, sort_keys=True).encode(),
        "s01_ru_final_captions_v01.vtt": "\n".join(vtt).encode(),
    }
    timing_sha = hashlib.sha256(files["s01_ru_accepted_timing_contract_v01.json"]).hexdigest()
    json_sha = hashlib.sha256(files["s01_ru_final_captions_v01.json"]).hexdigest()
    vtt_sha = hashlib.sha256(files["s01_ru_final_captions_v01.vtt"]).hexdigest()
    recovery.update({"accepted_timing_sha256": timing_sha, "caption_json_sha256": json_sha, "caption_vtt_sha256": vtt_sha})
    files["caption_recovery_receipt.json"] = json.dumps(recovery, ensure_ascii=False, sort_keys=True).encode()
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    sums = "".join(f"{hashlib.sha256(raw).hexdigest()}  {name}\n" for name, raw in files.items())
    (root / "SHA256SUMS").write_text(sums, encoding="utf-8")
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


class CaptionExtractionTests(unittest.TestCase):
    def test_canonical_caption_blocks_pass(self) -> None:
        self.assertEqual([{"x": 1}], caption_blocks({"caption_blocks": [{"x": 1}]}))

    def test_legacy_alias_blocks_pass(self) -> None:
        self.assertEqual([{"x": 1}], caption_blocks({"blocks": [{"x": 1}]}))

    def test_missing_array_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "CAPTION_BLOCK_ARRAY_MISSING"):
            caption_blocks({})

    def test_non_object_block_rejected(self) -> None:
        with self.assertRaisesRegex(SystemExit, "CAPTION_BLOCK_OBJECT_REQUIRED"):
            caption_blocks({"caption_blocks": ["bad"]})

    def test_wrong_block_count_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture(Path(tmp), count=12)
            with self.assertRaisesRegex(SystemExit, "CAPTION_JSON_BLOCK_COUNT_MISMATCH"):
                verify_captions(args)


class CaptionDurationTests(unittest.TestCase):
    def test_exact_authority_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_captions(write_fixture(Path(tmp)))
            self.assertTrue(result["caption_blocks_key_supported"])
            self.assertEqual(908398, result["accepted_duration_ms"])
            self.assertEqual(908398, result["final_caption_end_ms"])
            self.assertTrue(result["json_vtt_timing_identity"])

    def test_hardcoded_900000_ceiling_absent(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "scripts/gold_s01_canonical_pre_render_v2.py").read_text()
        self.assertIsNone(re.search(r"(?<![A-Za-z_])900_?000(?![A-Za-z_])", source))

    def test_cue_beyond_accepted_duration_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture(Path(tmp), final_end=908399)
            with self.assertRaises(SystemExit):
                verify_captions(args)

    def test_final_cue_shorter_than_authority_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture(Path(tmp), final_end=908397)
            with self.assertRaisesRegex(SystemExit, "TIMING_FINAL_END_MISMATCH"):
                verify_captions(args)

    def test_final_cue_longer_than_authority_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture(Path(tmp), final_end=908399)
            with self.assertRaisesRegex(SystemExit, "TIMING_FINAL_END_MISMATCH"):
                verify_captions(args)

    def test_receipt_duration_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture(Path(tmp), receipt_final_end=908397)
            with self.assertRaisesRegex(SystemExit, "RECEIPT_DURATION_MISMATCH"):
                verify_captions(args)

    def test_timing_duration_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            args = write_fixture(Path(tmp), timing_audio_duration=908397)
            with self.assertRaisesRegex(SystemExit, "TIMING_DURATION_MISMATCH"):
                verify_captions(args)


class WorkflowAuthorityTests(unittest.TestCase):
    def setup_root(self, duplicate: str | None = None, duplicate_name: str = "generic.yml") -> tuple[Path, tempfile.TemporaryDirectory]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        workflows = root / ".github/workflows"
        workflows.mkdir(parents=True)
        (workflows / "canonical-gold-s01-minute-proofs.yml").write_text(
            "name: Canonical Gold S01\non:\n  workflow_dispatch:\njobs:\n  static:\n    runs-on: ubuntu-latest\n",
            encoding="utf-8",
        )
        (workflows / "unrelated-generic.yml").write_text(
            "name: Generic lint\non:\n  pull_request:\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo lint\n",
            encoding="utf-8",
        )
        if duplicate:
            (workflows / duplicate_name).write_text(duplicate, encoding="utf-8")
        (root / "docs").mkdir()
        (root / "docs/inventory.json").write_text(json.dumps(inventory()), encoding="utf-8")
        return root, tmp

    def assert_duplicate_rejected(self, trigger: str, name: str = "opaque.yml") -> None:
        duplicate = f"name: Opaque\non:\n  {trigger}:\nenv:\n  SOURCE_REPO: TheGor-365/ai-course-source-library\n  SOURCE_HEAD: 4cfc9acd1509408f86c8b3a788779173395bbb2f\njobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/upload-artifact@v4\n"
        root, tmp = self.setup_root(duplicate, name)
        self.addCleanup(tmp.cleanup)
        with self.assertRaisesRegex(SystemExit, "ACTIVE_COMPETING_GOLD_PSU_WORKFLOW"):
            scan_workflow_authority(root / ".github/workflows", root / "docs/inventory.json")

    def test_duplicate_named_without_s01_detected(self) -> None:
        self.assert_duplicate_rejected("workflow_dispatch", "totally-generic.yml")

    def test_duplicate_gold_psu_source_gate_detected(self) -> None:
        self.assert_duplicate_rejected("workflow_dispatch", "gold-psu-source-exact-gate-v1.yml")

    def test_push_triggered_duplicate_detected(self) -> None:
        self.assert_duplicate_rejected("push")

    def test_pull_request_triggered_duplicate_detected(self) -> None:
        self.assert_duplicate_rejected("pull_request")

    def test_workflow_dispatch_duplicate_detected(self) -> None:
        self.assert_duplicate_rejected("workflow_dispatch")

    def test_unrelated_generic_workflow_not_false_positive(self) -> None:
        root, tmp = self.setup_root()
        self.addCleanup(tmp.cleanup)
        result = scan_workflow_authority(root / ".github/workflows", root / "docs/inventory.json")
        self.assertEqual(0, result["active_competing_gold_psu_workflow_count"])

    def test_canonical_single_workflow_pass(self) -> None:
        root, tmp = self.setup_root()
        self.addCleanup(tmp.cleanup)
        result = scan_workflow_authority(root / ".github/workflows", root / "docs/inventory.json")
        self.assertTrue(result["one_canonical_gold_s01_workflow"])
        self.assertFalse(result["filename_only_workflow_scanner"])


class ManifestTests(unittest.TestCase):
    def test_split_compile_runtime_heads_are_valid(self) -> None:
        result = verify_manifest_dict(manifest())
        self.assertNotEqual(result["production_compile_head"], result["production_runtime_head"])

    def test_provisional_manifest_is_rejected(self) -> None:
        value = manifest(); value["provisional_field_count"] = 1
        with self.assertRaises(SystemExit): verify_manifest_dict(value)

    def test_manifest_self_reference_is_rejected(self) -> None:
        value = manifest(); value["manifest_carrier_head"] = H40
        with self.assertRaises(SystemExit): verify_manifest_dict(value)

    def test_render_authorization_is_rejected(self) -> None:
        value = manifest(); value["two_minute_render_authorized"] = True
        with self.assertRaises(SystemExit): verify_manifest_dict(value)


class ComponentReceiptTests(unittest.TestCase):
    def test_exact_frame_set_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "component.json"
            payload = {
                "schema_version": "gold_s01_component_evidence.v2",
                "frames": [{"frame": frame, "composition_id": "GoldS01PremiumFirst120s", "production_runtime_head": H40, "frame_sha256": hashlib.sha256(str(frame).encode()).hexdigest(), "generic_asset_grid_count": 0} for frame in REQUIRED_EVIDENCE_FRAMES],
                "qc": {key: "PASS" for key in ("FRAME_ZERO_LAYOUT", "SCENE_CONTINUITY", "PRIMARY_FOCUS_BOUNDS", "CAPTION_CLEARANCE", "CONTACT_SHADOW_EVIDENCE", "DEPTH_LAYER_EVIDENCE", "EVENT_TARGET_DELTA", "NO_GENERIC_GRID", "NO_BLANK_FRAME")},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            args = type("Args", (), {"receipt_path": str(path), "output": None})()
            result = verify_component_receipt(args)
            self.assertEqual(result["frame_count"], 27)


if __name__ == "__main__":
    unittest.main()
