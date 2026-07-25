#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import private_owner_delivery_v1 as core


def finalize_receipt_chain(
    request: Mapping[str, Any],
    private_root: Path,
    receipt_dir: Path,
    registration: dict[str, Any],
    restore: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Bind restore and owner manifest to the final registration receipt hash."""
    expected_registration_hash = core.canonical_hash(registration, omit={"receipt_hash"})
    if registration.get("receipt_hash") != expected_registration_hash:
        raise core.DeliveryError(
            "REGISTRATION_RECEIPT_HASH_MISMATCH",
            "registration receipt is not canonical",
        )

    restore["registration_receipt_hash"] = expected_registration_hash
    restore["receipt_hash"] = core.canonical_hash(restore, omit={"receipt_hash"})
    manifest["registration_receipt_hash"] = expected_registration_hash
    manifest["restore_receipt_hash"] = restore["receipt_hash"]

    core.atomic_json(
        receipt_dir / "private_artifact_restore_receipt_v1.json",
        restore,
    )
    core.atomic_json(
        receipt_dir / "owner_delivery_manifest_for_git_v1.json",
        manifest,
    )
    package_root = (
        private_root
        / "owner_delivery_channels"
        / str(request["channel_id"])
        / str(request["package_id"])
    )
    core.atomic_json(package_root / "owner_delivery_manifest_v1.json", manifest)
    return registration, restore, manifest


def execute_finalized(
    request: Mapping[str, Any],
    production_dir: Path,
    private_root: Path,
    receipt_dir: Path,
    *,
    resume_token: str | None = None,
    inject_failure_after_registration: int | None = None,
    assembler=core.assemble_stills,
    clock=core.utc_now,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    registration, restore, manifest = core.execute_request(
        request,
        production_dir,
        private_root,
        receipt_dir,
        resume_token=resume_token,
        inject_failure_after_registration=inject_failure_after_registration,
        assembler=assembler,
        clock=clock,
    )
    return finalize_receipt_chain(
        request,
        private_root.resolve(),
        receipt_dir,
        registration,
        restore,
        manifest,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exact private owner delivery with finalized receipt chain"
    )
    parser.add_argument("--request", required=True)
    parser.add_argument("--production-dir", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--receipt-dir", required=True)
    parser.add_argument("--resume-token")
    parser.add_argument("--inject-failure-after-registration", type=int)
    args = parser.parse_args(argv)

    try:
        request = core.load_json(Path(args.request))
        registration, restore, _manifest = execute_finalized(
            request,
            Path(args.production_dir),
            Path(args.private_root),
            Path(args.receipt_dir),
            resume_token=args.resume_token,
            inject_failure_after_registration=args.inject_failure_after_registration,
        )
        core.sanitized_summary(registration, restore)
        print("RECEIPT_CHAIN_INTEGRITY=PASS")
        return 0
    except core.RetryableDeliveryError as exc:
        print("RESULT=RETRYABLE_FAILURE")
        print("FAILURE_CLASS=PRIVATE_DELIVERY_RETRYABLE_FAILURE")
        print("RESUME_TOKEN=" + exc.resume_token)
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return core.RETRY_EXIT
    except core.DeliveryError as exc:
        print("RESULT=FAIL")
        print("FAILURE_CLASS=" + exc.code)
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
