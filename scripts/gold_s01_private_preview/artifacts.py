from __future__ import annotations

from .common import *
from .contracts import validate_profile


def validate_ffprobe(probe: Mapping[str, Any], expected: Mapping[str, Any], artifact_type: str) -> None:
    format_name = str(probe.get("format", {}).get("format_name", ""))
    if expected["container"] not in format_name and format_name not in expected["container"]:
        raise PreviewError("FFPROBE_CONTAINER_MISMATCH", artifact_type)
    streams = probe.get("streams")
    if not isinstance(streams, list):
        raise PreviewError("FFPROBE_STREAMS_INVALID", artifact_type)
    video = [item for item in streams if item.get("codec_type") == "video"]
    audio = [item for item in streams if item.get("codec_type") == "audio"]
    if len(video) != 1:
        raise PreviewError("FFPROBE_VIDEO_STREAM_COUNT", artifact_type)
    v = video[0]
    if v.get("codec_name") != expected["video_codec"] or v.get("pix_fmt") != expected["pixel_format"] or v.get("width") != expected["width"] or v.get("height") != expected["height"]:
        raise PreviewError("FFPROBE_VIDEO_PROFILE_MISMATCH", artifact_type)
    rate = str(v.get("avg_frame_rate", "0/1")).split("/")
    if len(rate) != 2 or int(rate[0]) * expected["fps_den"] != expected["fps_num"] * int(rate[1]):
        raise PreviewError("FFPROBE_FRAME_RATE_MISMATCH", artifact_type)
    if artifact_type == "clean_visual_master":
        if len(audio) != expected["audio_streams"]:
            raise PreviewError("FFPROBE_CLEAN_MASTER_AUDIO_PRESENT", artifact_type)
    else:
        if len(audio) != 1:
            raise PreviewError("FFPROBE_AUDIO_STREAM_COUNT", artifact_type)
        a = audio[0]
        if a.get("codec_name") != expected["audio_codec"] or int(a.get("channels", 0)) != expected["audio_channels"] or int(a.get("sample_rate", 0)) != expected["audio_sample_rate"]:
            raise PreviewError("FFPROBE_AUDIO_PROFILE_MISMATCH", artifact_type)


def copy_verified(source: Path, target: Path, digest: str, size: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size == size and sha256_file(target) == digest:
            return
        raise PreviewError("CONTENT_ADDRESS_OVERWRITE_REJECTED", target.name)
    tmp = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(source, tmp)
    if tmp.stat().st_size != size or sha256_file(tmp) != digest:
        tmp.unlink(missing_ok=True)
        raise PreviewError("COPY_IDENTITY_MISMATCH", target.name)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)


