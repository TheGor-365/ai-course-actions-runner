#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_REPOS = {
    "TheGor-365/ai-course-production-system",
    "TheGor-365/ai-course-source-library",
    "TheGor-365/ai-course-actions-runner",
}


class SyncError(ValueError):
    pass


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SyncError("root_not_object")
    return value


def validate_shape(value: dict) -> None:
    if value.get("schema_version") != "factory-sync-epoch-v1":
        raise SyncError("schema_version")
    if value.get("factory_id") != "AI_COURSE_FACTORY":
        raise SyncError("factory_id")
    if value.get("no_fake_green") is not True:
        raise SyncError("no_fake_green")
    heads = value.get("integration_heads")
    if not isinstance(heads, dict) or set(heads) != EXPECTED_REPOS:
        raise SyncError("integration_repo_set")
    for repo, record in heads.items():
        if not isinstance(record, dict) or set(record) != {"branch", "sha"}:
            raise SyncError("integration_record_" + repo)
        if record["branch"] != "launch/factory-5d":
            raise SyncError("integration_branch_" + repo)
        if not HEX40.fullmatch(str(record["sha"])):
            raise SyncError("integration_sha_" + repo)
    upstream = value.get("active_upstream_heads")
    if not isinstance(upstream, dict):
        raise SyncError("active_upstream_heads")
    for role, record in upstream.items():
        required = {"repository", "branch", "sha", "pr"}
        if not isinstance(record, dict) or set(record) != required:
            raise SyncError("upstream_record_" + role)
        if record["repository"] not in EXPECTED_REPOS:
            raise SyncError("upstream_repo_" + role)
        if not HEX40.fullmatch(str(record["sha"])):
            raise SyncError("upstream_sha_" + role)
        if not isinstance(record["pr"], int) or record["pr"] < 1:
            raise SyncError("upstream_pr_" + role)


def compare(expected: dict, observed: dict) -> list[str]:
    validate_shape(expected)
    validate_shape(observed)
    drift: list[str] = []
    for repo in sorted(EXPECTED_REPOS):
        if expected["integration_heads"][repo] != observed["integration_heads"][repo]:
            drift.append("integration:" + repo)
    expected_roles = set(expected["active_upstream_heads"])
    observed_roles = set(observed["active_upstream_heads"])
    if expected_roles != observed_roles:
        drift.append("upstream_role_set")
    for role in sorted(expected_roles & observed_roles):
        if expected["active_upstream_heads"][role] != observed["active_upstream_heads"][role]:
            drift.append("upstream:" + role)
    if expected.get("branch_format") != observed.get("branch_format"):
        drift.append("branch_format")
    return drift


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True)
    parser.add_argument("--observed", required=True)
    args = parser.parse_args()
    try:
        expected = load(Path(args.expected))
        observed = load(Path(args.observed))
        drift = compare(expected, observed)
    except (OSError, json.JSONDecodeError, SyncError) as exc:
        print("CROSS_REPO_SYNC_VALID=false")
        print("FAILURE_CLASS=CROSS_REPO_SYNC_CONTRACT_INVALID")
        print("ERROR_CODE=" + str(exc).split(":", 1)[0])
        print("NO_FAKE_GREEN=true")
        return 2
    if drift:
        print("CROSS_REPO_SYNC_VALID=false")
        print("FAILURE_CLASS=CROSS_REPO_DRIFT")
        print("DRIFT_COUNT=" + str(len(drift)))
        print("DRIFT_KEYS=" + ",".join(drift))
        print("NO_FAKE_GREEN=true")
        return 1
    print("CROSS_REPO_SYNC_VALID=true")
    print("INTEGRATION_REPOSITORY_COUNT=3")
    print("ACTIVE_UPSTREAM_COUNT=" + str(len(expected["active_upstream_heads"])))
    print("NO_FAKE_GREEN=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
