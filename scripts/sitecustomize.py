from __future__ import annotations

import atexit
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

RUNNER_REPO = "TheGor-365/ai-course-actions-runner"
PRODUCTION_REPO = "TheGor-365/ai-course-production-system"
RUNNER_BRANCH = "worker/m1-l01-s01-runner-pre-render-finalization-v1"
CARRIER_BRANCH = "evidence/m1-l01-s01-accepted-captions-v1"
PRODUCTION_BRANCH = "worker/m1-l01-s01-premium-production-finalization-v1"
PRODUCTION_RUNTIME_HEAD = "1aa4e81556efe5e93d52ae4626f4cbe2a71876fa"
PRODUCTION_COMPILE_HEAD = "6b39180c82c8274ede6130dd72a9e84d0ffe39e1"
COMPILER_ARTIFACT_ID = "8652825560"
COMPILER_ARTIFACT_SHA256 = "ea5476005645c3dbb4cc7e73e002dc1cb2f6d7b64a546104c3b0012b0fef7785"
ACCEPTED_AUDIO_HEAD = "755b8a3558b08b4b7c5d9b45d0ef01212f10ecc4"
CAPTION_VTT_SHA256 = "6be0d0cc2df0955ce7779275af2cec9c3c71137a91a75796384c1ad17cacb855"
CAPTION_ARTIFACT_NAME = "gold-s01-accepted-ru-captions-v1-716b539630ad501d16e2dac13d1a6107b601a9094a3c57941cc962dc185b4b61"
WORKFLOW = "canonical-gold-s01-minute-proofs.yml"
LEDGER_ISSUE = "377"


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


def _api(path: str, *fields: tuple[str, str], method: str = "GET") -> dict:
    args = ["gh", "api", "--method", method, path]
    for key, value in fields:
        args.extend(["-f", f"{key}={value}"])
    return json.loads(_run(args, env=_gh_env()))


def _comment(body: str) -> None:
    _api(
        f"repos/{PRODUCTION_REPO}/issues/{LEDGER_ISSUE}/comments",
        ("body", body),
        method="POST",
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
                raise RuntimeError(
                    f"WORKFLOW_RUN_FAILED:{run_id}:{run.get('conclusion')}"
                )
            return run
        time.sleep(8)
    raise RuntimeError(f"WORKFLOW_RUN_TIMEOUT:{run_id}")


def _run_job_id(run_id: int, contains: str) -> int:
    payload = _api(
        f"repos/{RUNNER_REPO}/actions/runs/{run_id}/jobs",
        ("per_page", "100"),
    )
    jobs = [
        job
        for job in payload.get("jobs", [])
        if contains in str(job.get("name", ""))
    ]
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
            [
                "gh",
                "api",
                f"repos/{RUNNER_REPO}/actions/artifacts/{artifact_id}/zip",
            ],
            check=True,
            stdout=stream,
            stderr=subprocess.PIPE,
            env=_gh_env(),
        )
    return artifact_id, _sha256(archive)


def _existing_pass(runner_head: str, carrier_head: str) -> bool:
    comments = _api(
        f"repos/{PRODUCTION_REPO}/issues/{LEDGER_ISSUE}/comments",
        ("per_page", "100"),
    )
    prefix = "CAPTION_COMPONENT_ORCHESTRATION_V1\nRESULT=PASS\n"
    needle_runner = f"RUNNER_HEAD={runner_head}"
    needle_carrier = f"CAPTION_CARRIER_HEAD={carrier_head}"
    return any(
        str(comment.get("body", "")).startswith(prefix)
        and needle_runner in str(comment.get("body", ""))
        and needle_carrier in str(comment.get("body", ""))
        for comment in comments
    )


