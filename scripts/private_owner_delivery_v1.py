#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
SAFE_RELATIVE = re.compile(r"^[A-Za-z0-9._/-]+$")
RETRY_EXIT = 75
FACTORY_ID = "AI_COURSE_FACTORY"
REQUEST_SCHEMA = "PrivateOwnerDeliveryRequest_v1"
REGISTRATION_SCHEMA = "PrivateArtifactRegistrationReceipt_v1"
RESTORE_SCHEMA = "PrivateArtifactRestoreReceipt_v1"
MANIFEST_SCHEMA = "OwnerDeliveryManifest_v1"
SUPPORTED_TYPES = {"contact_sheet", "still_archive", "cross_scene_clip", "RU_preview"}
GENERATED_STILL_TYPES = {"contact_sheet", "still_archive"}
ADOPTED_MEDIA_TYPES = {"cross_scene_clip", "RU_preview"}


class DeliveryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class RetryableDeliveryError(DeliveryError):
    def __init__(self, message: str, resume_token: str) -> None:
        super().__init__("PRIVATE_DELIVERY_RETRYABLE_FAILURE", message)
        self.resume_token = resume_token


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value: Mapping[str, Any], *, omit: set[str] | None = None) -> str:
    omitted = omit or set()
    return hashlib.sha256(canonical_bytes({k: deepcopy(v) for k, v in value.items() if k not in omitted})).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryError("JSON_INVALID", str(path)) from exc
    if not isinstance(value, dict):
        raise DeliveryError("JSON_ROOT_INVALID", str(path))
    return value


