#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .common import RunnerError, require_relpath, require_sha40, sha256_file


def _run(argv: list[str], *, cwd: Path | None = None, capture: bool = True) -> str:
    try:
        result = subprocess.run(
            argv, cwd=cwd, check=True, text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RunnerError(f"COMMAND_FAILED:{argv[0]}:{stderr[-500:]}") from exc
    return (result.stdout or "").strip()


def assert_clean(repo: Path) -> None:
    if _run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo):
        raise RunnerError(f"GIT_TREE_DIRTY:{repo}")


def git_blob_sha(repo: Path, relative: str) -> str:
    relative = require_relpath(relative, "GIT_BLOB_PATH_INVALID")
    value = _run(["git", "rev-parse", f"HEAD:{relative}"], cwd=repo)
    return require_sha40(value, "GIT_BLOB_SHA_INVALID")


def checkout_exact(url: str, head: str, destination: Path, *, required_ancestor: str | None = None) -> dict[str, Any]:
    head = require_sha40(head, "EXACT_HEAD_INVALID")
    if destination.exists():
        raise RunnerError(f"CHECKOUT_DESTINATION_EXISTS:{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "--quiet", str(destination)])
    _run(["git", "remote", "add", "origin", url], cwd=destination)
    _run(["git", "fetch", "--quiet", "--no-tags", "origin", head], cwd=destination)
    _run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=destination)
    observed = _run(["git", "rev-parse", "HEAD"], cwd=destination)
    if observed != head:
        raise RunnerError("EXACT_HEAD_CHECKOUT_MISMATCH")
    symbolic = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=destination, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if symbolic.returncode == 0:
        raise RunnerError("DETACHED_HEAD_REQUIRED")
    if required_ancestor:
        required_ancestor = require_sha40(required_ancestor, "REQUIRED_ANCESTOR_INVALID")
        _run(["git", "fetch", "--quiet", "--no-tags", "origin", required_ancestor], cwd=destination)
        try:
            subprocess.run(["git", "merge-base", "--is-ancestor", required_ancestor, head], cwd=destination, check=True)
        except subprocess.CalledProcessError as exc:
            raise RunnerError("REQUIRED_ANCESTRY_FAILED") from exc
    assert_clean(destination)
    return {
        "head": head,
        "tree": require_sha40(_run(["git", "rev-parse", "HEAD^{tree}"], cwd=destination), "TREE_SHA_INVALID"),
        "detached": True,
        "clean": True,
        "required_ancestor": required_ancestor,
    }


def verify_remote_branch_tip(repo: Path, branch: str, expected_head: str) -> None:
    if not isinstance(branch, str) or not branch or branch.startswith("-"):
        raise RunnerError("CONTROL_BRANCH_INVALID")
    output = _run(["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"], cwd=repo)
    rows = [row.split() for row in output.splitlines() if row.strip()]
    if len(rows) != 1 or rows[0][0] != expected_head:
        raise RunnerError("STALE_CONTROL_HEAD")


def verify_bound_file(repo: Path, binding: Mapping[str, Any]) -> dict[str, str]:
    relative = require_relpath(binding["path"], "BOUND_FILE_PATH_INVALID")
    path = repo / relative
    if not path.is_file() or path.is_symlink():
        raise RunnerError(f"BOUND_FILE_MISSING:{relative}")
    digest = sha256_file(path)
    blob = git_blob_sha(repo, relative)
    if digest != binding["sha256"] or blob != binding["git_blob_sha"]:
        raise RunnerError(f"BOUND_FILE_IDENTITY_MISMATCH:{relative}")
    return {"path": relative, "sha256": digest, "git_blob_sha": blob}


def run_command(command: Mapping[str, Any], repos: Mapping[str, Path], values: Mapping[str, str], log_path: Path) -> dict[str, Any]:
    repo_key = command["repo"]
    if repo_key not in repos:
        raise RunnerError(f"COMMAND_REPOSITORY_NOT_CHECKED_OUT:{repo_key}")
    argv: list[str] = []
    for item in command["argv"]:
        try:
            argv.append(item.format_map(values))
        except KeyError as exc:
            raise RunnerError(f"COMMAND_TEMPLATE_VALUE_MISSING:{exc.args[0]}") from exc
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            argv, cwd=repos[repo_key], check=False, text=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError as exc:
        raise RunnerError(f"COMMAND_EXECUTION_FAILED:{argv[0]}") from exc
    log_path.write_bytes(result.stdout or b"")
    if result.returncode != 0:
        raise RunnerError(f"COMMAND_NONZERO:{argv[0]}:{result.returncode}")
    return {
        "repo": repo_key,
        "argv": argv,
        "exit_code": result.returncode,
        "log_path": str(log_path),
        "log_sha256": sha256_file(log_path),
    }
