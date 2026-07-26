#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ALLOWED_DECISIONS = ("ACCEPT", "REPAIR_REQUIRED", "REJECT")


class OwnerReviewError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value: Mapping[str, Any], omit: set[str] | None = None) -> str:
    omitted = omit or set()
    return hashlib.sha256(canonical_bytes({k: v for k, v in value.items() if k not in omitted})).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OwnerReviewError("JSON_ROOT_INVALID")
    return value


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.STDOUT).strip()


def verify_checkout(repo: Path, expected: str) -> None:
    if git(repo, "rev-parse", "HEAD") != expected:
        raise OwnerReviewError("EXACT_HEAD_DRIFT")
    if git(repo, "status", "--porcelain"):
        raise OwnerReviewError("CHECKOUT_DIRTY")


def verify_receipt(value: Mapping[str, Any]) -> None:
    if value.get("receipt_hash") != canonical_hash(value, {"receipt_hash"}):
        raise OwnerReviewError("RECEIPT_HASH_MISMATCH")
    serialized = json.dumps(value)
    if "file://" in serialized or "/home/" in serialized:
        raise OwnerReviewError("RAW_PATH_DISCLOSURE")


def resolve_preview(private_root: Path, manifest: Mapping[str, Any]) -> Path:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise OwnerReviewError("OWNER_MANIFEST_ARTIFACTS_INVALID")
    item = next((row for row in artifacts if row.get("artifact_type") == "ru_preview"), None)
    if not item:
        raise OwnerReviewError("RU_PREVIEW_NOT_REGISTERED")
    digest = str(item["sha256"])
    filename = str(item["owner_pointer"]).rsplit("/", 1)[-1]
    target = private_root / "gold_s01_owner_delivery_v1" / str(manifest["request_id"]) / filename
    if not target.is_file() or target.stat().st_size != item["size_bytes"]:
        raise OwnerReviewError("RU_PREVIEW_LOCAL_FILE_MISSING")
    observed = hashlib.sha256(target.read_bytes()).hexdigest()
    if observed != digest:
        raise OwnerReviewError("RU_PREVIEW_LOCAL_HASH_MISMATCH")
    return target


def choose_player() -> str:
    for command in ("mpv", "vlc", "xdg-open"):
        if shutil.which(command):
            return command
    raise OwnerReviewError("LOCAL_PLAYER_UNAVAILABLE")


def write_decision(path: Path, request_id: str, manifest_hash: str, decision: str) -> dict[str, Any]:
    if decision not in ALLOWED_DECISIONS:
        raise OwnerReviewError("DECISION_TOKEN_INVALID")
    receipt = {
        "schema_version": "GoldS01LocalOwnerDecisionReceipt_v1",
        "request_id": request_id,
        "owner_manifest_hash": manifest_hash,
        "decision_token": decision,
        "human_final_preview_accepted": decision == "ACCEPT",
        "local_only": True,
        "github_write_performed": False,
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "no_fake_green": True,
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open the private Gold S01 RU preview and record an explicit local owner decision")
    parser.add_argument("--runner-dir", required=True)
    parser.add_argument("--runner-sha", required=True)
    parser.add_argument("--control-dir", required=True)
    parser.add_argument("--control-sha", required=True)
    parser.add_argument("--production-dir", required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--request-path", required=True)
    parser.add_argument("--request-blob", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--owner-manifest", required=True)
    parser.add_argument("--primary-receipt", required=True)
    parser.add_argument("--replica-receipt", required=True)
    parser.add_argument("--restore-receipt", required=True)
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--decision", choices=ALLOWED_DECISIONS)
    parser.add_argument("--decision-receipt")
    args = parser.parse_args(argv)

    runner = Path(args.runner_dir)
    control = Path(args.control_dir)
    production = Path(args.production_dir)
    verify_checkout(runner, args.runner_sha)
    verify_checkout(control, args.control_sha)
    verify_checkout(production, args.production_sha)
    request = control / args.request_path
    if git(control, "hash-object", str(request)) != args.request_blob:
        raise OwnerReviewError("REQUEST_BLOB_MISMATCH")

    manifest = load(Path(args.owner_manifest))
    receipts = [load(Path(args.primary_receipt)), load(Path(args.replica_receipt)), load(Path(args.restore_receipt))]
    for receipt in receipts:
        verify_receipt(receipt)
    if manifest.get("primary_receipt_hash") != receipts[0]["receipt_hash"] or manifest.get("replica_receipt_hash") != receipts[1]["receipt_hash"] or manifest.get("restore_receipt_hash") != receipts[2]["receipt_hash"]:
        raise OwnerReviewError("OWNER_MANIFEST_RECEIPT_CHAIN_MISMATCH")
    preview = resolve_preview(Path(args.private_root), manifest)

    print("CHECKSUM_MANIFEST_HASH=" + canonical_hash(manifest))
    print("MACHINE_QC_STATUS=" + str(manifest.get("machine_qc_status")))
    print("OWNER_DECISIONS=" + ",".join(ALLOWED_DECISIONS))
    print("HUMAN_FINAL_PREVIEW_ACCEPTED=false")
    if args.open:
        subprocess.Popen([choose_player(), str(preview)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("LOCAL_PLAYER_LAUNCHED=true")
    if args.decision:
        if not args.decision_receipt:
            raise OwnerReviewError("DECISION_RECEIPT_PATH_REQUIRED")
        receipt = write_decision(Path(args.decision_receipt), str(manifest["request_id"]), canonical_hash(manifest), args.decision)
        print("LOCAL_DECISION_RECEIPT_HASH=" + receipt["receipt_hash"])
        print("LOCAL_DECISION_TOKEN=" + args.decision)
    print("GITHUB_WRITE_PERFORMED=false")
    print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
    print("NO_FAKE_GREEN=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