def register_outputs(outputs: Mapping[str, Path], probes: Mapping[str, Mapping[str, Any]], profile: Mapping[str, Any], private_root: Path, request: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    primary_root = private_root / "gold_s01_primary_v1" / "sha256"
    replica_root = private_root / "gold_s01_replica_v1" / "sha256"
    owner_root = private_root / "gold_s01_owner_delivery_v1" / request["request_id"]
    owner_root.mkdir(parents=True, exist_ok=True)
    os.chmod(owner_root, 0o700)
    token = owner_root.parent / ".access_token"
    if not token.exists():
        token.write_text(secrets.token_hex(32) + "\n", encoding="ascii")
    os.chmod(token, 0o600)
    artifacts: list[dict[str, Any]] = []
    for artifact_type in ("clean_visual_master", "ru_preview"):
        source = outputs[artifact_type]
        if not source.is_file():
            raise PreviewError("FINAL_OUTPUT_MISSING", artifact_type)
        digest = sha256_file(source)
        size = source.stat().st_size
        validate_ffprobe(probes[artifact_type], profile["expected_outputs"][artifact_type], artifact_type)
        filename = profile["expected_outputs"][artifact_type]["filename"]
        primary = primary_root / digest[:2] / digest / filename
        replica = replica_root / digest[:2] / digest / filename
        owner = owner_root / filename
        copy_verified(source, primary, digest, size)
        copy_verified(primary, replica, digest, size)
        copy_verified(primary, owner, digest, size)
        artifacts.append({
            "artifact_type": artifact_type,
            "sha256": digest,
            "size_bytes": size,
            "codec_probe": probes[artifact_type],
            "primary_pointer": f"private-primary://sha256/{digest}",
            "replica_pointer": f"private-replica://sha256/{digest}",
            "owner_pointer": f"private-owner-review://{request['request_id']}/{filename}",
        })
    base = {"request_id": request["request_id"], "input_fingerprint": request["input_fingerprint"], "artifacts": artifacts, "artifact_count": len(artifacts), "public_artifacts_created": False, "private_content_public_exposure": False, "raw_private_paths_in_receipt": False, "no_fake_green": True, "completed_at": utc_now()}
    primary = {"schema_version": REGISTRATION_SCHEMA, **base, "registration_status": "PASS", "store_class": DEFAULT_PRIMARY_CLASS}
    primary["receipt_hash"] = canonical_hash(primary)
    replica = {"schema_version": REPLICA_SCHEMA, **base, "replica_status": "PASS", "store_class": DEFAULT_REPLICA_CLASS, "primary_receipt_hash": primary["receipt_hash"]}
    replica["receipt_hash"] = canonical_hash(replica)
    restore_rows: list[dict[str, Any]] = []
    scratch = private_root / "gold_s01_restore_scratch_v1" / request["input_fingerprint"]
    scratch.mkdir(parents=True, exist_ok=True)
    for item in artifacts:
        filename = profile["expected_outputs"][item["artifact_type"]]["filename"]
        source = replica_root / item["sha256"][:2] / item["sha256"] / filename
        restored = scratch / filename
        copy_verified(source, restored, item["sha256"], item["size_bytes"])
        if sha256_file(restored) != item["sha256"] or restored.stat().st_size != item["size_bytes"]:
            raise PreviewError("RESTORE_IDENTITY_MISMATCH", item["artifact_type"])
        validate_ffprobe(item["codec_probe"], profile["expected_outputs"][item["artifact_type"]], item["artifact_type"])
        restore_rows.append({"artifact_type": item["artifact_type"], "sha256": item["sha256"], "size_bytes": item["size_bytes"], "codec_verified": True})
        restored.unlink()
    scratch.rmdir()
    restore = {"schema_version": RESTORE_SCHEMA, "request_id": request["request_id"], "input_fingerprint": request["input_fingerprint"], "primary_receipt_hash": primary["receipt_hash"], "replica_receipt_hash": replica["receipt_hash"], "restore_status": "PASS", "verified_artifacts": restore_rows, "cleanup_status": "PASS", "public_artifacts_created": False, "private_content_public_exposure": False, "raw_private_paths_in_receipt": False, "no_fake_green": True, "completed_at": utc_now()}
    restore["receipt_hash"] = canonical_hash(restore)
    return primary, replica, restore


def load_private_output_manifest(path: Path, request: Mapping[str, Any], profile: Mapping[str, Any], private_root: Path) -> tuple[dict[str, Path], dict[str, Mapping[str, Any]], dict[str, Any]]:
    value = load_json(path)
    require_fields(value, {"schema_version", "input_fingerprint", "outputs", "machine_qc_status", "machine_qc_report_sha256", "public_artifacts_created", "private_content_public_exposure", "no_fake_green"}, "output_manifest")
    if value["schema_version"] != "GoldS01PrivateOutputManifest_v1":
        raise PreviewError("OUTPUT_MANIFEST_SCHEMA_INVALID", str(value.get("schema_version")))
    if value["input_fingerprint"] != request["input_fingerprint"]:
        raise PreviewError("OUTPUT_MANIFEST_FINGERPRINT_MISMATCH", "input fingerprint")
    if value["machine_qc_status"] != "GREEN":
        raise PreviewError("MACHINE_MEDIA_QC_NOT_GREEN", str(value["machine_qc_status"]))
    require_hex(value["machine_qc_report_sha256"], 64, "machine_qc_report_sha256")
    if value["public_artifacts_created"] is not False or value["private_content_public_exposure"] is not False or value["no_fake_green"] is not True:
        raise PreviewError("OUTPUT_MANIFEST_TRUTH_BOUNDARY_INVALID", "privacy")
    outputs = value["outputs"]
    if not isinstance(outputs, Mapping) or set(outputs) != {"clean_visual_master", "ru_preview"}:
        raise PreviewError("OUTPUT_MANIFEST_ARTIFACT_SET_INVALID", "clean visual + RU preview")
    paths: dict[str, Path] = {}
    probes: dict[str, Mapping[str, Any]] = {}
    for artifact_type, expected in profile["expected_outputs"].items():
        item = outputs[artifact_type]
        require_fields(item, {"relative_path", "sha256", "size_bytes", "ffprobe"}, f"outputs.{artifact_type}")
        relative = safe_relative(item["relative_path"], f"outputs.{artifact_type}.relative_path")
        target = private_root / relative
        if not target.is_file():
            raise PreviewError("FINAL_OUTPUT_MISSING", artifact_type)
        digest = require_hex(item["sha256"], 64, f"outputs.{artifact_type}.sha256")
        if target.stat().st_size != item["size_bytes"] or sha256_file(target) != digest:
            raise PreviewError("FINAL_OUTPUT_IDENTITY_MISMATCH", artifact_type)
        if target.name != expected["filename"]:
            raise PreviewError("FINAL_OUTPUT_FILENAME_MISMATCH", artifact_type)
        validate_ffprobe(item["ffprobe"], expected, artifact_type)
        paths[artifact_type] = target
        probes[artifact_type] = item["ffprobe"]
    return paths, probes, value
