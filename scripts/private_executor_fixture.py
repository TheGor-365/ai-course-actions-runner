#!/usr/bin/env python3
"""Deterministic private-executor fixture for retry/resume and restore proofs.

This fixture never publishes media or private paths. It materializes bytes only in a
caller-provided private work directory and emits a sanitized JSON receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request")
    parser.add_argument("work_dir")
    parser.add_argument("--inject-retryable-failure", action="store_true")
    args = parser.parse_args()

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    work_dir = Path(args.work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    state_path = work_dir / "state.json"
    started = now()

    state = json.loads(state_path.read_text()) if state_path.exists() else {"completed": []}
    station_id = request["station_id"]
    already_completed = station_id in state["completed"]

    if args.inject_retryable_failure and not already_completed:
        token = hashlib.sha256(request["idempotency_key"].encode()).hexdigest()[:24]
        receipt = {
            "schema_version": "PRIVATE_EXECUTOR_RECEIPT_v1",
            "request_id": request["request_id"],
            "station_id": station_id,
            "attempt_id": request["attempt_id"],
            "executor_id": "fixture-private-executor",
            "runtime_lock_id": request["runtime_lock_id"],
            "started_at": started,
            "completed_at": now(),
            "exit_code": 75,
            "result": "FAIL",
            "failure_class": "STATION_RETRYABLE_FAILURE",
            "retryable": True,
            "output_artifacts": [],
            "sanitized_metrics": {"completed_station_reused": False},
            "resume_token_optional": token,
            "cleanup_status": "PASS",
            "private_content_public_exposure": False,
        }
        print(json.dumps(receipt, sort_keys=True))
        return 75

    artifact = work_dir / "fixture-artifact.bin"
    if not already_completed:
        artifact.write_bytes((request["input_hash"] + "\n").encode("ascii"))
        state["completed"].append(station_id)
        state_path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    backup = work_dir / "backup" / artifact.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact, backup)
    restore = work_dir / "restore" / artifact.name
    restore.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, restore)
    digest = sha256(artifact)
    if sha256(restore) != digest:
        raise SystemExit("RESTORE_FAILED")

    pointer = {
        "artifact_id": "fixture-artifact-v1",
        "package_request_id": request["package_request_id"],
        "station_id": station_id,
        "artifact_type": request["output_artifact_types"][0],
        "sha256": digest,
        "size_bytes": artifact.stat().st_size,
        "codec_or_format": "fixture-binary",
        "duration_ms_optional": None,
        "private_storage_pointer": "private://fixture-store/fixture-artifact-v1",
        "producer_version": "private-executor-fixture-v1",
        "created_at": now(),
        "backup_pointer_optional": "private://fixture-backup/fixture-artifact-v1",
        "restore_status": "PASS",
        "QC_identity_optional": None,
    }
    receipt = {
        "schema_version": "PRIVATE_EXECUTOR_RECEIPT_v1",
        "request_id": request["request_id"],
        "station_id": station_id,
        "attempt_id": request["attempt_id"],
        "executor_id": "fixture-private-executor",
        "runtime_lock_id": request["runtime_lock_id"],
        "started_at": started,
        "completed_at": now(),
        "exit_code": 0,
        "result": "PASS",
        "failure_class": None,
        "retryable": False,
        "output_artifacts": [pointer],
        "sanitized_metrics": {"completed_station_reused": already_completed, "restore_sha_match": True},
        "resume_token_optional": None,
        "cleanup_status": "PASS",
        "private_content_public_exposure": False,
    }
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