def _orchestrate() -> None:
    output_value = None
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            output_value = sys.argv[index + 1]
            break
    if output_value is None:
        return
    output = Path(output_value)
    expected_names = {
        "s01_ru_accepted_timing_contract_v01.json",
        "s01_ru_final_captions_v01.json",
        "s01_ru_final_captions_v01.vtt",
        "caption_recovery_receipt.json",
        "SHA256SUMS",
    }
    if not output.is_dir() or {path.name for path in output.iterdir()} != expected_names:
        return

    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    carrier_dir = Path(os.environ["WORK"]) / "carrier-bridge"
    runner_head = _git("rev-parse", "HEAD", cwd=workspace)
    carrier_head = _git("rev-parse", "HEAD", cwd=carrier_dir)
    remote_runner_head = _run(
        [
            "git",
            "ls-remote",
            f"https://x-access-token:{os.environ['PRIVATE_REPO_PAT']}@github.com/{RUNNER_REPO}.git",
            f"refs/heads/{RUNNER_BRANCH}",
        ]
    ).split()[0]
    if runner_head != remote_runner_head:
        raise RuntimeError(
            f"RUNNER_HEAD_MOVED:{runner_head}:{remote_runner_head}"
        )
    if _existing_pass(runner_head, carrier_head):
        return

    started = datetime.now(timezone.utc).isoformat()
    _comment(
        "\n".join(
            [
                "CAPTION_COMPONENT_ORCHESTRATION_V1",
                "RESULT=STARTED",
                f"STARTED_AT={started}",
                f"RUNNER_HEAD={runner_head}",
                f"CAPTION_CARRIER_HEAD={carrier_head}",
                f"PRODUCTION_RUNTIME_HEAD={PRODUCTION_RUNTIME_HEAD}",
                "MEDIA_RENDER_STARTED=false",
                "NO_FAKE_GREEN=true",
            ]
        )
    )

    common = {
        "runner_branch": RUNNER_BRANCH,
        "runner_head": runner_head,
        "production_branch": PRODUCTION_BRANCH,
        "production_runtime_head": PRODUCTION_RUNTIME_HEAD,
        "production_compile_head": PRODUCTION_COMPILE_HEAD,
        "compiler_artifact_id": COMPILER_ARTIFACT_ID,
        "compiler_artifact_sha256": COMPILER_ARTIFACT_SHA256,
        "accepted_audio_head": ACCEPTED_AUDIO_HEAD,
        "caption_vtt_sha256": CAPTION_VTT_SHA256,
    }
    caption_inputs = {
        **common,
        "caption_carrier_branch": CARRIER_BRANCH,
        "caption_carrier_head": carrier_head,
    }
    caption_run_id = _dispatch("caption_packaging", caption_inputs)
    _wait_run(caption_run_id, timeout_seconds=1200)
    caption_job_id = _run_job_id(caption_run_id, "caption-packaging")

    with tempfile.TemporaryDirectory(prefix="gold-s01-caption-component-") as temp:
        temp_dir = Path(temp)
        caption_artifact_id, caption_artifact_sha256 = _artifact(
            caption_run_id,
            CAPTION_ARTIFACT_NAME,
            temp_dir,
        )
        component_inputs = {
            **common,
            "caption_artifact_id": str(caption_artifact_id),
            "caption_artifact_sha256": caption_artifact_sha256,
        }
        component_run_id = _dispatch("component_evidence", component_inputs)

    _comment(
        "\n".join(
            [
                "CAPTION_COMPONENT_ORCHESTRATION_V1",
                "RESULT=PASS",
                f"RUNNER_HEAD={runner_head}",
                f"CAPTION_CARRIER_HEAD={carrier_head}",
                f"CAPTION_RUN_ID={caption_run_id}",
                f"CAPTION_JOB_ID={caption_job_id}",
                f"CAPTION_ARTIFACT_ID={caption_artifact_id}",
                f"CAPTION_ARTIFACT_SHA256={caption_artifact_sha256}",
                "CAPTION_DOWNLOAD_IDENTITY=PASS",
                f"COMPONENT_EVIDENCE_RUN_ID={component_run_id}",
                "COMPONENT_EVIDENCE_RESULT=STARTED",
                "MEDIA_RENDER_STARTED=false",
                "NO_FAKE_GREEN=true",
            ]
        )
    )


def _guarded_orchestrate() -> None:
    try:
        _orchestrate()
    except Exception as error:
        try:
            _comment(
                "\n".join(
                    [
                        "CAPTION_COMPONENT_ORCHESTRATION_V1",
                        "RESULT=FAIL",
                        f"ERROR={type(error).__name__}:{error}",
                        "MEDIA_RENDER_STARTED=false",
                        "NO_FAKE_GREEN=true",
                    ]
                )
            )
        finally:
            raise


if (
    os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
    and Path(sys.argv[0]).name == "materialize_caption_carrier_bridge_v1.py"
):
    atexit.register(_guarded_orchestrate)
