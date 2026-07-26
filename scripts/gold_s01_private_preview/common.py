#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

PROFILE_ID = "M1_L01_S01_RU_GOLD_V2_PRIVATE_PREVIEW_V1"
REQUEST_SCHEMA = "GoldS01PrivatePreviewRequest_v1"
HOST_RECEIPT_SCHEMA = "GoldS01HostLockReceipt_v1"
STORE_PROBE_RECEIPT_SCHEMA = "GoldS01StoreProbeReceipt_v1"
REBIND_RECEIPT_SCHEMA = "GoldS01RequestRebindReceipt_v1"
AUTHORITY_MAP_SCHEMA = "GoldS01LiveAuthorityMap_v1"
STATION_RECEIPT_SCHEMA = "GoldS01StationRunReceipt_v1"
ARTIFACT_RECEIPT_SCHEMA = "GoldS01ArtifactReceipt_v1"
REGISTRATION_SCHEMA = "GoldS01PrimaryRegistrationReceipt_v1"
REPLICA_SCHEMA = "GoldS01ReplicaReceipt_v1"
RESTORE_SCHEMA = "GoldS01RestoreReceipt_v1"
OWNER_MANIFEST_SCHEMA = "GoldS01OwnerDeliveryManifest_v1"
RETRY_EXIT = 75
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,180}$")
SAFE_REL = re.compile(r"^[A-Za-z0-9._/-]+$")
MEDIA_EXTENSIONS = {".wav", ".mp3", ".flac", ".mp4", ".mov", ".webm", ".mkv", ".png", ".jpg", ".jpeg"}
A3483_SHA256 = "74d9a9008b594bd8bd18f001d05542e249bd9af371c32e87181a0df42064f352"
DEFAULT_PRIMARY_CLASS = "private-content-addressed-primary-v1"
DEFAULT_REPLICA_CLASS = "private-content-addressed-replica-v1"
DEFAULT_OWNER_CLASS = "private-owner-review-local-capability-v1"
CONTROL_BINDING_MODE = "external-exact-head-request-blob-v1"


class PreviewError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class RetryablePreviewError(PreviewError):
    def __init__(self, station: str, token: str) -> None:
        super().__init__("RETRYABLE_STATION_FAILURE", station)
        self.station = station
        self.token = token


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value: Mapping[str, Any], *, omit: set[str] | None = None) -> str:
    omitted = omit or set()
    return hashlib.sha256(canonical_bytes({k: copy.deepcopy(v) for k, v in value.items() if k not in omitted})).hexdigest()


def validate_embedded_hash(value: Mapping[str, Any], field: str = "receipt_hash") -> None:
    observed = value.get(field)
    require_hex(observed, 64, field)
    expected = canonical_hash(value, omit={field})
    if observed != expected:
        raise PreviewError("RECEIPT_HASH_MISMATCH", field)


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
        raise PreviewError("JSON_INVALID", path.name) from exc
    if not isinstance(value, dict):
        raise PreviewError("JSON_ROOT_INVALID", path.name)
    return value


def atomic_json(path: Path, value: Mapping[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def safe_relative(value: Any, field: str) -> str:
    text = str(value)
    if not SAFE_REL.fullmatch(text) or text.startswith("/") or ".." in Path(text).parts:
        raise PreviewError("UNSAFE_RELATIVE_PATH", field)
    return text


def require_hex(value: Any, length: int, field: str) -> str:
    text = str(value)
    matcher = HEX40 if length == 40 else HEX64
    if not matcher.fullmatch(text):
        raise PreviewError("IDENTITY_INVALID", field)
    return text


def require_fields(value: Mapping[str, Any], fields: set[str], field: str) -> None:
    missing = sorted(fields - set(value))
    if missing:
        raise PreviewError("FIELDS_MISSING", f"{field}:{','.join(missing)}")


def scan_forbidden_keys(value: Any, path: str = "request") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in {"command", "commands", "script_path", "shell", "provider_payload", "secret", "token"}:
                raise PreviewError("DYNAMIC_EXECUTION_FIELD_FORBIDDEN", f"{path}.{key}")
            scan_forbidden_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_forbidden_keys(item, f"{path}[{index}]")


def git_output(repo: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        raise PreviewError("GIT_CHECK_FAILED", exc.output[-300:]) from exc


def validate_git_checkout(repo: Path, expected_sha: str, *, clean: bool = True) -> None:
    if git_output(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise PreviewError("CHECKOUT_INVALID", repo.name)
    if git_output(repo, "rev-parse", "HEAD") != expected_sha:
        raise PreviewError("EXACT_HEAD_DRIFT", expected_sha)
    if clean and git_output(repo, "status", "--porcelain"):
        raise PreviewError("CHECKOUT_DIRTY", repo.name)


def validate_ancestor(repo: Path, ancestor_sha: str, head_sha: str) -> None:
    try:
        subprocess.check_call(["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor_sha, head_sha], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        raise PreviewError("CONTROL_BASE_NOT_ANCESTOR", ancestor_sha) from exc


def validate_blob(repo: Path, path: str, expected_blob: str, expected_sha256: str | None = None) -> Path:
    safe_relative(path, "blob.path")
    target = repo / path
    if not target.is_file():
        raise PreviewError("BOUND_FILE_MISSING", path)
    observed_blob = git_output(repo, "hash-object", str(target))
    if observed_blob != expected_blob:
        raise PreviewError("BOUND_BLOB_MISMATCH", path)
    if expected_sha256 and sha256_file(target) != expected_sha256:
        raise PreviewError("BOUND_SHA256_MISMATCH", path)
    return target
