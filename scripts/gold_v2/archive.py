#!/usr/bin/env python3
from __future__ import annotations

import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .common import RunnerError, require_relpath, scan_sensitive, sha256_bytes, sha256_file


@dataclass(frozen=True)
class ArchivePolicy:
    expected_files: frozenset[str]
    receipt_schemas: Mapping[str, str]
    expected_archive_sha256: str | None = None
    checksums_path: str = "SHA256SUMS"
    max_file_count: int = 4096
    max_member_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 512 * 1024 * 1024
    max_compression_ratio: float = 200.0
    forbidden_suffixes: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.checksums_path not in self.expected_files:
            raise RunnerError("ARCHIVE_POLICY_CHECKSUMS_NOT_EXPECTED")
        if not self.receipt_schemas or not set(self.receipt_schemas).issubset(self.expected_files):
            raise RunnerError("ARCHIVE_POLICY_RECEIPT_SCHEMA_INVALID")
        if min(self.max_file_count, self.max_member_bytes, self.max_total_bytes) <= 0:
            raise RunnerError("ARCHIVE_POLICY_LIMIT_INVALID")
        if self.max_compression_ratio <= 1:
            raise RunnerError("ARCHIVE_POLICY_RATIO_INVALID")


def _member_kind(info: zipfile.ZipInfo) -> str:
    mode = (info.external_attr >> 16) & 0xFFFF
    kind = stat.S_IFMT(mode)
    if info.is_dir():
        if kind not in (0, stat.S_IFDIR):
            raise RunnerError(f"ARCHIVE_DIRECTORY_MODE_INVALID:{info.filename}")
        return "directory"
    if kind in (0, stat.S_IFREG):
        return "file"
    if kind == stat.S_IFLNK:
        raise RunnerError(f"ARCHIVE_SYMLINK_FORBIDDEN:{info.filename}")
    raise RunnerError(f"ARCHIVE_SPECIAL_FILE_FORBIDDEN:{info.filename}")


def _parse_checksums(data: bytes) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerError("SHA256SUMS_NOT_UTF8") from exc
    result: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        if "  " not in line:
            raise RunnerError(f"SHA256SUMS_LINE_INVALID:{number}")
        digest, raw_name = line.split("  ", 1)
        name = require_relpath(raw_name, f"SHA256SUMS_PATH_INVALID:{number}")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise RunnerError(f"SHA256SUMS_DIGEST_INVALID:{number}")
        if name in result:
            raise RunnerError(f"SHA256SUMS_DUPLICATE:{name}")
        result[name] = digest
    if not result:
        raise RunnerError("SHA256SUMS_EMPTY")
    return result


def inspect_archive(path: Path, policy: ArchivePolicy) -> dict:
    if not path.is_file():
        raise RunnerError("ARCHIVE_MISSING")
    archive_sha = sha256_file(path)
    if policy.expected_archive_sha256 and archive_sha != policy.expected_archive_sha256:
        raise RunnerError("ARCHIVE_SHA256_MISMATCH")

    files: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos:
            raise RunnerError("ARCHIVE_EMPTY")
        if len(infos) > policy.max_file_count:
            raise RunnerError("ARCHIVE_FILE_COUNT_EXCEEDED")
        seen: set[str] = set()
        for info in infos:
            raw = info.filename.rstrip("/") if info.is_dir() else info.filename
            name = require_relpath(raw, "ARCHIVE_MEMBER_PATH_UNSAFE")
            if name in seen:
                raise RunnerError(f"ARCHIVE_DUPLICATE_MEMBER:{name}")
            seen.add(name)
            if info.flag_bits & 0x1:
                raise RunnerError(f"ARCHIVE_ENCRYPTED_MEMBER_FORBIDDEN:{name}")
            if _member_kind(info) == "directory":
                continue
            if Path(name).suffix.lower() in policy.forbidden_suffixes:
                raise RunnerError(f"ARCHIVE_SUFFIX_FORBIDDEN:{name}")
            if info.file_size > policy.max_member_bytes:
                raise RunnerError(f"ARCHIVE_MEMBER_TOO_LARGE:{name}")
            total += info.file_size
            if total > policy.max_total_bytes:
                raise RunnerError("ARCHIVE_TOTAL_TOO_LARGE")
            if info.file_size / max(info.compress_size, 1) > policy.max_compression_ratio:
                raise RunnerError(f"ARCHIVE_COMPRESSION_RATIO_EXCEEDED:{name}")
            data = archive.read(info)
            if len(data) != info.file_size:
                raise RunnerError(f"ARCHIVE_MEMBER_SIZE_MISMATCH:{name}")
            scan_sensitive(name, data)
            files[name] = data

    observed = frozenset(files)
    if policy.checksums_path not in files:
        raise RunnerError("SHA256SUMS_MISSING")
    if observed != policy.expected_files:
        missing = sorted(policy.expected_files - observed)
        extra = sorted(observed - policy.expected_files)
        raise RunnerError(f"ARCHIVE_EXACT_FILE_SET_MISMATCH:missing={missing}:extra={extra}")
    checksums = _parse_checksums(files[policy.checksums_path])
    if set(checksums) != set(policy.expected_files) - {policy.checksums_path}:
        raise RunnerError("SHA256SUMS_EXACT_FILE_SET_MISMATCH")
    for name, digest in checksums.items():
        if sha256_bytes(files[name]) != digest:
            raise RunnerError(f"SHA256SUMS_IDENTITY_FAILED:{name}")
    for receipt_path, schema in policy.receipt_schemas.items():
        try:
            value = json.loads(files[receipt_path].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RunnerError(f"RECEIPT_JSON_INVALID:{receipt_path}") from exc
        if not isinstance(value, dict) or value.get("schema_version") != schema:
            raise RunnerError(f"RECEIPT_SCHEMA_MISMATCH:{receipt_path}")
    return {
        "schema_version": "gold_v2_runner_archive_security_receipt.v1",
        "result": "PASS",
        "archive_sha256": archive_sha,
        "regular_file_count": len(files),
        "checksums_entry_count": len(checksums),
        "archive_traversal_acceptance_count": 0,
        "symlink_or_special_file_acceptance_count": 0,
        "encrypted_entry_acceptance_count": 0,
        "exact_artifact_file_set_enforced": True,
        "missing_sha256sums_acceptance_count": 0,
        "secret_or_private_payload_acceptance_count": 0,
        "file_sha256": {name: sha256_bytes(data) for name, data in sorted(files.items())},
        "no_fake_green": True,
    }


def deterministic_zip(root: Path, destination: Path, exact_files: list[str]) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(exact_files):
            relative = require_relpath(relative, "ZIP_SOURCE_PATH_INVALID")
            source = root / relative
            if not source.is_file() or source.is_symlink():
                raise RunnerError(f"ZIP_SOURCE_REGULAR_FILE_REQUIRED:{relative}")
            data = source.read_bytes()
            scan_sensitive(relative, data)
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    return sha256_file(destination)
