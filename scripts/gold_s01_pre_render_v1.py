#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VTT_TS_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})$")
BLOCKING = ("UNRESOLVED", "PROVISIONAL", "PENDING", "ABSENT", "UNKNOWN", "TBD", "TODO")
EXPECTED = {
    "oc_head": "6fc3801532486b6bcd40d6f8b2a6c6bf90aa80d7",
    "oc_blob": "f41935cd1163a6aadc1aac89d6c59e2057402c5e",
    "a3483_sha": "74d9a9008b594bd8bd18f001d05542e249bd9af371c32e87181a0df42064f352",
    "accepted_timing_sha": "716b539630ad501d16e2dac13d1a6107b601a9094a3c57941cc962dc185b4b61",
    "caption_json_sha": "5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18",
}
REQUIRED_MANIFEST_KEYS = (
    "schema_version", "oc_head", "oc_blob", "source_repo", "source_branch", "source_head", "source_receipt_hash",
    "source_receipt_path", "production_repo", "production_branch", "production_head", "production_receipt_hash",
    "production_receipt_path", "compiler_output_dir", "component_evidence_path", "caption_input_receipt_path",
    "PSU_closure_sha", "shared_ID_registry_sha", "mandatory_visual_minimum_sha", "premium_shot_specs_sha",
    "compiler_receipt_sha", "ShotIR_sha", "SceneIR_sha", "asset_manifest_sha", "asset_consumption_sha",
    "runtime_binding_sha", "telemetry_plan_sha", "quality_manifest_sha", "A3483_release", "A3483_sha",
    "accepted_timing_sha", "caption_artifact_id", "caption_json_sha", "caption_vtt_sha",
    "two_minute_render_authorized", "full_render_authorized", "qualifying_media_run_started",
    "provisional_field_count", "no_fake_green"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object JSON required: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def has_blocking(value: Any) -> bool:
    if isinstance(value, str):
        upper = value.upper()
        return any(token in upper for token in BLOCKING)
    if isinstance(value, dict):
        return any(has_blocking(item) for item in value.values())
    if isinstance(value, list):
        return any(has_blocking(item) for item in value)
    return False


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"MISSING:{key}")
    if manifest.get("schema_version") != "gold_s01_two_minute_pre_render_input.v1":
        errors.append("SCHEMA_VERSION")
    if has_blocking(manifest):
        errors.append("PROVISIONAL_OR_UNRESOLVED_VALUE")
    for key in ("oc_head", "oc_blob", "source_head", "production_head"):
        if not isinstance(manifest.get(key), str) or not SHA1_RE.fullmatch(manifest[key]):
            errors.append(f"SHA1:{key}")
    for key in (
        "source_receipt_hash", "production_receipt_hash", "PSU_closure_sha", "shared_ID_registry_sha",
        "mandatory_visual_minimum_sha", "premium_shot_specs_sha", "compiler_receipt_sha", "ShotIR_sha", "SceneIR_sha",
        "asset_manifest_sha", "asset_consumption_sha", "runtime_binding_sha", "telemetry_plan_sha", "quality_manifest_sha",
        "A3483_sha", "accepted_timing_sha", "caption_json_sha", "caption_vtt_sha"
    ):
        if not isinstance(manifest.get(key), str) or not SHA256_RE.fullmatch(manifest[key]):
            errors.append(f"SHA256:{key}")
    identity_keys = {
        "oc_head": "oc_head",
        "oc_blob": "oc_blob",
        "a3483_sha": "A3483_sha",
        "accepted_timing_sha": "accepted_timing_sha",
        "caption_json_sha": "caption_json_sha",
    }
    for expected_key, manifest_key in identity_keys.items():
        if manifest.get(manifest_key) != EXPECTED[expected_key]:
            errors.append(f"IDENTITY:{manifest_key}")
    if manifest.get("source_repo") != "TheGor-365/ai-course-source-library":
        errors.append("SOURCE_REPO")
    if manifest.get("production_repo") != "TheGor-365/ai-course-production-system":
        errors.append("PRODUCTION_REPO")
    if manifest.get("A3483_release") != "gold-s01-a3483-input-v1":
        errors.append("A3483_RELEASE")
    if not isinstance(manifest.get("caption_artifact_id"), int) or manifest["caption_artifact_id"] <= 0:
        errors.append("CAPTION_ARTIFACT_ID")
    if manifest.get("two_minute_render_authorized") is not False:
        errors.append("TWO_MINUTE_RENDER_AUTHORIZED")
    if manifest.get("full_render_authorized") is not False:
        errors.append("FULL_RENDER_AUTHORIZED")
    if manifest.get("qualifying_media_run_started") is not False:
        errors.append("QUALIFYING_MEDIA_RUN_STARTED")
    if manifest.get("provisional_field_count") != 0:
        errors.append("PROVISIONAL_FIELD_COUNT")
    if manifest.get("no_fake_green") is not True:
        errors.append("NO_FAKE_GREEN")
    for key in (
        "source_receipt_path", "production_receipt_path", "compiler_output_dir",
        "component_evidence_path", "caption_input_receipt_path",
    ):
        value = manifest.get(key)
        if not isinstance(value, str) or not value or value.startswith("/") or ".." in Path(value).parts:
            errors.append(f"RELATIVE_PATH:{key}")
    return sorted(set(errors))


