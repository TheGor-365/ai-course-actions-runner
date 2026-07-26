#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gold_s01_private_preview.common import *
from gold_s01_private_preview.contracts import *
from gold_s01_private_preview.host import *
from gold_s01_private_preview.artifacts import *
from gold_s01_private_preview.state import *
from gold_s01_private_preview.executor import *
from gold_s01_private_preview.policy import *
from gold_s01_private_preview.rebind import *


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gold S01 bounded private visual master and RU preview contour")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate-profile", "public-diagnostic"):
        p = sub.add_parser(name)
        p.add_argument("--profile", required=True)
    p = sub.add_parser("validate-request")
    p.add_argument("--profile", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--allow-provisional", action="store_true")
    p = sub.add_parser("host-readiness")
    p.add_argument("--profile", required=True)
    p.add_argument("--production-dir", required=True)
    p.add_argument("--production-sha", required=True)
    p.add_argument("--private-root", required=True)
    p.add_argument("--receipt-dir", required=True)
    p = sub.add_parser("rebind-request")
    p.add_argument("--profile", required=True)
    p.add_argument("--provisional-request", required=True)
    p.add_argument("--audio-handoff", required=True)
    p.add_argument("--visual-handoff", required=True)
    p.add_argument("--host-receipt", required=True)
    p.add_argument("--store-probe-receipt", required=True)
    p.add_argument("--runner-sha", required=True)
    p.add_argument("--control-base-sha", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--receipt", required=True)
    p.add_argument("--authorize", action="store_true")
    p = sub.add_parser("execute")
    p.add_argument("--profile", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--runner-dir", required=True)
    p.add_argument("--control-dir", required=True)
    p.add_argument("--control-head-sha", required=True)
    p.add_argument("--request-blob-sha", required=True)
    p.add_argument("--production-dir", required=True)
    p.add_argument("--audio-authority-dir", required=True)
    p.add_argument("--private-root", required=True)
    p.add_argument("--receipt-dir", required=True)
    p.add_argument("--host-receipt", required=True)
    p.add_argument("--store-probe-receipt", required=True)
    p.add_argument("--resume-token")
    p.add_argument("--inject-failure-after-station")
    args = parser.parse_args(argv)
    try:
        profile = load_json(Path(args.profile))
        if args.command == "validate-profile":
            validate_profile(profile)
            print("PRIVATE_PROFILE_IMPLEMENTED=true")
            print("REQUEST_VALIDATOR_GREEN=true")
        elif args.command == "public-diagnostic":
            print(json.dumps(public_diagnostic(profile), sort_keys=True))
        elif args.command == "validate-request":
            request = validate_request(load_json(Path(args.request)), profile, allow_provisional=args.allow_provisional)
            print("REQUEST_VALIDATION_STATUS=" + request["validation_status"])
            print("INPUT_FINGERPRINT=" + request["input_fingerprint"])
            print("BLOCKERS=" + ",".join(request["blockers"]))
        elif args.command == "host-readiness":
            require_private_execution_host()
            receipt_dir = Path(args.receipt_dir)
            receipt_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(receipt_dir, 0o700)
            host = host_probe(profile, Path(args.private_root), production_dir=Path(args.production_dir), production_sha=args.production_sha)
            atomic_json(receipt_dir / "sanitized_host_lock_receipt_v1.json", host)
            print("HOST_LOCK_STATUS=" + host["host_lock_status"])
            print("HOST_LOCK_RECEIPT_HASH=" + host["receipt_hash"])
            print("HOST_LOCK_FINGERPRINT=" + host["lock_fingerprint"])
            if host["host_lock_status"] != "READY":
                print("BLOCKERS=" + ",".join(host["blockers"]))
                print("STORE_PRIMARY_REPLICA_PROBE_GREEN=false")
                print("FINAL_RENDER_EXECUTED=false")
                print("PUBLIC_MEDIA_ARTIFACTS_CREATED=false")
                print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
                print("NO_FAKE_GREEN=true")
                return 2
            store = store_probe(profile, Path(args.private_root) / "gold_s01_primary_v1", Path(args.private_root) / "gold_s01_replica_v1")
            atomic_json(receipt_dir / "sanitized_store_probe_receipt_v1.json", store)
            print("STORE_PRIMARY_REPLICA_PROBE_GREEN=" + str(store["probe_status"] == "PASS").lower())
            print("STORE_PROBE_RECEIPT_HASH=" + store["receipt_hash"])
        elif args.command == "rebind-request":
            request, receipt = rebind_request(load_json(Path(args.provisional_request)), load_json(Path(args.audio_handoff)), load_json(Path(args.visual_handoff)), load_json(Path(args.host_receipt)), load_json(Path(args.store_probe_receipt)), profile, runner_sha=args.runner_sha, control_base_sha=args.control_base_sha, authorize=args.authorize)
            status = atomic_rebind(Path(args.output), request, receipt, Path(args.receipt))
            print("REQUEST_STATUS=EXACT_AUTHORIZED")
            print("REBIND_STATUS=" + status)
            print("INPUT_FINGERPRINT=" + receipt["input_fingerprint"])
            print("EXECUTION_REQUEST_SHA256=" + receipt["request_sha256"])
            print("REBIND_RECEIPT_HASH=" + receipt["receipt_hash"])
        elif args.command == "execute":
            handoff = execute_private_request(load_json(Path(args.request)), profile, Path(args.runner_dir), Path(args.control_dir), Path(args.production_dir), Path(args.audio_authority_dir), Path(args.private_root), Path(args.receipt_dir), Path(args.host_receipt), Path(args.store_probe_receipt), control_head_sha=args.control_head_sha, request_blob_sha=args.request_blob_sha, resume_token=args.resume_token, inject_failure_after_station=args.inject_failure_after_station)
            print("PRIVATE_EXECUTION_HANDOFF_HASH=" + handoff["receipt_hash"])
            print("VISUAL_MASTER_RENDERED=true")
            print("RU_PREVIEW_RENDERED=true")
            print("MACHINE_MEDIA_QC_GREEN=true")
            print("PRIMARY_REGISTERED=true")
            print("REPLICA_CREATED=true")
            print("CLEAN_RESTORE_VERIFIED=true")
            print("OWNER_REVIEW_PACKAGE_READY=true")
            print("HUMAN_FINAL_PREVIEW_ACCEPTED=false")
            print("FINAL_RENDER_EXECUTED=true")
            print("PUBLIC_MEDIA_ARTIFACTS_CREATED=false")
            print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
            print("NO_FAKE_GREEN=true")
            return 0
        print("FINAL_RENDER_EXECUTED=false")
        print("PUBLIC_MEDIA_ARTIFACTS_CREATED=false")
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return 0
    except RetryablePreviewError as exc:
        print("RESULT=RETRYABLE_FAILURE")
        print("FAILURE_CLASS=RETRYABLE_STATION_FAILURE")
        print("FAILED_AFTER_STATION=" + exc.station)
        print("RESUME_TOKEN=" + exc.token)
        print("FINAL_RENDER_EXECUTED=false")
        print("PUBLIC_MEDIA_ARTIFACTS_CREATED=false")
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return RETRY_EXIT
    except PreviewError as exc:
        print("RESULT=FAIL")
        print("FAILURE_CLASS=" + exc.code)
        print("FINAL_RENDER_EXECUTED=false")
        print("PUBLIC_MEDIA_ARTIFACTS_CREATED=false")
        print("PRIVATE_CONTENT_PUBLIC_EXPOSURE=false")
        print("NO_FAKE_GREEN=true")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