def atomic_json(path: Path, value: Mapping[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def require_fields(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    missing = sorted(fields - set(value))
    if missing:
        raise DeliveryError("REQUEST_FIELDS_MISSING", f"{label}:{','.join(missing)}")


def safe_relative(value: Any, label: str) -> str:
    text = str(value)
    if not SAFE_RELATIVE.fullmatch(text) or text.startswith("/") or ".." in Path(text).parts:
        raise DeliveryError("UNSAFE_RELATIVE_PATH", label)
    return text


def validate_request(request: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "request_id", "package_id", "channel_id", "profile_id",
        "execution_authorized", "authorization_owner", "authorized_outputs",
        "authorized_inputs", "private_artifact_relative_root", "idempotency_key",
        "public_workflow_execution_allowed", "public_artifact_upload_allowed",
        "private_content_public_exposure", "no_fake_green",
    }
    require_fields(request, required, "request")
    if request["schema_version"] != REQUEST_SCHEMA:
        raise DeliveryError("REQUEST_SCHEMA_UNSUPPORTED", str(request.get("schema_version")))
    for key in ("request_id", "package_id", "channel_id", "authorization_owner", "idempotency_key"):
        if not isinstance(request[key], str) or not SAFE_ID.fullmatch(request[key]):
            raise DeliveryError("REQUEST_ID_UNSAFE", key)
    if request["execution_authorized"] is not True:
        raise DeliveryError("EXECUTION_NOT_AUTHORIZED", "execution_authorized must be true")
    if request["public_workflow_execution_allowed"] is not False:
        raise DeliveryError("PUBLIC_EXECUTION_FORBIDDEN", "public workflow execution must be false")
    if request["public_artifact_upload_allowed"] is not False:
        raise DeliveryError("PUBLIC_ARTIFACT_FORBIDDEN", "public artifact upload must be false")
    if request["private_content_public_exposure"] is not False or request["no_fake_green"] is not True:
        raise DeliveryError("TRUTH_BOUNDARY_INVALID", "privacy/no-fake-green")
    outputs = request["authorized_outputs"]
    if not isinstance(outputs, list) or not outputs or len(outputs) != len(set(outputs)):
        raise DeliveryError("OUTPUT_SET_INVALID", "authorized_outputs")
    if set(outputs) - SUPPORTED_TYPES:
        raise DeliveryError("OUTPUT_TYPE_UNSUPPORTED", ",".join(sorted(set(outputs) - SUPPORTED_TYPES)))
    profile = request["profile_id"]
    if profile == "OWNER_DELIVERY_EXISTING_STILLS_V1":
        if set(outputs) != GENERATED_STILL_TYPES:
            raise DeliveryError("PROFILE_OUTPUT_MISMATCH", profile)
    elif profile == "OWNER_DELIVERY_EXISTING_MEDIA_V1":
        if not set(outputs).issubset(ADOPTED_MEDIA_TYPES):
            raise DeliveryError("PROFILE_OUTPUT_MISMATCH", profile)
    else:
        raise DeliveryError("PROFILE_NOT_ALLOWLISTED", str(profile))

    inputs = request["authorized_inputs"]
    if not isinstance(inputs, Mapping):
        raise DeliveryError("AUTHORIZED_INPUTS_INVALID", "not object")
    required_inputs = {
        "production_repository", "production_branch", "production_sha",
        "input_manifest_repository_path", "input_manifest_git_blob_sha",
        "source_repository", "source_snapshot_branch", "source_snapshot_sha",
        "visual_runtime_head", "audio_timing_head", "accepted_timing_contract_sha256",
        "required_input_count",
    }
    require_fields(inputs, required_inputs, "authorized_inputs")
    for key in ("production_sha", "source_snapshot_sha", "visual_runtime_head"):
        if not HEX40.fullmatch(str(inputs[key])):
            raise DeliveryError("AUTHORIZED_HEAD_INVALID", key)
    if not HEX40.fullmatch(str(inputs["input_manifest_git_blob_sha"])):
        raise DeliveryError("MANIFEST_BLOB_INVALID", "input_manifest_git_blob_sha")
    safe_relative(inputs["input_manifest_repository_path"], "input_manifest_repository_path")
    safe_relative(request["private_artifact_relative_root"], "private_artifact_relative_root")
    if not isinstance(inputs["required_input_count"], int) or inputs["required_input_count"] < 1:
        raise DeliveryError("INPUT_COUNT_INVALID", "required_input_count")
    if profile == "OWNER_DELIVERY_EXISTING_STILLS_V1":
        if inputs["required_input_count"] != 17:
            raise DeliveryError("INPUT_COUNT_INVALID", "expected 17 stills")
        if inputs["audio_timing_head"] is not None or inputs["accepted_timing_contract_sha256"] is not None:
            raise DeliveryError("STILL_PROFILE_TIMING_SCOPE", "timing must remain unset")
    else:
        if not HEX40.fullmatch(str(inputs["audio_timing_head"])):
            raise DeliveryError("ACCEPTED_TIMING_REQUIRED", "audio_timing_head")
        if not HEX64.fullmatch(str(inputs["accepted_timing_contract_sha256"])):
            raise DeliveryError("ACCEPTED_TIMING_REQUIRED", "accepted_timing_contract_sha256")
        source_artifacts = request.get("source_artifacts")
        if not isinstance(source_artifacts, list) or len(source_artifacts) != len(outputs):
            raise DeliveryError("SOURCE_ARTIFACTS_REQUIRED", "one exact source per output")
        by_type = {item.get("artifact_type"): item for item in source_artifacts if isinstance(item, Mapping)}
        if set(by_type) != set(outputs):
            raise DeliveryError("SOURCE_ARTIFACTS_REQUIRED", "type mismatch")
        for artifact_type, item in by_type.items():
            safe_relative(item.get("relative_path"), f"source_artifact:{artifact_type}")
            if not HEX64.fullmatch(str(item.get("sha256"))) or not isinstance(item.get("size_bytes"), int):
                raise DeliveryError("SOURCE_ARTIFACT_IDENTITY_INVALID", artifact_type)
    return deepcopy(dict(request))


def git_output(checkout: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(checkout), *args], text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        raise DeliveryError("GIT_CHECK_FAILED", exc.output.strip()) from exc


def validate_exact_checkout(request: Mapping[str, Any], checkout: Path) -> Path:
    if git_output(checkout, "rev-parse", "--is-inside-work-tree") != "true":
        raise DeliveryError("PRIVATE_CHECKOUT_INVALID", "not a git worktree")
    expected = request["authorized_inputs"]["production_sha"]
    if git_output(checkout, "rev-parse", "HEAD") != expected:
        raise DeliveryError("EXACT_HEAD_MISMATCH", expected)
    if git_output(checkout, "status", "--porcelain"):
        raise DeliveryError("PRIVATE_CHECKOUT_DIRTY", "exact checkout must be clean")
    manifest = checkout / request["authorized_inputs"]["input_manifest_repository_path"]
    if not manifest.is_file():
        raise DeliveryError("INPUT_MANIFEST_MISSING", "repository path")
    observed_blob = git_output(checkout, "hash-object", str(manifest))
    if observed_blob != request["authorized_inputs"]["input_manifest_git_blob_sha"]:
        raise DeliveryError("INPUT_MANIFEST_BLOB_MISMATCH", observed_blob)
    return manifest


def validate_still_manifest(request: Mapping[str, Any], manifest: Mapping[str, Any], private_root: Path) -> list[dict[str, Any]]:
    if manifest.get("status") != "PENDING_EXPLICIT_HUMAN_VISUAL_QC":
        raise DeliveryError("STILL_MANIFEST_STATUS_INVALID", str(manifest.get("status")))
    if manifest.get("machine_qc_green") is not True or manifest.get("automatic_human_qc_green") is not False:
        raise DeliveryError("STILL_MANIFEST_QC_INVALID", "machine/human boundary")
    for flag in ("short_clip_allowed", "full_video_allowed", "video_allowed"):
        if manifest.get(flag) is not False:
            raise DeliveryError("VIDEO_AUTHORITY_INVALID", flag)
    items = manifest.get("review_items")
    expected_count = request["authorized_inputs"]["required_input_count"]
    if not isinstance(items, list) or len(items) != expected_count or manifest.get("artifact_count") != expected_count:
        raise DeliveryError("STILL_COUNT_MISMATCH", str(expected_count))
    root = private_root / request["private_artifact_relative_root"]
    validated: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in items:
        if not isinstance(raw, Mapping):
            raise DeliveryError("STILL_ITEM_INVALID", "not object")
        required = {"still_id", "filename", "sha256", "size_bytes", "width", "height", "frame", "scene_id", "component", "purpose"}
        require_fields(raw, required, "still")
        filename = safe_relative(raw["filename"], "still filename")
        if "/" in filename or filename in names:
            raise DeliveryError("STILL_FILENAME_INVALID", filename)
        names.add(filename)
        if not HEX64.fullmatch(str(raw["sha256"])) or not isinstance(raw["size_bytes"], int):
            raise DeliveryError("STILL_IDENTITY_INVALID", filename)
        path = root / filename
        if not path.is_file():
            raise DeliveryError("PRIVATE_ARTIFACT_MISSING", filename)
        if path.stat().st_size != raw["size_bytes"]:
            raise DeliveryError("PRIVATE_ARTIFACT_SIZE_MISMATCH", filename)
        digest = sha256_file(path)
        if digest != raw["sha256"]:
            raise DeliveryError("PRIVATE_ARTIFACT_HASH_MISMATCH", filename)
        validated.append({**dict(raw), "resolved_private_path": str(path), "validated_sha256": digest})
    return sorted(validated, key=lambda item: (int(item["frame"]), str(item["still_id"])))


def deterministic_tar(items: Sequence[Mapping[str, Any]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for item in items:
            path = Path(str(item["resolved_private_path"]))
            info = archive.gettarinfo(str(path), arcname=f"stills/{item['filename']}")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as handle:
                archive.addfile(info, handle)


def assemble_stills(request: Mapping[str, Any], checkout: Path, manifest_path: Path, manifest: Mapping[str, Any], items: Sequence[Mapping[str, Any]], staging: Path) -> dict[str, Path]:
    staging.mkdir(parents=True, exist_ok=True)
    runtime_request = deepcopy(dict(manifest))
    by_name = {item["filename"]: item for item in items}
    for item in runtime_request["review_items"]:
        item["private_path"] = by_name[item["filename"]]["resolved_private_path"]
    private_request = staging / "private_review_request_runtime_v1.json"
    atomic_json(private_request, runtime_request)
    review_dir = staging / "review_pack"
    script = checkout / "11_tools/render_factory/visual_runtime_v1/review_pack.py"
    if not script.is_file():
        raise DeliveryError("FIXED_ASSEMBLER_MISSING", "visual runtime review_pack.py")
    if shutil.which("ffmpeg") is None:
        raise DeliveryError("FFMPEG_UNAVAILABLE", "ffmpeg")
    try:
        subprocess.run([sys.executable, str(script), "--request", str(private_request), "--output-dir", str(review_dir), "--execute"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as exc:
        raise DeliveryError("REVIEW_PACK_ASSEMBLY_FAILED", exc.stderr[-500:]) from exc
    contact_sheet = review_dir / "contact_sheet_5x4_v1.png"
    if not contact_sheet.is_file():
        raise DeliveryError("CONTACT_SHEET_MISSING", "assembler output")
    archive = staging / "stills_full_resolution_v1.tar"
    deterministic_tar(items, archive)
    return {"contact_sheet": contact_sheet, "still_archive": archive}


def adopted_media(request: Mapping[str, Any], private_root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for item in request["source_artifacts"]:
        path = private_root / safe_relative(item["relative_path"], item["artifact_type"])
        if not path.is_file() or path.stat().st_size != item["size_bytes"] or sha256_file(path) != item["sha256"]:
            raise DeliveryError("SOURCE_ARTIFACT_IDENTITY_MISMATCH", item["artifact_type"])
        result[item["artifact_type"]] = path
    return result


def copy_verified(source: Path, target: Path, expected_sha: str, expected_size: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(source, tmp)
    if tmp.stat().st_size != expected_size or sha256_file(tmp) != expected_sha:
        tmp.unlink(missing_ok=True)
        raise DeliveryError("COPY_IDENTITY_MISMATCH", target.name)
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)


def ensure_channel(private_root: Path, channel_id: str, package_id: str) -> tuple[Path, Path]:
    channel_root = private_root / "owner_delivery_channels" / channel_id
    package_root = channel_root / package_id
    package_root.mkdir(parents=True, exist_ok=True)
    os.chmod(channel_root, 0o700)
    os.chmod(package_root, 0o700)
    token = channel_root / ".access_token"
    if not token.exists():
        token.write_text(secrets.token_hex(32) + "\n", encoding="ascii")
        os.chmod(token, stat.S_IRUSR | stat.S_IWUSR)
    elif stat.S_IMODE(token.stat().st_mode) != 0o600:
        os.chmod(token, 0o600)
    return package_root, token


def artifact_filename(artifact_type: str, source: Path) -> str:
    return {"contact_sheet": "contact_sheet_5x4_v1.png", "still_archive": "stills_full_resolution_v1.tar", "cross_scene_clip": "cross_scene_clip_v1.mp4", "RU_preview": "RU_preview_v1.mp4"}.get(artifact_type, source.name)


def create_base_state(request: Mapping[str, Any]) -> dict[str, Any]:
    return {"request_id": request["request_id"], "idempotency_key": request["idempotency_key"], "registered": {}, "completed": False, "resume_token_hash": None, "registration_attempts": 0, "skipped_existing_registrations": 0}


def execute_request(request: Mapping[str, Any], checkout: Path, private_root: Path, receipt_dir: Path, *, resume_token: str | None = None, inject_failure_after_registration: int | None = None, assembler: Callable[..., dict[str, Path]] = assemble_stills, clock: Callable[[], str] = utc_now) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    req = validate_request(request)
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise DeliveryError("PUBLIC_WORKFLOW_EXECUTION_FORBIDDEN", "private media must not execute in GitHub Actions")
    manifest_path = validate_exact_checkout(req, checkout)
    manifest = load_json(manifest_path)
    private_root = private_root.resolve()
    private_root.mkdir(parents=True, exist_ok=True)
    os.chmod(private_root, 0o700)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(receipt_dir, 0o700)

    state_key = hashlib.sha256(req["idempotency_key"].encode("utf-8")).hexdigest()
    state_path = private_root / "owner_delivery_state" / f"{state_key}.json"
    state = load_json(state_path) if state_path.exists() else create_base_state(req)
    if state.get("request_id") != req["request_id"] or state.get("idempotency_key") != req["idempotency_key"]:
        raise DeliveryError("IDEMPOTENCY_STATE_CONFLICT", state_key)
    if state.get("resume_token_hash"):
        if not resume_token or not hmac.compare_digest(state["resume_token_hash"], hashlib.sha256(resume_token.encode()).hexdigest()):
            raise DeliveryError("RESUME_TOKEN_MISMATCH", "resume token required")
    state["registration_attempts"] += 1
    atomic_json(state_path, state)

    staging = private_root / "owner_delivery_staging" / state_key
    if req["profile_id"] == "OWNER_DELIVERY_EXISTING_STILLS_V1":
        items = validate_still_manifest(req, manifest, private_root)
        outputs = assembler(req, checkout, manifest_path, manifest, items, staging)
    else:
        outputs = adopted_media(req, private_root)
    if set(outputs) != set(req["authorized_outputs"]):
        raise DeliveryError("ASSEMBLER_OUTPUT_MISMATCH", ",".join(sorted(outputs)))

    package_root, _token = ensure_channel(private_root, req["channel_id"], req["package_id"])
    store_root = private_root / "artifact_store_v1"
    backup_root = private_root / "artifact_backup_v1"
    registered: dict[str, dict[str, Any]] = dict(state["registered"])
    new_registration_count = 0

    for artifact_type in sorted(outputs):
        source = outputs[artifact_type]
        digest = sha256_file(source)
        size = source.stat().st_size
        filename = artifact_filename(artifact_type, source)
        store_path = store_root / "sha256" / digest[:2] / digest / filename
        backup_path = backup_root / "sha256" / digest[:2] / digest / filename
        delivery_path = package_root / filename
        existing = registered.get(artifact_type)
        if existing:
            if existing["sha256"] != digest or existing["size_bytes"] != size:
                raise DeliveryError("IDEMPOTENCY_ARTIFACT_CONFLICT", artifact_type)
            for path in (store_path, backup_path, delivery_path):
                if not path.is_file() or path.stat().st_size != size or sha256_file(path) != digest:
                    raise DeliveryError("REGISTERED_ARTIFACT_MISSING", artifact_type)
            state["skipped_existing_registrations"] += 1
            atomic_json(state_path, state)
            continue
        copy_verified(source, store_path, digest, size)
        copy_verified(store_path, backup_path, digest, size)
        copy_verified(store_path, delivery_path, digest, size)
        registered[artifact_type] = {
            "artifact_id": f"owner-{req['package_id'].lower()}-{artifact_type}-{digest[:16]}",
            "artifact_type": artifact_type,
            "sha256": digest,
            "size_bytes": size,
            "private_storage_pointer": f"private-artifact://sha256/{digest}",
            "private_backup_pointer": f"private-backup://sha256/{digest}",
            "owner_delivery_pointer": f"private-owner-delivery://{req['channel_id']}/{req['package_id']}/{filename}",
            "restore_status": "NOT_RUN",
        }
        state["registered"] = registered
        new_registration_count += 1
        atomic_json(state_path, state)
        if inject_failure_after_registration and new_registration_count >= inject_failure_after_registration and len(registered) < len(outputs):
            token = secrets.token_hex(32)
            state["resume_token_hash"] = hashlib.sha256(token.encode()).hexdigest()
            atomic_json(state_path, state)
            raise RetryableDeliveryError("injected after bounded registration", token)

    registration = {
        "schema_version": REGISTRATION_SCHEMA, "request_id": req["request_id"], "package_id": req["package_id"], "channel_id": req["channel_id"], "idempotency_key": req["idempotency_key"],
        "authorized_heads": {"production_sha": req["authorized_inputs"]["production_sha"], "source_snapshot_sha": req["authorized_inputs"]["source_snapshot_sha"], "visual_runtime_head": req["authorized_inputs"]["visual_runtime_head"], "audio_timing_head": req["authorized_inputs"]["audio_timing_head"]},
        "input_manifest_git_blob_sha": req["authorized_inputs"]["input_manifest_git_blob_sha"], "registration_status": "PASS", "artifacts": [registered[k] for k in sorted(registered)], "artifact_count": len(registered),
        "owner_delivery_pointer": f"private-owner-delivery://{req['channel_id']}/{req['package_id']}", "auth_required": True, "auth_method": "local_capability_token_file_v1",
        "raw_private_paths_in_receipt": False, "private_content_public_exposure": False, "public_artifacts_created": False, "completed_at": clock(), "no_fake_green": True,
    }
    registration["receipt_hash"] = canonical_hash(registration)

    restore_root = private_root / "restore_scratch" / state_key
    restore_root.mkdir(parents=True, exist_ok=True)
    verified: list[dict[str, Any]] = []
    for record in registration["artifacts"]:
        artifact_type = record["artifact_type"]
        filename = artifact_filename(artifact_type, outputs[artifact_type])
        source = store_root / "sha256" / record["sha256"][:2] / record["sha256"] / filename
        restored = restore_root / filename
        copy_verified(source, restored, record["sha256"], record["size_bytes"])
        verified.append({"artifact_id": record["artifact_id"], "artifact_type": artifact_type, "sha256": record["sha256"], "size_bytes": record["size_bytes"], "restore_status": "PASS"})
        restored.unlink()
        record["restore_status"] = "PASS"
    restore_root.rmdir()
    restore = {"schema_version": RESTORE_SCHEMA, "request_id": req["request_id"], "registration_receipt_hash": registration["receipt_hash"], "restore_status": "PASS", "verified_artifacts": verified, "verified_artifact_count": len(verified), "cleanup_status": "PASS", "raw_private_paths_in_receipt": False, "private_content_public_exposure": False, "completed_at": clock(), "no_fake_green": True}
    restore["receipt_hash"] = canonical_hash(restore)
    registration["artifacts"] = [registered[k] for k in sorted(registered)]
    registration["receipt_hash"] = canonical_hash(registration, omit={"receipt_hash"})

    manifest_for_git = {"schema_version": MANIFEST_SCHEMA, "factory_id": FACTORY_ID, "request_id": req["request_id"], "package_id": req["package_id"], "channel_id": req["channel_id"], "owner_delivery_pointer": registration["owner_delivery_pointer"], "auth_required": True, "authorized_heads": registration["authorized_heads"], "artifacts": registration["artifacts"], "registration_receipt_hash": registration["receipt_hash"], "restore_receipt_hash": restore["receipt_hash"], "human_decision": None, "automatic_human_qc_green": False, "private_content_public_exposure": False, "public_artifacts_created": False, "no_fake_green": True}
    atomic_json(receipt_dir / "private_artifact_registration_receipt_v1.json", registration)
    atomic_json(receipt_dir / "private_artifact_restore_receipt_v1.json", restore)
    atomic_json(receipt_dir / "owner_delivery_manifest_for_git_v1.json", manifest_for_git)
    atomic_json(package_root / "owner_delivery_manifest_v1.json", manifest_for_git)
    state["completed"] = True
    state["resume_token_hash"] = None
    atomic_json(state_path, state)
    return registration, restore, manifest_for_git


def sanitized_summary(registration: Mapping[str, Any], restore: Mapping[str, Any]) -> None:
    print("PRIVATE_EXECUTOR_CONNECTED=true")
    print("OWNER_DELIVERY_CHANNEL=true")
    print("OWNER_DELIVERY_POINTER=" + str(registration["owner_delivery_pointer"]))
    print("REGISTERED_ARTIFACT_COUNT=" + str(registration["artifact_count"]))
    for item in registration["artifacts"]:
        print(f"ARTIFACT_{item['artifact_type']}_SHA256={item['sha256']}")
        print(f"ARTIFACT_{item['artifact_type']}_SIZE_BYTES={item['size_bytes']}")
    print("REGISTRATION_RECEIPT_HASH=" + str(registration["receipt_hash"]))
    print("RESTORE_RECEIPT_HASH=" + str(restore["receipt_hash"]))
    print("RESTORE_STATUS=" + str(restore["restore_status"]))
    print("PUBLIC_MEDIA_ARTIFACTS_CREATED=false")
    print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
    print("NO_FAKE_GREEN=true")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private owner delivery and content-addressed artifact store")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate-request")
    p.add_argument("--request", required=True)
    p = sub.add_parser("execute")
    p.add_argument("--request", required=True)
    p.add_argument("--production-dir", required=True)
    p.add_argument("--private-root", required=True)
    p.add_argument("--receipt-dir", required=True)
    p.add_argument("--resume-token")
    p.add_argument("--inject-failure-after-registration", type=int)
    args = parser.parse_args(argv)
    try:
        request = load_json(Path(args.request))
        if args.command == "validate-request":
            validate_request(request)
            print("REQUEST_VALID=true")
            print("PUBLIC_WORKFLOW_EXECUTION_ALLOWED=false")
            print("PUBLIC_ARTIFACT_UPLOAD_ALLOWED=false")
            print("NO_FAKE_GREEN=true")
            return 0
        registration, restore, _manifest = execute_request(request, Path(args.production_dir), Path(args.private_root), Path(args.receipt_dir), resume_token=args.resume_token, inject_failure_after_registration=args.inject_failure_after_registration)
        sanitized_summary(registration, restore)
        return 0
    except RetryableDeliveryError as exc:
        print("RESULT=RETRYABLE_FAILURE")
        print("FAILURE_CLASS=PRIVATE_DELIVERY_RETRYABLE_FAILURE")
        print("RESUME_TOKEN=" + exc.resume_token)
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return RETRY_EXIT
    except DeliveryError as exc:
        print("RESULT=FAIL")
        print("FAILURE_CLASS=" + exc.code)
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
