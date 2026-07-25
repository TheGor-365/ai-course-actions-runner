#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

RETRY_EXIT = 75
PROFILE_ID = "ALIGNMENT_MODEL_RU_WAV2VEC2_V1"
MODEL_REPO = "jonatasgrosman/wav2vec2-large-xlsr-53-russian"
MODEL_REVISION = "2329100508896c6d9b157019803ab5601e6f3406"
RUNTIME_LOCK_ID = "ru-alignment-wav2vec2-23291005-v1"


class ProvisionError(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitized(receipt: dict) -> None:
    print("profile_id=" + receipt["profile_id"])
    print("result=" + receipt["result"])
    print("retryable=" + str(receipt["retryable"]).lower())
    print("bytes_total=" + str(receipt["bytes_total"]))
    print("bytes_transferred_this_attempt=" + str(receipt["bytes_transferred_this_attempt"]))
    print("resume_offset=" + str(receipt["resume_offset"]))
    if receipt.get("sha256"):
        print("sha256=" + receipt["sha256"])
    print("private_content_public_exposure=false")
    print("public_artifacts_created=false")


def resume_copy(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    destination = Path(args.destination).resolve()
    receipt_path = Path(args.receipt).resolve()
    if not source.is_file():
        raise ProvisionError("source_missing")
    if source == destination:
        raise ProvisionError("source_destination_same")
    total = source.stat().st_size
    destination.parent.mkdir(parents=True, exist_ok=True)
    offset = destination.stat().st_size if destination.exists() else 0
    if offset > total:
        raise ProvisionError("destination_larger_than_source")
    if offset:
        with source.open("rb") as expected, destination.open("rb") as observed:
            remaining = offset
            while remaining:
                size = min(1024 * 1024, remaining)
                if expected.read(size) != observed.read(size):
                    raise ProvisionError("partial_prefix_mismatch")
                remaining -= size

    limit = total
    if args.interrupt_after_bytes is not None and offset < total:
        if args.interrupt_after_bytes < 1:
            raise ProvisionError("invalid_interrupt_after_bytes")
        limit = min(total, offset + args.interrupt_after_bytes)

    transferred = 0
    with source.open("rb") as src, destination.open("ab") as dst:
        src.seek(offset)
        remaining = limit - offset
        while remaining:
            chunk = src.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            dst.write(chunk)
            transferred += len(chunk)
            remaining -= len(chunk)
        dst.flush()
        os.fsync(dst.fileno())

    completed = destination.stat().st_size == total
    receipt = {
        "schema_version": "alignment-model-provisioning-receipt-v1",
        "profile_id": PROFILE_ID,
        "runtime_lock_id": RUNTIME_LOCK_ID,
        "started_at": now(),
        "completed_at": now(),
        "result": "PASS" if completed else "RETRYABLE_FAILURE",
        "failure_class": "NONE" if completed else "DOWNLOAD_INTERRUPTED",
        "retryable": not completed,
        "bytes_total": total,
        "bytes_transferred_this_attempt": transferred,
        "resume_offset": offset,
        "sha256": sha256_file(destination) if completed else None,
        "private_cache_pointer": "private-cache://alignment-model/ru-wav2vec2-v1",
        "private_content_public_exposure": False,
        "public_artifacts_created": False,
    }
    if completed and args.expected_sha256 and receipt["sha256"] != args.expected_sha256:
        receipt.update({
            "result": "TERMINAL_FAILURE",
            "failure_class": "ARTIFACT_HASH_MISMATCH",
            "retryable": False,
        })
        write_json(receipt_path, receipt)
        sanitized(receipt)
        return 2
    write_json(receipt_path, receipt)
    sanitized(receipt)
    return 0 if completed else RETRY_EXIT


def provision_hf(args: argparse.Namespace) -> int:
    receipt_path = Path(args.receipt).resolve()
    cache_dir = Path(args.cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ProvisionError("huggingface_hub_not_installed") from exc
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    snapshot = Path(snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        cache_dir=str(cache_dir),
        max_workers=1,
    ))
    files = sorted(path for path in snapshot.rglob("*") if path.is_file())
    if not files:
        raise ProvisionError("snapshot_empty")
    inventory = []
    total = 0
    for path in files:
        size = path.stat().st_size
        total += size
        inventory.append({
            "relative_path_hash": hashlib.sha256(path.relative_to(snapshot).as_posix().encode()).hexdigest(),
            "size_bytes": size,
            "sha256": sha256_file(path),
        })
    inventory_hash = hashlib.sha256(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt = {
        "schema_version": "alignment-model-provisioning-receipt-v1",
        "profile_id": PROFILE_ID,
        "runtime_lock_id": RUNTIME_LOCK_ID,
        "model_repo": MODEL_REPO,
        "model_revision": MODEL_REVISION,
        "result": "PASS",
        "failure_class": "NONE",
        "retryable": False,
        "bytes_total": total,
        "bytes_transferred_this_attempt": total,
        "resume_offset": 0,
        "file_count": len(files),
        "snapshot_inventory_hash": inventory_hash,
        "private_cache_pointer": "private-cache://alignment-model/ru-wav2vec2-v1",
        "private_content_public_exposure": False,
        "public_artifacts_created": False,
        "created_at": now(),
    }
    write_json(receipt_path, receipt)
    print("profile_id=" + PROFILE_ID)
    print("model_revision=" + MODEL_REVISION)
    print("result=PASS")
    print("file_count=" + str(len(files)))
    print("bytes_total=" + str(total))
    print("snapshot_inventory_hash=" + inventory_hash)
    print("private_content_public_exposure=false")
    print("public_artifacts_created=false")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    fixture = sub.add_parser("resume-copy-fixture")
    fixture.add_argument("--source", required=True)
    fixture.add_argument("--destination", required=True)
    fixture.add_argument("--receipt", required=True)
    fixture.add_argument("--expected-sha256")
    fixture.add_argument("--interrupt-after-bytes", type=int)
    locked = sub.add_parser("provision-locked-model")
    locked.add_argument("--cache-dir", required=True)
    locked.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        if args.command == "resume-copy-fixture":
            return resume_copy(args)
        if args.command == "provision-locked-model":
            return provision_hf(args)
        raise ProvisionError("unknown_command")
    except (OSError, ProvisionError, ValueError) as exc:
        print("profile_id=" + PROFILE_ID)
        print("result=TERMINAL_FAILURE")
        print("failure_class=PROVISIONING_CONTRACT_FAILURE")
        print("retryable=false")
        print("error_code=" + str(exc).split(":", 1)[0])
        print("private_content_public_exposure=false")
        print("public_artifacts_created=false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
