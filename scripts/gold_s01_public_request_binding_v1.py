#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_BLOCKERS = re.compile(r"^[A-Z0-9_,.-]*$")


class BindingError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(dict(value)))


def git_output(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def append_output(path: str | None, values: Mapping[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


def validate_binding(args: argparse.Namespace) -> int:
    if not HEX40.fullmatch(args.private_sha):
        raise BindingError("PRIVATE_SHA_INVALID", args.private_sha)
    if not HEX40.fullmatch(args.request_blob):
        raise BindingError("REQUEST_BLOB_INVALID", args.request_blob)
    if not HEX64.fullmatch(args.request_sha256):
        raise BindingError("REQUEST_SHA256_INVALID", args.request_sha256)
    if not SAFE_ID.fullmatch(args.request_id):
        raise BindingError("REQUEST_ID_INVALID", args.request_id)
    private_dir = Path(args.private_dir)
    request_rel = Path(args.request_path)
    if request_rel.is_absolute() or ".." in request_rel.parts:
        raise BindingError("REQUEST_PATH_UNSAFE", args.request_path)
    if git_output(private_dir, "rev-parse", "HEAD") != args.private_sha:
        raise BindingError("EXACT_HEAD_DRIFT", args.private_sha)
    request_file = private_dir / request_rel
    if not request_file.is_file():
        raise BindingError("REQUEST_FILE_MISSING", args.request_path)
    observed_blob = git_output(private_dir, "hash-object", args.request_path)
    if observed_blob != args.request_blob:
        raise BindingError("REQUEST_BLOB_MISMATCH", observed_blob)
    try:
        request = json.loads(request_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BindingError("REQUEST_JSON_INVALID", args.request_path) from exc
    if not isinstance(request, dict):
        raise BindingError("REQUEST_OBJECT_REQUIRED", args.request_path)
    if request.get("request_id") != args.request_id:
        raise BindingError("REQUEST_ID_MISMATCH", str(request.get("request_id")))
    if request.get("request_sha256") != args.request_sha256:
        raise BindingError("DECLARED_REQUEST_HASH_MISMATCH", str(request.get("request_sha256")))
    self_hash_input = dict(request)
    self_hash_input.pop("request_sha256", None)
    observed_declared_hash = hashlib.sha256(canonical_bytes(self_hash_input)).hexdigest()
    if observed_declared_hash != args.request_sha256:
        raise BindingError("REQUEST_SELF_HASH_MISMATCH", observed_declared_hash)
    raw_hash = sha256_file(request_file)
    receipt = {
        "schema_version": "gold-s01-public-request-binding-v1",
        "status": "PASS",
        "private_sha": args.private_sha,
        "request_path": args.request_path,
        "request_blob": observed_blob,
        "request_declared_sha256": args.request_sha256,
        "request_raw_sha256": raw_hash,
        "request_id": args.request_id,
        "private_content_printed": False,
        "no_fake_green": True,
    }
    write_json(Path(args.output), receipt)
    append_output(
        args.github_output,
        {
            "request_raw_sha256": raw_hash,
            "request_declared_sha256": args.request_sha256,
            "request_blob": observed_blob,
            "request_id": args.request_id,
        },
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


def api_json(url: str, token: str, *, method: str = "GET", body: Mapping[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise BindingError("GITHUB_API_FAILED", url) from exc


def resolve_job_id(token: str) -> str:
    repository = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not repository or not run_id:
        return "unavailable"
    payload = api_json(f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100", token)
    current = os.environ.get("GITHUB_JOB", "")
    for job in payload.get("jobs", []):
        normalized = str(job.get("name", "")).lower().replace(" ", "-")
        if job.get("name") == current or normalized == current:
            return str(job["id"])
    jobs = payload.get("jobs", [])
    return str(jobs[0]["id"]) if jobs else "unavailable"


def writeback_blocked(args: argparse.Namespace) -> int:
    token = os.environ.get("PRIVATE_REPO_PAT")
    if not token:
        raise BindingError("PRIVATE_REPO_PAT_MISSING", "blocked writeback")
    if not HEX40.fullmatch(args.private_sha):
        raise BindingError("PRIVATE_SHA_INVALID", args.private_sha)
    if not HEX64.fullmatch(args.input_fingerprint):
        raise BindingError("INPUT_FINGERPRINT_INVALID", args.input_fingerprint)
    if not SAFE_BLOCKERS.fullmatch(args.blockers):
        raise BindingError("BLOCKERS_INVALID", args.blockers)
    job_id = resolve_job_id(token)
    fields = {
        "RUN_ID": os.environ.get("GITHUB_RUN_ID", "unavailable"),
        "JOB_ID": job_id,
        "ARTIFACT_ID": args.artifact_id,
        "ARTIFACT_NAME": args.artifact_name,
        "RETENTION_OR_EXPIRY": "30_days",
        "PRIVATE_SHA": args.private_sha,
        "INPUT_FINGERPRINT": args.input_fingerprint,
        "PREFLIGHT_STATUS": "BLOCKED",
        "BLOCKERS": args.blockers,
        "PILOT_60S_RENDERED": "false",
        "PILOT_MACHINE_QC_GREEN": "false",
        "FULL_15M_RENDER_STARTED": "false",
        "HUMAN_FINAL_PREVIEW_ACCEPTED": "false",
        "NO_FAKE_GREEN": "true",
    }
    body = "## Gold S01 public media preflight receipt\n\n```text\n" + "\n".join(f"{key}={value}" for key, value in fields.items()) + "\n```"
    production_repo = "TheGor-365/ai-course-production-system"
    for issue_number in (350, 346, 348, 344):
        api_json(
            f"https://api.github.com/repos/{production_repo}/issues/{issue_number}/comments",
            token,
            method="POST",
            body={"body": body},
        )
    api_json(
        "https://api.github.com/repos/TheGor-365/ai-course-actions-runner/issues/17/comments",
        token,
        method="POST",
        body={"body": body},
    )
    print(json.dumps(fields, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gold S01 exact request self-hash binding and blocked preflight writeback")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--private-dir", required=True)
    validate.add_argument("--private-sha", required=True)
    validate.add_argument("--request-path", required=True)
    validate.add_argument("--request-blob", required=True)
    validate.add_argument("--request-sha256", required=True)
    validate.add_argument("--request-id", required=True)
    validate.add_argument("--output", required=True)
    validate.add_argument("--github-output")
    blocked = sub.add_parser("writeback-blocked")
    blocked.add_argument("--artifact-id", required=True)
    blocked.add_argument("--artifact-name", required=True)
    blocked.add_argument("--private-sha", required=True)
    blocked.add_argument("--input-fingerprint", required=True)
    blocked.add_argument("--blockers", required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            return validate_binding(args)
        if args.command == "writeback-blocked":
            return writeback_blocked(args)
        raise BindingError("COMMAND_INVALID", str(args.command))
    except BindingError as exc:
        print(f"RESULT=FAIL\nFAILURE_CLASS={exc.code}\nDETAIL={exc.detail}\nNO_FAKE_GREEN=true", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
