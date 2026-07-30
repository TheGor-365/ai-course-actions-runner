#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
DRIVE = re.compile(r"^[A-Za-z]:")
MODES = ("validate-only", "compile", "pre-render-evidence", "render")
MODE_RANK = {mode: rank for rank, mode in enumerate(MODES)}
SENSITIVE_MARKERS = (
    "x-access-token:", "github_pat_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_",
    "BEGIN PRIVATE KEY", "-----BEGIN", "PRIVATE_REPO_PAT", "raw_provider_payload",
    "private_repository_archive", "client_private_media", "sk-proj-", "sk-live-", "AKIA",
)
PRIVATE_PATH_MARKERS = (
    "/.git/", ".git/", "private_repository_archive", "raw_provider_payload",
    "client_private_media", "private_media/", "private_media",
)


class RunnerError(ValueError):
    pass


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RunnerError(f"JSON_DUPLICATE_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"JSON_INVALID:{path}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_keys(value: Mapping[str, Any], keys: Iterable[str], context: str) -> None:
    missing = sorted(set(keys) - set(value))
    if missing:
        raise RunnerError(f"{context}_MISSING_KEYS:{','.join(missing)}")


def require_sha40(value: Any, code: str) -> str:
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise RunnerError(code)
    return value


def require_sha64(value: Any, code: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise RunnerError(code)
    return value


def require_relpath(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value or DRIVE.match(value):
        raise RunnerError(code)
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise RunnerError(code)
    return path.as_posix()


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunnerError("AUTHORIZATION_EXPIRY_INVALID") from exc
    if parsed.tzinfo is None:
        raise RunnerError("AUTHORIZATION_EXPIRY_TIMEZONE_REQUIRED")
    return parsed.astimezone(timezone.utc)


def scan_sensitive(path: str, data: bytes) -> None:
    lower = path.lower()
    if any(marker in lower for marker in PRIVATE_PATH_MARKERS):
        raise RunnerError(f"PRIVATE_PAYLOAD_PATH_FORBIDDEN:{path}")
    text = data.decode("utf-8", errors="ignore")
    for marker in SENSITIVE_MARKERS:
        if marker in text:
            raise RunnerError(f"SENSITIVE_MARKER_FORBIDDEN:{path}:{marker}")


def consume_single_use(identity: str, ledger: Path) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    existing = set(ledger.read_text(encoding="utf-8").splitlines()) if ledger.exists() else set()
    if identity in existing:
        raise RunnerError("AUTHORIZATION_SINGLE_USE_ALREADY_CONSUMED")
    tmp = ledger.with_name(f".{ledger.name}.{os.getpid()}.tmp")
    tmp.write_text("".join(f"{item}\n" for item in sorted(existing | {identity})), encoding="utf-8")
    os.replace(tmp, ledger)
