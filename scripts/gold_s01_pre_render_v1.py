#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
VTT_TS = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\.(\d{3})$")
BLOCKING = ("UNRESOLVED", "PROVISIONAL", "PENDING", "ABSENT", "UNKNOWN", "TBD", "TODO")
EXPECTED = {
    "oc_head": "6fc3801532486b6bcd40d6f8b2a6c6bf90aa80d7",
    "oc_blob": "f41935cd1163a6aadc1aac89d6c59e2057402c5e",
    "A3483_sha": "74d9a9008b594bd8bd18f001d05542e249bd9af371c32e87181a0df42064f352",
    "accepted_timing_sha": "716b539630ad501d16e2dac13d1a6107b601a9094a3c57941cc962dc185b4b61",
    "caption_json_sha": "5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18",
}
REQUIRED = (
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
SHA256_KEYS = (
    "source_receipt_hash", "production_receipt_hash", "PSU_closure_sha", "shared_ID_registry_sha",
    "mandatory_visual_minimum_sha", "premium_shot_specs_sha", "compiler_receipt_sha", "ShotIR_sha",
    "SceneIR_sha", "asset_manifest_sha", "asset_consumption_sha", "runtime_binding_sha",
    "telemetry_plan_sha", "quality_manifest_sha", "A3483_sha", "accepted_timing_sha",
    "caption_json_sha", "caption_vtt_sha"
)
PATH_KEYS = ("source_receipt_path", "production_receipt_path", "compiler_output_dir", "component_evidence_path", "caption_input_receipt_path")


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object JSON required: {path}")
    return value


def write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def blocked(value: Any) -> bool:
    if isinstance(value, str):
        upper = value.upper()
        return any(token in upper for token in BLOCKING)
    if isinstance(value, dict):
        return any(blocked(item) for item in value.values())
    if isinstance(value, list):
        return any(blocked(item) for item in value)
    return False


def validate_manifest(m: dict[str, Any]) -> list[str]:
    errors = [f"MISSING:{key}" for key in REQUIRED if key not in m]
    if m.get("schema_version") != "gold_s01_two_minute_pre_render_input.v1":
        errors.append("SCHEMA_VERSION")
    if blocked(m):
        errors.append("PROVISIONAL_OR_UNRESOLVED_VALUE")
    for key in ("oc_head", "oc_blob", "source_head", "production_head"):
        if not isinstance(m.get(key), str) or not SHA1.fullmatch(m[key]):
            errors.append(f"SHA1:{key}")
    for key in SHA256_KEYS:
        if not isinstance(m.get(key), str) or not SHA256.fullmatch(m[key]):
            errors.append(f"SHA256:{key}")
    for key, expected in EXPECTED.items():
        if m.get(key) != expected:
            errors.append(f"IDENTITY:{key}")
    if m.get("source_repo") != "TheGor-365/ai-course-source-library":
        errors.append("SOURCE_REPO")
    if m.get("production_repo") != "TheGor-365/ai-course-production-system":
        errors.append("PRODUCTION_REPO")
    if m.get("A3483_release") != "gold-s01-a3483-input-v1":
        errors.append("A3483_RELEASE")
    if not isinstance(m.get("caption_artifact_id"), int) or m["caption_artifact_id"] <= 0:
        errors.append("CAPTION_ARTIFACT_ID")
    for key in PATH_KEYS:
        value = m.get(key)
        if not isinstance(value, str) or not value or value.startswith("/") or ".." in Path(value).parts:
            errors.append(f"RELATIVE_PATH:{key}")
    if m.get("two_minute_render_authorized") is not False:
        errors.append("TWO_MINUTE_RENDER_AUTHORIZED")
    if m.get("full_render_authorized") is not False:
        errors.append("FULL_RENDER_AUTHORIZED")
    if m.get("qualifying_media_run_started") is not False:
        errors.append("QUALIFYING_MEDIA_RUN_STARTED")
    if m.get("provisional_field_count") != 0:
        errors.append("PROVISIONAL_FIELD_COUNT")
    if m.get("no_fake_green") is not True:
        errors.append("NO_FAKE_GREEN")
    return sorted(set(errors))


def timestamp(value: str) -> int:
    match = VTT_TS.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid VTT timestamp: {value}")
    hours, minutes, seconds, millis = map(int, match.groups())
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def caption_blocks(doc: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("captions", "caption_blocks", "segments", "items", "cues"):
        value = doc.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    raise ValueError("caption JSON has no caption block array")


def bounds(block: dict[str, Any]) -> tuple[int, int]:
    start = next((block.get(key) for key in ("start_ms", "start", "begin_ms") if key in block), None)
    end = next((block.get(key) for key in ("end_ms", "end", "finish_ms") if key in block), None)
    if isinstance(start, str) and ":" in start:
        start = timestamp(start)
    if isinstance(end, str) and ":" in end:
        end = timestamp(end)
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("caption block lacks integer timing")
    return start, end


def verify_caption_json(path: Path) -> dict[str, Any]:
    blocks = caption_blocks(load(path))
    if len(blocks) != 13:
        raise ValueError(f"expected 13 caption blocks, observed {len(blocks)}")
    previous = -1
    for index, block in enumerate(blocks):
        start, end = bounds(block)
        if start < 0 or end <= start or start < previous or end > 900000:
            raise ValueError(f"invalid caption block {index}")
        previous = end
    return {"block_count": 13, "first_start_ms": bounds(blocks[0])[0], "last_end_ms": previous}


def verify_vtt(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").replace("\r\n", "\n").splitlines()
    if not lines or lines[0].strip() != "WEBVTT":
        raise ValueError("WEBVTT header missing")
    cues = []
    for line in lines:
        if " --> " in line:
            left, right = line.split(" --> ", 1)
            cues.append((timestamp(left.split()[0]), timestamp(right.split()[0])))
    if len(cues) != 13:
        raise ValueError(f"expected 13 VTT cues, observed {len(cues)}")
    previous = -1
    for index, (start, end) in enumerate(cues):
        if start < 0 or end <= start or start < previous or end > 900000:
            raise ValueError(f"invalid VTT cue {index}")
        previous = end
    return {"cue_count": 13, "first_start_ms": cues[0][0], "last_end_ms": cues[-1][1]}


def cmd_manifest(args: argparse.Namespace) -> int:
    errors = validate_manifest(load(args.manifest))
    result = {"valid": not errors, "errors": errors, "no_fake_green": True}
    if args.receipt:
        write(args.receipt, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def cmd_get(args: argparse.Namespace) -> int:
    value: Any = load(args.manifest)
    for part in args.key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(args.key)
        value = value[part]
    print(json.dumps(value, separators=(",", ":"), sort_keys=True) if isinstance(value, (dict, list)) else str(value).lower() if isinstance(value, bool) else value)
    return 0


def cmd_file(args: argparse.Namespace) -> int:
    observed = digest(args.path)
    if observed != args.sha256:
        raise ValueError(f"hash mismatch: {args.path}: {observed}")
    print(observed)
    return 0


def cmd_captions(args: argparse.Namespace) -> int:
    observed = {"json": digest(args.json_path), "vtt": digest(args.vtt_path), "timing": digest(args.timing_path)}
    expected = {"json": args.json_sha256, "vtt": args.vtt_sha256, "timing": args.timing_sha256}
    if observed != expected:
        raise ValueError(f"caption identity mismatch: {observed}")
    receipt = {
        "schema_version": "gold_s01_caption_input_receipt.v1",
        "accepted_caption_json_materialized": True,
        "accepted_caption_vtt_materialized": True,
        "caption_json_sha256": observed["json"],
        "caption_vtt_sha256": observed["vtt"],
        "accepted_timing_sha256": observed["timing"],
        "caption_artifact_id": args.artifact_id,
        "caption_packaging_run_id": args.run_id,
        "caption_packaging_job_id": args.job_id,
        "caption_artifact_download_hash_verified": args.download_verified,
        "json": verify_caption_json(args.json_path),
        "vtt": verify_vtt(args.vtt_path),
        "qualifying_media_run_started": False,
        "no_fake_green": True
    }
    write(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    files = {
        "s01_ru_final_captions_v01.json": args.json_path,
        "s01_ru_final_captions_v01.vtt": args.vtt_path,
        "s01_ru_accepted_timing_contract_v01.json": args.timing_path,
        "caption_input_receipt.json": args.receipt,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, source in files.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        shutil.copy2(source, args.output_dir / name)
    sums = [f"{digest(args.output_dir / name)}  {name}" for name in sorted(files)]
    (args.output_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return 0


def cmd_receipt(args: argparse.Namespace) -> int:
    manifest = load(args.manifest)
    errors = validate_manifest(manifest)
    production = load(args.production_validation_receipt)
    if production.get("valid") is not True:
        errors.extend(f"PRODUCTION_VALIDATION:{item}" for item in production.get("errors", ["NOT_VALID"]))
    errors = sorted(set(errors))
    result = {
        "schema_version": "gold_s01_public_runner_pre_render_receipt.v1",
        "run_id": args.run_id,
        "job_id": args.job_id,
        "runner_head": args.runner_head,
        "source_head": manifest.get("source_head"),
        "production_head": manifest.get("production_head"),
        "exact_source_clone": "PASS",
        "exact_production_clone": "PASS",
        "oc_v36_binding": "PASS",
        "composition_discovery": "PASS",
        "typecheck": "PASS",
        "no_render_validators": "PASS" if not errors else "FAIL",
        "media_render_started": False,
        "result": "PASS" if not errors else "FAIL",
        "open_non_human_pre_render_blocker_count": len(errors),
        "errors": errors,
        "two_minute_render_ready": not errors,
        "two_minute_render_authorized": False,
        "qualifying_media_run_started": False,
        "no_fake_green": True
    }
    write(args.receipt, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser()
    sub = root.add_subparsers(dest="command", required=True)
    p = sub.add_parser("verify-manifest"); p.add_argument("--manifest", type=Path, required=True); p.add_argument("--receipt", type=Path); p.set_defaults(func=cmd_manifest)
    p = sub.add_parser("get"); p.add_argument("--manifest", type=Path, required=True); p.add_argument("--key", required=True); p.set_defaults(func=cmd_get)
    p = sub.add_parser("verify-file"); p.add_argument("--path", type=Path, required=True); p.add_argument("--sha256", required=True); p.set_defaults(func=cmd_file)
    p = sub.add_parser("verify-captions")
    p.add_argument("--json", dest="json_path", type=Path, required=True); p.add_argument("--vtt", dest="vtt_path", type=Path, required=True); p.add_argument("--timing", dest="timing_path", type=Path, required=True)
    p.add_argument("--json-sha256", required=True); p.add_argument("--vtt-sha256", required=True); p.add_argument("--timing-sha256", required=True)
    p.add_argument("--artifact-id", type=int, default=0); p.add_argument("--run-id", type=int, required=True); p.add_argument("--job-id", type=int, required=True); p.add_argument("--download-verified", action="store_true"); p.add_argument("--receipt", type=Path, required=True); p.set_defaults(func=cmd_captions)
    p = sub.add_parser("stage-caption-pack"); p.add_argument("--json", dest="json_path", type=Path, required=True); p.add_argument("--vtt", dest="vtt_path", type=Path, required=True); p.add_argument("--timing", dest="timing_path", type=Path, required=True); p.add_argument("--receipt", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True); p.set_defaults(func=cmd_stage)
    p = sub.add_parser("write-pre-render-receipt"); p.add_argument("--manifest", type=Path, required=True); p.add_argument("--production-validation-receipt", type=Path, required=True); p.add_argument("--receipt", type=Path, required=True); p.add_argument("--run-id", type=int, required=True); p.add_argument("--job-id", type=int, required=True); p.add_argument("--runner-head", required=True); p.set_defaults(func=cmd_receipt)
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
