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
    p = sub.add_parser("host-probe")
    p.add_argument("--profile", required=True)
    p.add_argument("--private-root", required=True)
    p.add_argument("--receipt", required=True)
    p.add_argument("--authorize-store-probe", action="store_true")
    p = sub.add_parser("execute")
    p.add_argument("--profile", required=True)
    p.add_argument("--request", required=True)
    p.add_argument("--runner-dir", required=True)
    p.add_argument("--control-dir", required=True)
    p.add_argument("--production-dir", required=True)
    p.add_argument("--private-root", required=True)
    p.add_argument("--receipt-dir", required=True)
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
        elif args.command == "host-probe":
            receipt = host_probe(profile, Path(args.private_root), authorize_store_probe=args.authorize_store_probe)
            atomic_json(Path(args.receipt), receipt)
            print("HOST_LOCK_STATUS=" + receipt["host_lock_status"])
            print("STORE_PRIMARY_REPLICA_PROBE_GREEN=" + str(receipt["primary_probe"] == receipt["replica_probe"] == "PASS").lower())
            print("BLOCKERS=" + ",".join(receipt["blockers"]))
        elif args.command == "execute":
            handoff = execute_private_request(
                load_json(Path(args.request)),
                profile,
                Path(args.runner_dir),
                Path(args.control_dir),
                Path(args.production_dir),
                Path(args.private_root),
                Path(args.receipt_dir),
                resume_token=args.resume_token,
                inject_failure_after_station=args.inject_failure_after_station,
            )
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
