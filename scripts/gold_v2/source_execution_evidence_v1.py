#!/usr/bin/env python3
"""Bounded GitHub-hosted evidence runner for production-system issue #424."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

RUNNER_REPO = "TheGor-365/ai-course-actions-runner"
TARGET_BRANCH = "worker/gold-v2-source-execution-evidence-v1"
WORKFLOW_PATH = ".github/workflows/gold-v2-source-execution-evidence-v1.yml"
SOURCE_REPO = "TheGor-365/ai-course-source-library"
SOURCE_PR = 66
SOURCE_HEAD = "ab38ac36a786cdb93fc15263fadf391ce62368d5"
PACKAGE_REL = Path("Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

POSITIVE = (
    ("python3", "10_pipeline/validate_gold_psu_execution_contract_v1.py", "--validate-materialized"),
    ("python3", "10_pipeline/validate_gold_psu_final_exact_oc_lineage_v1.py"),
    ("python3", "10_pipeline/validate_gold_psu_source_finalization_v1.py", "--root", "{ROOT}"),
    ("python3", "10_pipeline/validate_gold_psu_v2.py", "--idempotence-only", "--root", "{ROOT}"),
    ("python3", "10_pipeline/validate_gold_psu_visual_minimum_v1.py"),
    ("python3", "10_pipeline/validate_package.py", "{ROOT}"),
)
EXTRA = (
    ("python3", "10_pipeline/validate_gold_psu_v2.py", "--full", "--root", "{ROOT}"),
    ("python3", "10_pipeline/validate_gold_psu_execution_contract_v1.py", "--self-test"),
    ("python3", "10_pipeline/validate_gold_psu_source_finalization_v1.py", "--negative-fixtures", "--root", "{ROOT}"),
    ("python3", "10_pipeline/validate_gold_psu_v2.py", "--source-repair-self-test", "--root", "{ROOT}"),
)
MATERIALIZE = ("python3", "10_pipeline/validate_gold_psu_execution_contract_v1.py", "--materialize")


class Gate(RuntimeError):
    def __init__(self, code: str, detail: Any = "") -> None:
        self.code, self.detail = code, detail
        super().__init__(f"{code}:{detail}" if detail != "" else code)


def need(ok: bool, code: str, detail: Any = "") -> None:
    if not ok:
        raise Gate(code, detail)


def canon(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proc(argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None, timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), cwd=cwd, env=dict(env) if env else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)


def git(repo: Path, *args: str, env: Mapping[str, str] | None = None, check: bool = True) -> str:
    done = proc(("git", "-c", "core.quotepath=false", *args), repo, env, 900)
    if check and done.returncode:
        raise Gate("GIT_COMMAND_FAILED", {"args": list(args), "exit": done.returncode, "stderr_sha256": sha(done.stderr.encode())})
    return done.stdout.strip()


def api(url: str, token: str, method: str = "GET", body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url, data=canon(body) if body else None, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gold-v2-source-execution-evidence-v1",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            value = json.loads(raw.decode()) if raw else {}
            return response.status, value if isinstance(value, dict) else {"value": value}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            value = json.loads(raw.decode()) if raw else {}
        except Exception:
            value = {}
        return exc.code, value if isinstance(value, dict) else {}


def token_names(env: Mapping[str, str]) -> list[str]:
    return [name for name in ("GOLD_V2_SOURCE_READ_TOKEN", "SOURCE_REPO_READ_TOKEN", "REPO_READ_TOKEN") if env.get(name)]


def token(env: Mapping[str, str]) -> tuple[str, str]:
    names = token_names(env)
    if not names:
        raise Gate("MISSING_READ_ONLY_PRIVATE_REPO_TOKEN")
    return names[0], env[names[0]]


def verify_runner(repo: Path, env: Mapping[str, str]) -> dict[str, Any]:
    head = env.get("GITHUB_SHA", "")
    workflow_ref = env.get("GITHUB_WORKFLOW_REF", "")
    need(env.get("GITHUB_REPOSITORY") == RUNNER_REPO, "RUNNER_REPOSITORY_DRIFT")
    need(env.get("GITHUB_REF_NAME") == TARGET_BRANCH, "RUNNER_BRANCH_DRIFT")
    need(env.get("GITHUB_EVENT_NAME") == "push", "WORKFLOW_EVENT_DRIFT")
    need(bool(HEX40.fullmatch(head)), "INVALID_RUNNER_HEAD", head)
    need(git(repo, "rev-parse", "HEAD") == head, "RUNNER_CHECKOUT_HEAD_DRIFT")
    need(workflow_ref == f"{RUNNER_REPO}/{WORKFLOW_PATH}@refs/heads/{TARGET_BRANCH}", "WORKFLOW_REF_DRIFT", workflow_ref)
    need(git(repo, "status", "--porcelain=v1") == "", "RUNNER_WORKTREE_DIRTY")
    return {"runner_head": head, "workflow_ref": workflow_ref}


def clone_source(root: Path, secret: str) -> dict[str, Any]:
    root.mkdir(parents=True)
    git(root, "init", "--quiet")
    git(root, "remote", "add", "origin", f"https://github.com/{SOURCE_REPO}.git")
    env = os.environ.copy()
    env.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": f"url.https://x-access-token:{secret}@github.com/.insteadOf",
        "GIT_CONFIG_VALUE_0": "https://github.com/",
    })
    done = proc(("git", "fetch", "--no-tags", "--depth=1", "origin", f"refs/pull/{SOURCE_PR}/head"), root, env, 900)
    need(done.returncode == 0, "SOURCE_FETCH_FAILED", {"exit": done.returncode, "stderr_sha256": sha(done.stderr.encode())})
    git(root, "checkout", "--detach", "--quiet", "FETCH_HEAD")
    observed = git(root, "rev-parse", "HEAD")
    need(observed == SOURCE_HEAD, "SOURCE_CHECKOUT_HEAD_DRIFT", observed)
    need(git(root, "symbolic-ref", "-q", "HEAD", check=False) == "", "SOURCE_NOT_DETACHED")
    need(git(root, "status", "--porcelain=v1") == "", "SOURCE_DIRTY_AFTER_CHECKOUT")
    return {"fresh_detached_checkout": True, "source_head": observed, "source_tree": git(root, "rev-parse", "HEAD^{tree}")}


def verify_pr(secret: str) -> None:
    status, value = api(f"https://api.github.com/repos/{SOURCE_REPO}/pulls/{SOURCE_PR}", secret)
    need(status == 200, "SOURCE_PR_READ_FAILED", status)
    need(value.get("head", {}).get("sha") == SOURCE_HEAD, "SOURCE_PR_HEAD_DRIFT", value.get("head", {}).get("sha"))
    need(value.get("state") == "open" and value.get("draft") is True, "SOURCE_PR_STATE_DRIFT")


def tracked(root: Path) -> list[str]:
    raw = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", PACKAGE_REL.as_posix()], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    need(raw.returncode == 0 and (raw.stdout == b"" or raw.stdout.endswith(b"\0")), "TRACKED_FILE_LIST_FAILED")
    paths = [os.fsdecode(item) for item in raw.stdout.split(b"\0") if item]
    need(paths == sorted(paths) and len(paths) == len(set(paths)) and paths, "TRACKED_FILE_SET_INVALID")
    return paths


def snapshot(root: Path) -> tuple[list[dict[str, Any]], str]:
    rows = []
    for relative in tracked(root):
        path = root / relative
        need(path.is_file(), "TRACKED_FILE_MISSING", relative)
        rows.append({"path": relative, "sha256": file_sha(path), "size": path.stat().st_size})
    return rows, sha(canon(rows))


def status_paths(root: Path) -> list[str]:
    output = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    paths = []
    for line in output.splitlines():
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw.strip('"'))
    return sorted(set(paths))


def parsed(stdout: str) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for candidate in [stdout.strip(), *reversed(lines)]:
        try:
            value = json.loads(candidate)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return {}


def run_logged(label: str, argv: Sequence[str], cwd: Path, env: Mapping[str, str], logs: Path) -> dict[str, Any]:
    done = proc(argv, cwd, env)
    (logs / f"{label}.stdout.txt").write_text(done.stdout, encoding="utf-8")
    (logs / f"{label}.stderr.txt").write_text(done.stderr, encoding="utf-8")
    record = {"label": label, "argv": list(argv), "exit_code": done.returncode, "stdout_sha256": sha(done.stdout.encode()), "stderr_sha256": sha(done.stderr.encode()), "receipt": parsed(done.stdout)}
    (logs / f"{label}.json").write_bytes(canon(record))
    return record


def exact_count(receipt: Mapping[str, Any], key: str, expected: int) -> None:
    need(type(receipt.get(key)) is int and receipt[key] == expected, "RECEIPT_COUNT_DRIFT", {"key": key, "value": receipt.get(key)})


def validate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    need(all(record["exit_code"] == 0 for record in records), "VALIDATOR_COMMAND_FAILED", [record["exit_code"] for record in records])
    idem = records[3]["receipt"]
    exact_count(idem, "materialization_pass_count", 2)
    exact_count(idem, "pass_1_materialized_changed_path_count", 0)
    exact_count(idem, "untracked_materialization_output_count", 0)
    need(idem.get("pass_1_materialized_changed_paths") == [], "IDEMPOTENCE_PASS_1_PATH_DRIFT")
    need(idem.get("materialize_idempotent_zero_diff") is True and idem.get("read_only_reconciliation_byte_diff_zero") is True, "IDEMPOTENCE_FLAG_FALSE")
    for key in ("pass_1_tracked_snapshot_sha256", "pass_2_tracked_snapshot_sha256"):
        need(isinstance(idem.get(key), str) and HEX64.fullmatch(idem[key]), "IDEMPOTENCE_HASH_INVALID", key)
    need(idem["pass_1_tracked_snapshot_sha256"] == idem["pass_2_tracked_snapshot_sha256"], "IDEMPOTENCE_HASH_DRIFT")
    registry = records[7]["receipt"]
    exact_count(registry, "negative_fixture_reject_count", 12)
    for receipt in (records[8]["receipt"], records[9]["receipt"]):
        exact_count(receipt, "registry_negative_fixture_count", 12)
        exact_count(receipt, "source_repair_negative_mutation_count", 12)
        exact_count(receipt, "total_negative_case_count", 24)
        need(receipt.get("negative_fixture_reject_rate") == "100_PERCENT", "NEGATIVE_REJECT_RATE_DRIFT")
    return {"positive_validator_count": 6, "positive_validator_pass_count": 6, "registry_negative_fixture_count": 12, "source_repair_negative_mutation_count": 12, "total_negative_case_count": 24, "negative_fixture_reject_rate": "100_PERCENT", "canonical_idempotence_receipt": idem}


def materialize_twice(root: Path, package: Path, env: Mapping[str, str], logs: Path) -> dict[str, Any]:
    hashes, changed = [], []
    for number in (1, 2):
        record = run_logged(f"materialize_pass_{number}", MATERIALIZE, package, env, logs)
        need(record["exit_code"] == 0, "MATERIALIZER_FAILED", number)
        changed.append(status_paths(root))
        hashes.append(snapshot(root)[1])
        if number == 1:
            (logs.parent / "pass_1_checkpoint.json").write_bytes(canon({"source_head": SOURCE_HEAD, "git_write_tree": git(root, "write-tree"), "tracked_snapshot_sha256": hashes[0], "changed_paths": changed[0]}))
    need(changed == [[], []], "MATERIALIZATION_DIFF_NONZERO", changed)
    need(hashes[0] == hashes[1], "MATERIALIZATION_SNAPSHOT_DRIFT")
    need(git(root, "diff", "--name-only") == "" and git(root, "diff", "--cached", "--name-only") == "" and git(root, "ls-files", "--others", "--exclude-standard") == "", "FINAL_MATERIALIZATION_RESIDUE")
    return {"materialization_pass_count": 2, "pass_1_materialized_changed_path_count": 0, "pass_1_materialized_changed_paths": [], "pass_1_tracked_snapshot_sha256": hashes[0], "pass_2_tracked_snapshot_sha256": hashes[1], "materialize_idempotent_zero_diff": True, "read_only_reconciliation_byte_diff_zero": True, "untracked_materialization_output_count": 0}


def job_id(env: Mapping[str, str]) -> int | None:
    secret, run_id = env.get("ACTIONS_READ_TOKEN", ""), env.get("GITHUB_RUN_ID", "")
    if not secret or not run_id.isdigit():
        return None
    url = f"https://api.github.com/repos/{RUNNER_REPO}/actions/runs/{run_id}/jobs?per_page=100"
    for _ in range(5):
        status, value = api(url, secret)
        if status == 200:
            matches = [row for row in value.get("jobs", []) if row.get("name") == "execute-exact-source-evidence"]
            if len(matches) == 1 and isinstance(matches[0].get("id"), int):
                return matches[0]["id"]
        time.sleep(2)
    return None


def publish_status(secret: str, run_id: str, passed: bool) -> tuple[bool, str]:
    status, value = api(f"https://api.github.com/repos/{SOURCE_REPO}/statuses/{SOURCE_HEAD}", secret, "POST", {"state": "success" if passed else "failure", "target_url": f"https://github.com/{RUNNER_REPO}/actions/runs/{run_id}", "description": "Exact-head GitHub-hosted source execution evidence", "context": "gold-v2/source-execution-evidence-v1"})
    if status == 201:
        return True, "published"
    return False, f"permission_or_endpoint_denied:{str(value.get('message', f'HTTP_{status}'))[:120]}"


def archive(directory: Path, destination: Path) -> str:
    files = sorted(path for path in directory.rglob("*") if path.is_file())
    need(files, "EMPTY_EVIDENCE_ARCHIVE")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(directory).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type, info.create_system, info.external_attr = zipfile.ZIP_DEFLATED, 3, 0o100644 << 16
            output.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return file_sha(destination)


def execute(workspace: Path, runner: Path, env: Mapping[str, str]) -> tuple[int, dict[str, Any], Path]:
    evidence, logs = workspace / "evidence", workspace / "evidence/logs"
    logs.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {"evidence_result": "REPAIR_REQUIRED", "workflow_repository": RUNNER_REPO, "workflow_run_id": env.get("GITHUB_RUN_ID") or None, "workflow_job_id": None, "runner_head": env.get("GITHUB_SHA") or None, "source_head": SOURCE_HEAD, "remote_only_inputs": True, "fresh_detached_checkout": False, "source_writes": 0, "production_writes": 0, "media_render_started": False, "independent_verifier_pass_claimed": False, "no_fake_green": True, "secret_value_exposed": False}
    source, zip_path, secret = workspace / "fresh-source", workspace / "gold-v2-source-execution-evidence-v1.zip", ""
    try:
        receipt.update(verify_runner(runner, env))
        receipt["available_secret_names_observed"] = token_names(env)
        secret_name, secret = token(env)
        receipt["source_transport_secret_name"] = secret_name
        receipt["source_transport_secret_value_exposed"] = False
        verify_pr(secret)
        receipt.update(clone_source(source, secret))
        package = source / PACKAGE_REL
        need(package.is_dir(), "SOURCE_PACKAGE_ROOT_MISSING")
        paths = tracked(source)
        (evidence / "tracked_file_set.json").write_bytes(canon(paths))
        pre_rows, pre_hash = snapshot(source)
        (evidence / "pre_execution_tracked_snapshot.json").write_bytes(canon(pre_rows))
        receipt["pre_execution_package_sha256"] = pre_hash
        command_env = dict(env)
        command_env.update(os.environ)
        for name in ("GOLD_V2_SOURCE_READ_TOKEN", "SOURCE_REPO_READ_TOKEN", "REPO_READ_TOKEN", "ACTIONS_READ_TOKEN"):
            command_env.pop(name, None)
        command_env["PYTHONPYCACHEPREFIX"] = str(workspace / "external-pycache")
        records = []
        for index, template in enumerate((*POSITIVE, *EXTRA), 1):
            argv = tuple(item.replace("{ROOT}", str(source)) for item in template)
            records.append(run_logged(f"command_{index:02d}", argv, package, command_env, logs))
        summary = validate_records(records)
        receipt.update({key: value for key, value in summary.items() if key != "canonical_idempotence_receipt"})
        (evidence / "canonical_idempotence_receipt.json").write_bytes(canon(summary["canonical_idempotence_receipt"]))
        independent = materialize_twice(source, package, command_env, logs)
        receipt.update(independent)
        (evidence / "independent_materialization_receipt.json").write_bytes(canon(independent))
        post_rows, post_hash = snapshot(source)
        (evidence / "post_execution_tracked_snapshot.json").write_bytes(canon(post_rows))
        receipt["post_execution_package_sha256"] = post_hash
        receipt["package_bytes_unchanged"] = pre_hash == post_hash
        need(receipt["package_bytes_unchanged"], "PACKAGE_BYTES_CHANGED")
        receipt["final_worktree_clean"] = status_paths(source) == []
        need(receipt["final_worktree_clean"], "FINAL_WORKTREE_DIRTY")
        receipt["workflow_job_id"] = job_id(env)
        receipt["evidence_result"] = "PASS_EXACT_HEAD_GITHUB_HOSTED_EXECUTION"
        published, reason = publish_status(secret, str(receipt.get("workflow_run_id") or ""), True)
        receipt["source_commit_status_published"], receipt["source_commit_status_reason"] = published, reason
        code = 0
    except Gate as exc:
        receipt["blocker"], receipt["blocker_detail"] = exc.code, exc.detail
        if secret:
            published, reason = publish_status(secret, str(receipt.get("workflow_run_id") or ""), False)
            receipt["source_commit_status_published"], receipt["source_commit_status_reason"] = published, reason
        else:
            receipt["source_commit_status_published"], receipt["source_commit_status_reason"] = False, "not_attempted_without_transport_credential"
        code = 2
    except Exception as exc:
        receipt["blocker"], receipt["blocker_detail"] = "UNEXPECTED_EVIDENCE_WORKER_FAILURE", type(exc).__name__
        receipt["source_commit_status_published"], receipt["source_commit_status_reason"] = False, "not_attempted_after_unexpected_failure"
        code = 3
    (evidence / "machine_receipt.json").write_bytes(canon(receipt))
    (evidence / "exact_identities.json").write_bytes(canon({"workflow_repository": RUNNER_REPO, "workflow_path": WORKFLOW_PATH, "target_branch": TARGET_BRANCH, "runner_head": receipt.get("runner_head"), "source_repository": SOURCE_REPO, "source_pr": SOURCE_PR, "source_head": SOURCE_HEAD, "source_tree": receipt.get("source_tree")}))
    archive_sha = archive(evidence, zip_path)
    (workspace / "archive_sha256.txt").write_text(f"{archive_sha}  {zip_path.name}\n", encoding="utf-8")
    return code, receipt, zip_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--runner-repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    args.workspace.mkdir(parents=True, exist_ok=True)
    code, receipt, zip_path = execute(args.workspace.resolve(), args.runner_repo.resolve(), os.environ)
    print(json.dumps({"archive": str(zip_path), "blocker": receipt.get("blocker"), "evidence_result": receipt.get("evidence_result"), "secret_value_exposed": False}, sort_keys=True, separators=(",", ":")))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
