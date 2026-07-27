#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
VTT_TIME = re.compile(
    r"^(?:(?P<h>\d{2}):)?(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d{3})$"
)
REQUIRED_CAPTION_FILES = (
    "s01_ru_accepted_timing_contract_v01.json",
    "s01_ru_final_captions_v01.json",
    "s01_ru_final_captions_v01.vtt",
    "caption_recovery_receipt.json",
    "SHA256SUMS",
)
REQUIRED_EVIDENCE_FRAMES = (
    0, 89, 90, 317, 318, 544, 545, 589, 634, 635,
    1301, 1302, 1967, 1968, 2013, 2057, 2058,
    2436, 2437, 2815, 2816, 2861, 2905, 2906,
    3329, 3330, 3599,
)
REQUIRED_QC = (
    "FRAME_ZERO_LAYOUT",
    "SCENE_CONTINUITY",
    "PRIMARY_FOCUS_BOUNDS",
    "CAPTION_CLEARANCE",
    "CONTACT_SHADOW_EVIDENCE",
    "DEPTH_LAYER_EVIDENCE",
    "EVENT_TARGET_DELTA",
    "NO_GENERIC_GRID",
    "NO_BLANK_FRAME",
)


def fail(code: str, detail: str) -> "NoReturn":
    raise SystemExit(f"{code}:{detail}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("JSON_READ_FAILED", f"{path}:{exc}")
    if not isinstance(value, dict):
        fail("JSON_OBJECT_REQUIRED", str(path))
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_hash(value: Any, key: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        fail("SHA256_REQUIRED", key)
    return value


def require_head(value: Any, key: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        fail("HEAD_SHA_REQUIRED", key)
    return value


def require_string(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value:
        fail("STRING_REQUIRED", key)
    return value


def require_int(value: Any, key: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        fail("INTEGER_REQUIRED", key)
    return value


def caption_blocks(value: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("blocks", "captions", "segments", "cues"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            if not all(isinstance(item, dict) for item in candidate):
                fail("CAPTION_BLOCK_OBJECT_REQUIRED", key)
            return candidate
    fail("CAPTION_BLOCK_ARRAY_MISSING", "caption_json")


def parse_vtt_time(value: str) -> int:
    match = VTT_TIME.fullmatch(value.strip())
    if not match:
        fail("VTT_TIMESTAMP_INVALID", value)
    hours = int(match.group("h") or 0)
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    milliseconds = int(match.group("ms"))
    if minutes >= 60 or seconds >= 60:
        fail("VTT_TIMESTAMP_RANGE_INVALID", value)
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + milliseconds


def parse_vtt_cues(path: Path) -> list[tuple[int, int]]:
    cues: list[tuple[int, int]] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        if "-->" not in raw:
            continue
        left, right = (item.strip().split()[0] for item in raw.split("-->", 1))
        start, end = parse_vtt_time(left), parse_vtt_time(right)
        if end <= start:
            fail("VTT_CUE_NON_POSITIVE", raw)
        cues.append((start, end))
    return cues


def verify_sums(root: Path) -> None:
    sums = root / "SHA256SUMS"
    if not sums.is_file():
        fail("SHA256SUMS_MISSING", str(root))
    seen: set[str] = set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split("  ", 1)
        except ValueError:
            fail("SHA256SUMS_LINE_INVALID", line)
        require_hash(digest, name)
        target = root / name
        if not target.is_file() or sha256(target) != digest:
            fail("SHA256SUMS_IDENTITY_FAILED", name)
        seen.add(name)
    required = set(REQUIRED_CAPTION_FILES) - {"SHA256SUMS"}
    if seen != required:
        fail("SHA256SUMS_FILE_SET_MISMATCH", ",".join(sorted(seen)))


def verify_captions(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    if not root.is_dir():
        fail("CAPTION_ROOT_MISSING", str(root))
    observed = sorted(path.name for path in root.iterdir() if path.is_file())
    if observed != sorted(REQUIRED_CAPTION_FILES):
        fail("CAPTION_FILE_SET_MISMATCH", ",".join(observed))
    verify_sums(root)
    timing = root / REQUIRED_CAPTION_FILES[0]
    caption_json = root / REQUIRED_CAPTION_FILES[1]
    caption_vtt = root / REQUIRED_CAPTION_FILES[2]
    recovery = load_json(root / REQUIRED_CAPTION_FILES[3])
    expected_timing = require_hash(args.timing_sha256, "timing_sha256")
    expected_json = require_hash(args.caption_json_sha256, "caption_json_sha256")
    expected_vtt = require_hash(args.caption_vtt_sha256, "caption_vtt_sha256")
    if sha256(timing) != expected_timing:
        fail("TIMING_IDENTITY_FAILED", str(timing))
    if sha256(caption_json) != expected_json:
        fail("CAPTION_JSON_IDENTITY_FAILED", str(caption_json))
    if sha256(caption_vtt) != expected_vtt:
        fail("CAPTION_VTT_IDENTITY_FAILED", str(caption_vtt))
    blocks = caption_blocks(load_json(caption_json))
    if len(blocks) != 13:
        fail("CAPTION_JSON_BLOCK_COUNT_MISMATCH", str(len(blocks)))
    cues = parse_vtt_cues(caption_vtt)
    if len(cues) != 13:
        fail("CAPTION_VTT_CUE_COUNT_MISMATCH", str(len(cues)))
    previous_end = -1
    for start, end in cues:
        if start < previous_end:
            fail("CAPTION_VTT_NON_MONOTONIC", f"{start}:{previous_end}")
        if end > 900_000:
            fail("CAPTION_VTT_OUTSIDE_LESSON", str(end))
        previous_end = end
    accepted_audio_head = require_head(args.accepted_audio_head, "accepted_audio_head")
    expected_receipt = {
        "accepted_audio_execution_head": accepted_audio_head,
        "accepted_timing_sha256": expected_timing,
        "caption_json_sha256": expected_json,
        "caption_vtt_sha256": expected_vtt,
        "editorial_mutation_performed": False,
        "timing_mutation_performed": False,
        "segmentation_mutated": False,
        "regeneration_performed": False,
    }
    for key, expected in expected_receipt.items():
        if recovery.get(key) != expected:
            fail("CAPTION_RECOVERY_RECEIPT_MISMATCH", key)
    result = {
        "schema_version": "gold_s01_caption_identity_receipt.v2",
        **expected_receipt,
        "json_block_count": len(blocks),
        "vtt_cue_count": len(cues),
        "caption_download_identity": True,
        "no_fake_green": True,
    }
    if args.receipt:
        write_json(Path(args.receipt), result)
    return result


def stage_caption_pack(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    output = Path(args.output_dir).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for name in REQUIRED_CAPTION_FILES:
        source = root / name
        if not source.is_file():
            fail("CAPTION_SOURCE_FILE_MISSING", name)
        shutil.copy2(source, output / name)
    verify_sums(output)
    result = {
        "schema_version": "gold_s01_caption_pack_stage_receipt.v2",
        "file_count": len(REQUIRED_CAPTION_FILES),
        "file_names": list(REQUIRED_CAPTION_FILES),
        "no_extra_files": True,
    }
    if args.receipt:
        write_json(Path(args.receipt), result)
    return result


MANIFEST_REQUIRED = (
    "schema_version", "work_order_id", "oc_head", "oc_blob_sha",
    "source_repository", "source_branch", "source_head",
    "source_exact_run", "source_exact_artifact_id",
    "source_exact_artifact_sha256", "production_repository",
    "production_branch", "production_compile_head", "production_runtime_head",
    "compiler_run", "compiler_job", "compiler_artifact_id",
    "compiler_artifact_sha256", "compiler_output_file_hashes",
    "quality_repository", "quality_branch", "quality_evidence_head",
    "runner_repository", "runner_branch", "runner_workflow_head",
    "accepted_audio_execution_head", "A3483_sha256", "caption_carrier_head",
    "caption_json_sha256", "caption_vtt_sha256", "caption_artifact_id",
    "caption_artifact_sha256", "component_evidence_artifact_id",
    "component_evidence_artifact_sha256", "composition_id", "entrypoint",
    "fps", "duration_in_frames", "width", "height", "timeline_start_frame",
    "timeline_end_frame_exclusive", "provisional_field_count",
    "media_render_started", "two_minute_render_authorized",
    "full_15_minute_render_authorized", "no_fake_green",
)


def verify_manifest_dict(value: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in MANIFEST_REQUIRED if key not in value]
    if missing:
        fail("MANIFEST_REQUIRED_FIELD_MISSING", ",".join(missing))
    if "manifest_carrier_head" in value:
        fail("MANIFEST_SELF_REFERENCE_FORBIDDEN", "manifest_carrier_head")
    if value["schema_version"] != "gold_s01_pre_render_manifest.v2":
        fail("MANIFEST_SCHEMA_MISMATCH", str(value["schema_version"]))
    for key in (
        "oc_head", "source_head", "production_compile_head",
        "production_runtime_head", "quality_evidence_head",
        "runner_workflow_head", "accepted_audio_execution_head",
        "caption_carrier_head",
    ):
        require_head(value[key], key)
    for key in (
        "oc_blob_sha", "source_exact_artifact_sha256",
        "compiler_artifact_sha256", "A3483_sha256", "caption_json_sha256",
        "caption_vtt_sha256", "caption_artifact_sha256",
        "component_evidence_artifact_sha256",
    ):
        require_hash(value[key], key)
    output_hashes = value["compiler_output_file_hashes"]
    if not isinstance(output_hashes, dict) or not output_hashes:
        fail("COMPILER_OUTPUT_HASH_MAP_REQUIRED", "compiler_output_file_hashes")
    for name, digest in output_hashes.items():
        require_string(name, "compiler_output_file_name")
        require_hash(digest, f"compiler_output_file_hashes.{name}")
    for key in (
        "source_exact_run", "source_exact_artifact_id", "compiler_run",
        "compiler_job", "compiler_artifact_id", "caption_artifact_id",
        "component_evidence_artifact_id",
    ):
        require_int(value[key], key, 1)
    expected = {
        "composition_id": "GoldS01PremiumFirst120s",
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
    for key, wanted in expected.items():
        if value[key] != wanted:
            fail("MANIFEST_VALUE_MISMATCH", key)
    for key in (
        "work_order_id", "source_repository", "source_branch",
        "production_repository", "production_branch", "quality_repository",
        "quality_branch", "runner_repository", "runner_branch", "entrypoint",
    ):
        require_string(value[key], key)
    return value


def verify_manifest(args: argparse.Namespace) -> dict[str, Any]:
    path = Path(args.manifest)
    value = verify_manifest_dict(load_json(path))
    result = {
        "schema_version": "gold_s01_manifest_validation_receipt.v2",
        "manifest_sha256": sha256(path),
        "work_order_id": value["work_order_id"],
        "production_compile_head": value["production_compile_head"],
        "production_runtime_head": value["production_runtime_head"],
        "runner_workflow_head": value["runner_workflow_head"],
        "provisional_field_count": 0,
        "media_render_started": False,
        "result": "PASS",
        "no_fake_green": True,
    }
    if args.receipt:
        write_json(Path(args.receipt), result)
    return result


def verify_component_receipt(args: argparse.Namespace) -> dict[str, Any]:
    value = load_json(Path(args.receipt_path))
    if value.get("schema_version") != "gold_s01_component_evidence.v2":
        fail("COMPONENT_RECEIPT_SCHEMA_MISMATCH", str(value.get("schema_version")))
    frames = value.get("frames")
    if not isinstance(frames, list):
        fail("COMPONENT_FRAME_LIST_REQUIRED", "frames")
    observed = sorted(
        require_int(frame.get("frame"), "frame", 0)
        for frame in frames
        if isinstance(frame, dict)
    )
    if observed != list(REQUIRED_EVIDENCE_FRAMES):
        fail("COMPONENT_FRAME_SET_MISMATCH", ",".join(map(str, observed)))
    for frame in frames:
        if not isinstance(frame, dict):
            fail("COMPONENT_FRAME_OBJECT_REQUIRED", "frames")
        require_head(frame.get("production_runtime_head"), "production_runtime_head")
        require_hash(frame.get("frame_sha256"), "frame_sha256")
        if frame.get("composition_id") != "GoldS01PremiumFirst120s":
            fail("COMPONENT_COMPOSITION_ID_MISMATCH", str(frame.get("frame")))
        if frame.get("generic_asset_grid_count") != 0:
            fail("COMPONENT_GENERIC_GRID_DETECTED", str(frame.get("frame")))
    qc = value.get("qc")
    if not isinstance(qc, dict):
        fail("COMPONENT_QC_OBJECT_REQUIRED", "qc")
    for key in REQUIRED_QC:
        if qc.get(key) != "PASS":
            fail("COMPONENT_QC_FAILED", key)
    result = {
        "schema_version": "gold_s01_component_evidence_validation.v2",
        "frame_count": len(frames),
        "required_frame_count": len(REQUIRED_EVIDENCE_FRAMES),
        "qc_pass_count": len(REQUIRED_QC),
        "result": "PASS",
        "media_render_started": False,
    }
    if args.output:
        write_json(Path(args.output), result)
    return result


def get_value(args: argparse.Namespace) -> Any:
    value: Any = load_json(Path(args.manifest))
    for part in args.key.split("."):
        if not isinstance(value, dict) or part not in value:
            fail("MANIFEST_KEY_MISSING", args.key)
        value = value[part]
    if isinstance(value, (dict, list)):
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    elif isinstance(value, bool):
        print(str(value).lower())
    else:
        print(value)
    return value


def write_pre_render_receipt(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest)
    manifest = verify_manifest_dict(load_json(manifest_path))
    runtime = load_json(Path(args.runtime_receipt))
    quality = load_json(Path(args.quality_receipt))
    component = load_json(Path(args.component_receipt))
    caption = load_json(Path(args.caption_receipt))
    if runtime.get("result") != "PASS":
        fail("RUNTIME_RECEIPT_NOT_PASS", str(runtime.get("result")))
    if quality.get("result") != "PASS":
        fail("QUALITY_RECEIPT_NOT_PASS", str(quality.get("result")))
    if component.get("result") != "PASS":
        fail("COMPONENT_RECEIPT_NOT_PASS", str(component.get("result")))
    if caption.get("caption_download_identity") is not True:
        fail("CAPTION_DOWNLOAD_IDENTITY_NOT_PASS", "caption_receipt")
    result = {
        "schema_version": "gold_s01_public_pre_render_receipt.v2",
        "work_order_id": manifest["work_order_id"],
        "manifest_sha256": sha256(manifest_path),
        "source_head": manifest["source_head"],
        "production_compile_head": manifest["production_compile_head"],
        "production_runtime_head": manifest["production_runtime_head"],
        "quality_evidence_head": manifest["quality_evidence_head"],
        "runner_workflow_head": manifest["runner_workflow_head"],
        "caption_carrier_head": manifest["caption_carrier_head"],
        "composition_id": manifest["composition_id"],
        "duration_in_frames": manifest["duration_in_frames"],
        "public_pre_render_green": True,
        "real_job_steps_available": True,
        "media_render_started": False,
        "two_minute_render_authorized": False,
        "full_15_minute_render_authorized": False,
        "no_fake_green": True,
    }
    write_json(Path(args.output), result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify-captions")
    verify.add_argument("--root", required=True)
    verify.add_argument("--accepted-audio-head", required=True)
    verify.add_argument("--timing-sha256", required=True)
    verify.add_argument("--caption-json-sha256", required=True)
    verify.add_argument("--caption-vtt-sha256", required=True)
    verify.add_argument("--receipt")
    verify.set_defaults(func=verify_captions)
    stage = sub.add_parser("stage-caption-pack")
    stage.add_argument("--root", required=True)
    stage.add_argument("--output-dir", required=True)
    stage.add_argument("--receipt")
    stage.set_defaults(func=stage_caption_pack)
    manifest = sub.add_parser("verify-manifest")
    manifest.add_argument("--manifest", required=True)
    manifest.add_argument("--receipt")
    manifest.set_defaults(func=verify_manifest)
    component = sub.add_parser("verify-component-receipt")
    component.add_argument("--receipt-path", required=True)
    component.add_argument("--output")
    component.set_defaults(func=verify_component_receipt)
    getter = sub.add_parser("get")
    getter.add_argument("--manifest", required=True)
    getter.add_argument("--key", required=True)
    getter.set_defaults(func=get_value)
    receipt = sub.add_parser("write-pre-render-receipt")
    receipt.add_argument("--manifest", required=True)
    receipt.add_argument("--runtime-receipt", required=True)
    receipt.add_argument("--quality-receipt", required=True)
    receipt.add_argument("--component-receipt", required=True)
    receipt.add_argument("--caption-receipt", required=True)
    receipt.add_argument("--output", required=True)
    receipt.set_defaults(func=write_pre_render_receipt)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    if isinstance(result, dict):
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
