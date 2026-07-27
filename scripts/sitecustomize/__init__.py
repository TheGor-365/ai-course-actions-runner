from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

RUNNER_REPO = "TheGor-365/ai-course-actions-runner"
PRODUCTION_REPO = "TheGor-365/ai-course-production-system"
RUNNER_BRANCH = "worker/m1-l01-s01-runner-pre-render-finalization-v1"
WORKFLOW = "canonical-gold-s01-minute-proofs.yml"
LEDGER_ISSUE = "376"
RUNNER_PR = "22"


def _run(args: list[str], *, env: dict[str, str] | None = None, text: bool = True) -> str:
    completed = subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        env=env,
    )
    return completed.stdout if text else completed.stdout.decode("utf-8")


def _gh_env() -> dict[str, str]:
    token = os.environ.get("PRIVATE_REPO_PAT", "")
    if not token:
        raise RuntimeError("PRIVATE_REPO_PAT_MISSING")
    env = os.environ.copy()
    env["GH_TOKEN"] = token
    return env


def _api(path: str, *fields: tuple[str, str], method: str = "GET"):
    args = ["gh", "api", "--method", method, path]
    for key, value in fields:
        args.extend(["-f", f"{key}={value}"])
    payload = _run(args, env=_gh_env())
    return json.loads(payload) if payload.strip() else {}


def _comment(body: str) -> None:
    _api(
        f"repos/{PRODUCTION_REPO}/issues/{LEDGER_ISSUE}/comments",
        ("body", body),
        method="POST",
    )
    public_body = "\n".join(
        [
            "## Gold S01 exact orchestration status",
            "",
            "```text",
            body[:12000],
            "```",
            "",
            "This status is machine-written by the exact PR workflow. No media render is authorized or started.",
        ]
    )
    _api(
        f"repos/{RUNNER_REPO}/pulls/{RUNNER_PR}",
        ("body", public_body),
        method="PATCH",
    )


def _git(*args: str, cwd: Path | None = None) -> str:
    command = ["git"]
    if cwd is not None:
        command.extend(["-C", str(cwd)])
    command.extend(args)
    return _run(command).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _workflow_runs() -> list[dict]:
    payload = _api(
        f"repos/{RUNNER_REPO}/actions/workflows/{WORKFLOW}/runs",
        ("branch", RUNNER_BRANCH),
        ("event", "workflow_dispatch"),
        ("per_page", "50"),
    )
    return payload.get("workflow_runs", [])


def _dispatch(mode: str, inputs: dict[str, str]) -> int:
    before = {int(run["id"]) for run in _workflow_runs()}
    command = [
        "gh",
        "workflow",
        "run",
        WORKFLOW,
        "--repo",
        RUNNER_REPO,
        "--ref",
        RUNNER_BRANCH,
        "-f",
        f"mode={mode}",
    ]
    for key, value in inputs.items():
        command.extend(["-f", f"{key}={value}"])
    _run(command, env=_gh_env())
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        candidates = [
            run
            for run in _workflow_runs()
            if int(run["id"]) not in before
            and run.get("head_sha") == inputs["runner_head"]
        ]
        if candidates:
            candidates.sort(key=lambda item: item["created_at"], reverse=True)
            return int(candidates[0]["id"])
        time.sleep(3)
    raise RuntimeError(f"DISPATCH_RUN_NOT_FOUND:{mode}")


def _wait_run(run_id: int, timeout_seconds: int) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run = _api(f"repos/{RUNNER_REPO}/actions/runs/{run_id}")
        if run.get("status") == "completed":
            if run.get("conclusion") != "success":
                raise RuntimeError(f"WORKFLOW_RUN_FAILED:{run_id}:{run.get('conclusion')}")
            return run
        time.sleep(8)
    raise RuntimeError(f"WORKFLOW_RUN_TIMEOUT:{run_id}")


def _run_job_id(run_id: int, contains: str) -> int:
    payload = _api(
        f"repos/{RUNNER_REPO}/actions/runs/{run_id}/jobs",
        ("per_page", "100"),
    )
    jobs = [job for job in payload.get("jobs", []) if contains in str(job.get("name", ""))]
    if len(jobs) != 1:
        raise RuntimeError(f"JOB_COUNT_MISMATCH:{run_id}:{contains}:{len(jobs)}")
    if jobs[0].get("conclusion") != "success":
        raise RuntimeError(f"JOB_NOT_SUCCESS:{run_id}:{jobs[0].get('conclusion')}")
    return int(jobs[0]["id"])


def _artifact(run_id: int, name: str, directory: Path) -> tuple[int, str]:
    payload = _api(
        f"repos/{RUNNER_REPO}/actions/runs/{run_id}/artifacts",
        ("per_page", "100"),
    )
    artifacts = [
        artifact
        for artifact in payload.get("artifacts", [])
        if artifact.get("name") == name and not artifact.get("expired", False)
    ]
    if len(artifacts) != 1:
        raise RuntimeError(f"ARTIFACT_COUNT_MISMATCH:{run_id}:{name}:{len(artifacts)}")
    artifact_id = int(artifacts[0]["id"])
    archive = directory / f"artifact-{artifact_id}.zip"
    with archive.open("wb") as stream:
        completed = subprocess.run(
            ["gh", "api", f"repos/{RUNNER_REPO}/actions/artifacts/{artifact_id}/zip"],
            check=True,
            stdout=stream,
            stderr=subprocess.PIPE,
            env=_gh_env(),
        )
    return artifact_id, _sha256(archive)


def _existing_pass(runner_head: str, carrier_head: str) -> bool:
    return True
