#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

HEX64 = re.compile(r"^[0-9a-f]{64}$")
DRIVE = re.compile(r"^[A-Za-z]:")
DEFAULT_SENSITIVE_MARKERS = (
    "x-access-token:",
    "github_pat_",
    "ghp_",
    "BEGIN PRIVATE KEY",
    "PRIVATE_REPO_PAT",
    "raw_provider_payload",
    "private_repository_archive",
)


class ArchiveSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class ArchivePolicy:
    expected_files: frozenset[str]
    receipt_schemas: Mapping[str, str]
    expected_archive_sha256: str | None = None
    checksums_path: str = "SHA256SUMS"
    max_member_bytes: int = 32 * 1024 * 1024
    max_total_bytes: int = 128 * 1024 * 1024
    max_compression_ratio: float = 200.0
    forbidden_suffixes: frozenset[str] = frozenset()
    sensitive_markers: Sequence[str] = DEFAULT_SENSITIVE_MARKERS

    def __post_init__(self) -> None:
        if self.checksums_path not in self.expected_files:
            raise ArchiveSecurityError("POLICY_CHECKSUMS_PATH_NOT_EXPECTED")
        if not self.receipt_schemas:
            raise ArchiveSecurityError("POLICY_RECEIPT_SCHEMAS_REQUIRED")
        if not set(self.receipt_schemas).issubset(self.expected_files):
            raise ArchiveSecurityError("POLICY_RECEIPT_PATH_NOT_EXPECTED")
        if self.expected_archive_sha256 is not None and not HEX64.fullmatch(self.expected_archive_sha256):
            raise ArchiveSecurityError("POLICY_ARCHIVE_SHA256_INVALID")
        if self.max_member_bytes <= 0 or self.max_total_bytes <= 0 or self.max_compression_ratio <= 1:
            raise ArchiveSecurityError("POLICY_LIMIT_INVALID")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_member(name: str) -> str:
    if not name or "\x00" in name or "\\" in name or DRIVE.match(name):
        raise ArchiveSecurityError(f"ARCHIVE_MEMBER_NAME_UNSAFE:{name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ArchiveSecurityError(f"ARCHIVE_MEMBER_PATH_TRAVERSAL:{name}")
    normalized = path.as_posix()
    if normalized.startswith("/"):
        raise ArchiveSecurityError(f"ARCHIVE_MEMBER_ABSOLUTE:{name}")
    return normalized


def member_kind(info: zipfile.ZipInfo) -> str:
    mode = (info.external_attr >> 16) & 0xFFFF
    kind = stat.S_IFMT(mode)
    if info.is_dir():
        if kind not in (0, stat.S_IFDIR):
            raise ArchiveSecurityError(f"ARCHIVE_DIRECTORY_MODE_INVALID:{info.filename}")
        return "directory"
    if kind in (0, stat.S_IFREG):
        return "file"
    if kind == stat.S_IFLNK:
        raise ArchiveSecurityError(f"ARCHIVE_SYMLINK_FORBIDDEN:{info.filename}")
    raise ArchiveSecurityError(f"ARCHIVE_SPECIAL_FILE_FORBIDDEN:{info.filename}:{oct(kind)}")


def parse_checksums(data: bytes, checksums_path: str) -> dict[str, str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArchiveSecurityError(f"SHA256SUMS_NOT_UTF8:{checksums_path}") from exc
    result: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        if "  " not in line:
            raise ArchiveSecurityError(f"SHA256SUMS_LINE_INVALID:{line_number}")
        digest, raw_name = line.split("  ", 1)
        name = normalize_member(raw_name)
        if not HEX64.fullmatch(digest):
            raise ArchiveSecurityError(f"SHA256SUMS_DIGEST_INVALID:{line_number}")
        if name in result:
            raise ArchiveSecurityError(f"SHA256SUMS_DUPLICATE:{name}")
        result[name] = digest
    if not result:
        raise ArchiveSecurityError("SHA256SUMS_EMPTY")
    return result


def scan_sensitive(path: str, data: bytes, markers: Sequence[str]) -> None:
    lower_path = path.lower()
    if any(token in lower_path for token in ("/.git/", ".git/", "private_repository_archive", "raw_provider_payload")):
        raise ArchiveSecurityError(f"PRIVATE_PAYLOAD_PATH_FORBIDDEN:{path}")
    if len(data) > 4 * 1024 * 1024:
        return
    text = data.decode("utf-8", errors="ignore")
    for marker in markers:
        if marker and marker in text:
            raise ArchiveSecurityError(f"SENSITIVE_MARKER_FORBIDDEN:{path}:{marker}")


def inspect_archive(archive_path: Path, policy: ArchivePolicy) -> tuple[dict, dict[str, bytes]]:
    archive_path = Path(archive_path)
    if not archive_path.is_file():
        raise ArchiveSecurityError("ARCHIVE_MISSING")
    archive_sha = sha256_file(archive_path)
    if policy.expected_archive_sha256 is not None and archive_sha != policy.expected_archive_sha256:
        raise ArchiveSecurityError("ARCHIVE_SHA256_MISMATCH")

    files: dict[str, bytes] = {}
    directories: set[str] = set()
    total_uncompressed = 0
    with zipfile.ZipFile(archive_path) as archive:
        infos = archive.infolist()
        if not infos:
            raise ArchiveSecurityError("ARCHIVE_EMPTY")
        normalized_seen: set[str] = set()
        for info in infos:
            name = normalize_member(info.filename.rstrip("/") if info.is_dir() else info.filename)
            if name in normalized_seen:
                raise ArchiveSecurityError(f"ARCHIVE_DUPLICATE_MEMBER:{name}")
            normalized_seen.add(name)
            kind = member_kind(info)
            if info.flag_bits & 0x1:
                raise ArchiveSecurityError(f"ARCHIVE_ENCRYPTED_MEMBER_FORBIDDEN:{name}")
            if kind == "directory":
                directories.add(name)
                continue
            if Path(name).suffix.lower() in policy.forbidden_suffixes:
                raise ArchiveSecurityError(f"ARCHIVE_SUFFIX_FORBIDDEN:{name}")
            if info.file_size > policy.max_member_bytes:
                raise ArchiveSecurityError(f"ARCHIVE_MEMBER_TOO_LARGE:{name}")
            total_uncompressed += info.file_size
            if total_uncompressed > policy.max_total_bytes:
                raise ArchiveSecurityError("ARCHIVE_TOTAL_TOO_LARGE")
            compressed = max(info.compress_size, 1)
            if info.file_size / compressed > policy.max_compression_ratio:
                raise ArchiveSecurityError(f"ARCHIVE_COMPRESSION_RATIO_EXCEEDED:{name}")
            data = archive.read(info)
            if len(data) != info.file_size:
                raise ArchiveSecurityError(f"ARCHIVE_MEMBER_SIZE_MISMATCH:{name}")
            scan_sensitive(name, data, policy.sensitive_markers)
            files[name] = data

    observed = frozenset(files)
    if policy.checksums_path not in files:
        raise ArchiveSecurityError("SHA256SUMS_MISSING")
    if observed != policy.expected_files:
        missing = sorted(policy.expected_files - observed)
        extra = sorted(observed - policy.expected_files)
        raise ArchiveSecurityError(f"ARCHIVE_EXACT_FILE_SET_MISMATCH:missing={missing}:extra={extra}")

    checksums = parse_checksums(files[policy.checksums_path], policy.checksums_path)
    expected_checksum_files = policy.expected_files - {policy.checksums_path}
    if set(checksums) != expected_checksum_files:
        raise ArchiveSecurityError("SHA256SUMS_EXACT_FILE_SET_MISMATCH")
    for name, expected in checksums.items():
        if sha256_bytes(files[name]) != expected:
            raise ArchiveSecurityError(f"SHA256SUMS_IDENTITY_FAILED:{name}")

    for receipt_path, expected_schema in policy.receipt_schemas.items():
        try:
            receipt = json.loads(files[receipt_path].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ArchiveSecurityError(f"RECEIPT_JSON_INVALID:{receipt_path}") from exc
        if not isinstance(receipt, dict):
            raise ArchiveSecurityError(f"RECEIPT_OBJECT_REQUIRED:{receipt_path}")
        if receipt.get("schema_version") != expected_schema:
            raise ArchiveSecurityError(f"RECEIPT_SCHEMA_MISMATCH:{receipt_path}")

    receipt = {
        "schema_version": "gold_v2_diamond_artifact_security_receipt.v1",
        "result": "PASS",
        "archive_sha256": archive_sha,
        "regular_file_count": len(files),
        "checksums_entry_count": len(checksums),
        "archive_traversal_acceptance_count": 0,
        "symlink_or_special_file_acceptance_count": 0,
        "exact_artifact_file_set_enforced": True,
        "missing_sha256sums_acceptance_count": 0,
        "receipt_without_schema_acceptance_count": 0,
        "secret_or_private_payload_acceptance_count": 0,
        "extracted_file_sha256": {name: sha256_bytes(data) for name, data in sorted(files.items())},
        "no_fake_green": True,
    }
    return receipt, files


def extract_verified_archive(archive_path: Path, output_dir: Path, policy: ArchivePolicy) -> dict:
    receipt, files = inspect_archive(archive_path, policy)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ArchiveSecurityError("OUTPUT_DIRECTORY_ALREADY_EXISTS")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".gold-v2-diamond-", dir=output_dir.parent))
    try:
        for name, data in sorted(files.items()):
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(data)
        os.replace(stage, output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return receipt