def parse_timestamp(value: str) -> int:
    match = VTT_TS_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid VTT timestamp: {value}")
    hours, minutes, seconds, millis = (int(part) for part in match.groups())
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def extract_caption_blocks(document: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("captions", "caption_blocks", "segments", "items", "cues"):
        value = document.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    raise ValueError("caption JSON has no caption block array")


def block_bounds(block: dict[str, Any]) -> tuple[int, int]:
    start = next((block.get(key) for key in ("start_ms", "start", "begin_ms") if key in block), None)
    end = next((block.get(key) for key in ("end_ms", "end", "finish_ms") if key in block), None)
    if isinstance(start, str) and ":" in start:
        start = parse_timestamp(start)
    if isinstance(end, str) and ":" in end:
        end = parse_timestamp(end)
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("caption block lacks integer timing")
    return start, end


def validate_caption_json(path: Path) -> dict[str, Any]:
    document = load_json(path)
    blocks = extract_caption_blocks(document)
    if len(blocks) != 13:
        raise ValueError(f"expected 13 caption blocks, observed {len(blocks)}")
    previous_end = -1
    for index, block in enumerate(blocks):
        start, end = block_bounds(block)
        if start < 0 or end <= start or start < previous_end:
            raise ValueError(f"non-monotonic caption block {index}")
        if end > 15 * 60 * 1000:
            raise ValueError(f"caption block {index} exceeds lesson duration")
        previous_end = end
    declared = None
    for key in ("sha256", "declared_sha256", "caption_sha256", "content_sha256"):
        if isinstance(document.get(key), str):
            declared = document[key]
            break
    return {
        "block_count": len(blocks),
        "first_start_ms": block_bounds(blocks[0])[0],
        "last_end_ms": previous_end,
        "declared_internal_hash": declared,
    }


def validate_vtt(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").splitlines()
    if not lines or lines[0].strip() != "WEBVTT":
        raise ValueError("WEBVTT header missing")
    cues: list[tuple[int, int]] = []
    for line in lines:
        if " --> " not in line:
            continue
        left, right = line.split(" --> ", 1)
        start = parse_timestamp(left.split()[0])
        end = parse_timestamp(right.split()[0])
        cues.append((start, end))
    if len(cues) != 13:
        raise ValueError(f"expected 13 VTT cues, observed {len(cues)}")
    previous_end = -1
    for index, (start, end) in enumerate(cues):
        if start < 0 or end <= start or start < previous_end:
            raise ValueError(f"non-monotonic VTT cue {index}")
        if end > 15 * 60 * 1000:
            raise ValueError(f"VTT cue {index} exceeds lesson duration")
        previous_end = end
    return {"cue_count": len(cues), "first_start_ms": cues[0][0], "last_end_ms": cues[-1][1]}


def cmd_verify_manifest(args: argparse.Namespace) -> int:
    manifest = load_json(args.manifest)
    errors = validate_manifest(manifest)
    result = {"valid": not errors, "errors": errors, "no_fake_green": True}
    if args.receipt:
        write_json(args.receipt, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def cmd_get(args: argparse.Namespace) -> int:
    manifest = load_json(args.manifest)
    value: Any = manifest
    for part in args.key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(args.key)
        value = value[part]
    if isinstance(value, (dict, list)):
        print(json.dumps(value, separators=(",", ":"), sort_keys=True))
    elif isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)
    return 0


def cmd_verify_file(args: argparse.Namespace) -> int:
    observed = sha256_file(args.path)
    if observed != args.sha256:
        raise ValueError(f"hash mismatch for {args.path}: {observed}")
    print(observed)
    return 0


def cmd_verify_captions(args: argparse.Namespace) -> int:
    json_sha = sha256_file(args.json_path)
    vtt_sha = sha256_file(args.vtt_path)
    timing_sha = sha256_file(args.timing_path)
    if json_sha != args.json_sha256:
        raise ValueError(f"caption JSON hash mismatch: {json_sha}")
    if vtt_sha != args.vtt_sha256:
        raise ValueError(f"caption VTT hash mismatch: {vtt_sha}")
    if timing_sha != args.timing_sha256:
        raise ValueError(f"timing contract hash mismatch: {timing_sha}")
    json_meta = validate_caption_json(args.json_path)
    vtt_meta = validate_vtt(args.vtt_path)
    receipt = {
        "schema_version": "gold_s01_caption_input_receipt.v1",
        "accepted_caption_json_materialized": True,
        "accepted_caption_vtt_materialized": True,
        "caption_json_sha256": json_sha,
        "caption_vtt_sha256": vtt_sha,
        "accepted_timing_sha256": timing_sha,
        "caption_artifact_id": args.artifact_id if args.artifact_id > 0 else None,
        "caption_artifact_id_recorded_externally": args.artifact_id > 0,
        "caption_packaging_run_id": args.run_id,
        "caption_packaging_job_id": args.job_id,
        "caption_artifact_download_hash_verified": args.download_verified,
        "json": json_meta,
        "vtt": vtt_meta,
        "qualifying_media_run_started": False,
        "no_fake_green": True,
    }
    write_json(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def cmd_stage_caption_pack(args: argparse.Namespace) -> int:
    required = {
        "s01_ru_final_captions_v01.json": args.json_path,
        "s01_ru_final_captions_v01.vtt": args.vtt_path,
        "s01_ru_accepted_timing_contract_v01.json": args.timing_path,
        "caption_input_receipt.json": args.receipt,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, source in required.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, args.output_dir / name)
    sums = [f"{sha256_file(args.output_dir / name)}  {name}" for name in sorted(required)]
    (args.output_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return 0


def cmd_write_pre_render_receipt(args: argparse.Namespace) -> int:
    manifest = load_json(args.manifest)
    errors = validate_manifest(manifest)
    production_receipt = load_json(args.production_validation_receipt)
    if production_receipt.get("valid") is not True:
        errors.extend(f"PRODUCTION_VALIDATION:{item}" for item in production_receipt.get("errors", ["NOT_VALID"]))
    result = {
        "schema_version": "gold_s01_public_runner_pre_render_receipt.v1",
        "run_id": args.run_id,
        "job_id": args.job_id,
        "runner_head": args.runner_head,
        "source_head": manifest.get("source_head"),
        "production_head": manifest.get("production_head"),
        "exact_source_clone": "PASS" if args.source_clone_pass else "FAIL",
        "exact_production_clone": "PASS" if args.production_clone_pass else "FAIL",
        "oc_v36_binding": "PASS" if args.oc_pass else "FAIL",
        "composition_discovery": "PASS" if args.composition_pass else "FAIL",
        "typecheck": "PASS" if args.typecheck_pass else "FAIL",
        "no_render_validators": "PASS" if not errors else "FAIL",
        "media_render_started": False,
        "result": "PASS" if not errors else "FAIL",
        "open_non_human_pre_render_blocker_count": len(sorted(set(errors))),
        "errors": sorted(set(errors)),
        "two_minute_render_ready": not errors,
        "two_minute_render_authorized": False,
        "qualifying_media_run_started": False,
        "no_fake_green": True,
    }
    write_json(args.receipt, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    subs = root.add_subparsers(dest="command", required=True)

    p = subs.add_parser("verify-manifest")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--receipt", type=Path)
    p.set_defaults(func=cmd_verify_manifest)

    p = subs.add_parser("get")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_get)

    p = subs.add_parser("verify-file")
    p.add_argument("--path", type=Path, required=True)
    p.add_argument("--sha256", required=True)
    p.set_defaults(func=cmd_verify_file)

    p = subs.add_parser("verify-captions")
    p.add_argument("--json", dest="json_path", type=Path, required=True)
    p.add_argument("--vtt", dest="vtt_path", type=Path, required=True)
    p.add_argument("--timing", dest="timing_path", type=Path, required=True)
    p.add_argument("--json-sha256", required=True)
    p.add_argument("--vtt-sha256", required=True)
    p.add_argument("--timing-sha256", required=True)
    p.add_argument("--artifact-id", type=int, default=0)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--job-id", type=int, required=True)
    p.add_argument("--download-verified", action="store_true")
    p.add_argument("--receipt", type=Path, required=True)
    p.set_defaults(func=cmd_verify_captions)

    p = subs.add_parser("stage-caption-pack")
    p.add_argument("--json", dest="json_path", type=Path, required=True)
    p.add_argument("--vtt", dest="vtt_path", type=Path, required=True)
    p.add_argument("--timing", dest="timing_path", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.set_defaults(func=cmd_stage_caption_pack)

    p = subs.add_parser("write-pre-render-receipt")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--production-validation-receipt", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--job-id", type=int, required=True)
    p.add_argument("--runner-head", required=True)
    for name in ("source-clone-pass", "production-clone-pass", "oc-pass", "composition-pass", "typecheck-pass"):
        p.add_argument(f"--{name}", action="store_true")
    p.set_defaults(func=cmd_write_pre_render_receipt)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
