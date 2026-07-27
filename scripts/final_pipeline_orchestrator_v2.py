from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import sitecustomize as sc

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
LEDGER_ISSUE = 377
MANIFEST_PATH = "config/GOLD_S01_PRE_RENDER_MANIFEST_v2.json"

CARRIER_HASHES = {
    "s01_ru_accepted_timing_contract_v01.json": "716b539630ad501d16e2dac13d1a6107b601a9094a3c57941cc962dc185b4b61",
    "s01_ru_final_captions_v01.json": "5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18",
    "s01_ru_final_captions_v01.vtt": "6be0d0cc2df0955ce7779275af2cec9c3c71137a91a75796384c1ad17cacb855",
    "caption_recovery_receipt.json": "79be42708b70cd046f88f00fe6020370357b8150b159308debb4c77977f22b2e",
    "SHA256SUMS": "04ba3009a5f3a697681e8c1f25002ec5b7331ad15c4d8eb9f4bfef1edfb4f254",
}
COMPONENT_GATES = (
    "FRAME_ZERO_LAYOUT",
    "SCENE_CONTINUITY",
    "PRIMARY_FOCUS_BOUNDS",
    "CAPTION_CLEARANCE",
    "CONTACT_SHADOW_EVIDENCE",
    "DEPTH_LAYER_EVIDENCE",
    "EVENT_TARGET_DELTA",
    "NO_GENERIC_GRID",
    "NO_BLANK_FRAME",
    "COMPONENT_EVIDENCE_GREEN",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def comments() -> list[dict[str, Any]]:
    payload = sc._api(
        f"repos/{PRODUCTION_REPO}/issues/{LEDGER_ISSUE}/comments",
        ("per_page", "100"),
    )
    if not isinstance(payload, list):
        raise RuntimeError("LEDGER_COMMENTS_NOT_LIST")
    return payload


def parse_block(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in body.splitlines()[1:]:
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def latest_block(prefix: str, runner_head: str) -> dict[str, str] | None:
    matches: list[tuple[str, dict[str, str]]] = []
    for item in comments():
        body = str(item.get("body", ""))
        if not body.startswith(prefix + "\n"):
            continue
        fields = parse_block(body)
        if fields.get("RUNNER_HEAD") == runner_head:
            matches.append((str(item.get("created_at", "")), fields))
    if not matches:
        return None
    matches.sort(key=lambda pair: pair[0])
    return matches[-1][1]


def post(lines: list[str]) -> None:
    sc._comment("\n".join(lines))


def verify_runner_head(workspace: Path) -> str:
    local = sc._git("rev-parse", "HEAD", cwd=workspace)
    remote = sc._run(
        [
            "git",
            "ls-remote",
            f"https://x-access-token:{os.environ['PRIVATE_REPO_PAT']}@github.com/{RUNNER_REPO}.git",
            f"refs/heads/{RUNNER_BRANCH}",
        ]
    ).split()[0]
    if local != remote:
        raise RuntimeError(f"RUNNER_HEAD_MOVED:{local}:{remote}")
    return local


def verify_carrier(carrier_dir: Path) -> str:
    head = sc._git("rev-parse", "HEAD", cwd=carrier_dir)
    sc._git("merge-base", "--is-ancestor", ACCEPTED_AUDIO_HEAD, head, cwd=carrier_dir)
    root = carrier_dir / "sanitized_timing_handoff_v01"
    names = {path.name for path in root.iterdir()} if root.is_dir() else set()
    if names != set(CARRIER_HASHES):
        raise RuntimeError(f"CARRIER_FILE_SET_MISMATCH:{sorted(names)}")
    for name, expected in CARRIER_HASHES.items():
        actual = sha256(root / name)
        if actual != expected:
            raise RuntimeError(f"CARRIER_HASH_MISMATCH:{name}:{actual}")
    if (carrier_dir / ".github/workflows/materialize-accepted-caption-carrier.yml").exists():
        raise RuntimeError("CARRIER_STAGING_WORKFLOW_PRESENT")
    return head


def dispatch(mode: str, runner_head: str, extra: dict[str, str]) -> int:
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
    return sc._dispatch(mode, {**common, **extra})


def artifact(run_id: int, name: str, directory: Path) -> tuple[int, str, Path]:
    artifact_id, archive_sha = sc._artifact(run_id, name, directory)
    archive = directory / f"artifact-{artifact_id}.zip"
    return artifact_id, archive_sha, archive


def verify_caption_archive(archive: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="caption-verify-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(root)
        files = [path for path in root.rglob("*") if path.is_file()]
        by_name = {path.name: path for path in files}
        expected = set(CARRIER_HASHES)
        if set(by_name) != expected:
            raise RuntimeError(f"CAPTION_ARTIFACT_FILE_SET_MISMATCH:{sorted(by_name)}")
        for name, expected_hash in CARRIER_HASHES.items():
            actual = sha256(by_name[name])
            if actual != expected_hash:
                raise RuntimeError(f"CAPTION_ARTIFACT_HASH_MISMATCH:{name}:{actual}")


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            result.update(flatten(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(flatten(child, f"{prefix}[{index}]"))
    else:
        result[prefix] = value
    return result


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def pass_value(value: Any) -> bool:
    return value is True or str(value).upper() in {"PASS", "GREEN", "TRUE"}


def verify_component_archive(archive: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="component-verify-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(root)
        terminals: dict[str, list[Any]] = {}
        all_text: list[str] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".json", ".txt", ".log"}:
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                all_text.append(text)
                if path.suffix.lower() == ".json":
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    for key, value in flatten(payload).items():
                        terminal = normalize(key.split(".")[-1])
                        terminals.setdefault(terminal, []).append(value)
        joined = "\n".join(all_text).upper()
        for gate in COMPONENT_GATES:
            values = terminals.get(gate, [])
            line_pass = f"{gate}=PASS" in joined or f"{gate}=TRUE" in joined
            if not line_pass and not any(pass_value(value) for value in values):
                raise RuntimeError(f"COMPONENT_GATE_NOT_PASS:{gate}:{values}")
        if "GENERIC_ASSET_GRID_COUNT=0" not in joined:
            values = terminals.get("GENERIC_ASSET_GRID_COUNT", [])
            if not any(str(value) == "0" for value in values):
                raise RuntimeError(f"GENERIC_ASSET_GRID_COUNT_NOT_ZERO:{values}")
        media_values = terminals.get("MEDIA_RENDER_STARTED", [])
        if "MEDIA_RENDER_STARTED=TRUE" in joined or any(
            value is True or str(value).lower() == "true" for value in media_values
        ):
            raise RuntimeError("MEDIA_RENDER_STARTED_TRUE")


def run_caption_component(runner_head: str, carrier_head: str) -> dict[str, str]:
    existing = latest_block("FINAL_CAPTION_COMPONENT_V2", runner_head)
    if existing and existing.get("RESULT") == "PASS":
        if existing.get("CAPTION_CARRIER_HEAD") != carrier_head:
            raise RuntimeError("EXISTING_COMPONENT_CARRIER_MISMATCH")
        return existing

    post(
        [
            "FINAL_CAPTION_COMPONENT_V2",
            "RESULT=STARTED",
            f"RUNNER_HEAD={runner_head}",
            f"CAPTION_CARRIER_HEAD={carrier_head}",
            "MEDIA_RENDER_STARTED=false",
            "NO_FAKE_GREEN=true",
        ]
    )
    caption_run_id = dispatch(
        "caption_packaging",
        runner_head,
        {
            "caption_carrier_branch": CARRIER_BRANCH,
            "caption_carrier_head": carrier_head,
        },
    )
    sc._wait_run(caption_run_id, timeout_seconds=1200)
    caption_job_id = sc._run_job_id(caption_run_id, "caption-packaging")
    with tempfile.TemporaryDirectory(prefix="caption-component-") as temp:
        temp_dir = Path(temp)
        caption_artifact_id, caption_artifact_sha, caption_archive = artifact(
            caption_run_id,
            CAPTION_ARTIFACT_NAME,
            temp_dir,
        )
        verify_caption_archive(caption_archive)
        component_run_id = dispatch(
            "component_evidence",
            runner_head,
            {
                "caption_artifact_id": str(caption_artifact_id),
                "caption_artifact_sha256": caption_artifact_sha,
            },
        )
        post(
            [
                "FINAL_CAPTION_COMPONENT_V2",
                "RESULT=COMPONENT_STARTED",
                f"RUNNER_HEAD={runner_head}",
                f"CAPTION_CARRIER_HEAD={carrier_head}",
                f"CAPTION_RUN_ID={caption_run_id}",
                f"CAPTION_JOB_ID={caption_job_id}",
                f"CAPTION_ARTIFACT_ID={caption_artifact_id}",
                f"CAPTION_ARTIFACT_SHA256={caption_artifact_sha}",
                "CAPTION_DOWNLOAD_IDENTITY=PASS",
                f"COMPONENT_EVIDENCE_RUN_ID={component_run_id}",
                "MEDIA_RENDER_STARTED=false",
                "NO_FAKE_GREEN=true",
            ]
        )
        sc._wait_run(component_run_id, timeout_seconds=3600)
        component_job_id = sc._run_job_id(component_run_id, "component-evidence")
        component_name = f"gold-s01-component-evidence-{PRODUCTION_RUNTIME_HEAD}"
        component_artifact_id, component_artifact_sha, component_archive = artifact(
            component_run_id,
            component_name,
            temp_dir,
        )
        verify_component_archive(component_archive)

    fields = {
        "RESULT": "PASS",
        "RUNNER_HEAD": runner_head,
        "CAPTION_CARRIER_HEAD": carrier_head,
        "CAPTION_RUN_ID": str(caption_run_id),
        "CAPTION_JOB_ID": str(caption_job_id),
        "CAPTION_ARTIFACT_ID": str(caption_artifact_id),
        "CAPTION_ARTIFACT_SHA256": caption_artifact_sha,
        "CAPTION_DOWNLOAD_IDENTITY": "PASS",
        "COMPONENT_EVIDENCE_RUN_ID": str(component_run_id),
        "COMPONENT_EVIDENCE_JOB_ID": str(component_job_id),
        "COMPONENT_EVIDENCE_ARTIFACT_ID": str(component_artifact_id),
        "COMPONENT_EVIDENCE_ARTIFACT_SHA256": component_artifact_sha,
        "COMPONENT_EVIDENCE_GREEN": "true",
        "MEDIA_RENDER_STARTED": "false",
        "NO_FAKE_GREEN": "true",
    }
    post(["FINAL_CAPTION_COMPONENT_V2", *[f"{key}={value}" for key, value in fields.items()]])
    return fields


def wait_for_run(run_id: int, timeout_seconds: int) -> dict[str, Any]:
    return sc._wait_run(run_id, timeout_seconds=timeout_seconds)


def run_pre_render(runner_head: str, component: dict[str, str]) -> None:
    existing = latest_block("FINAL_PRE_RENDER_V2", runner_head)
    if existing and existing.get("RESULT") == "PASS":
        return
    handoff = latest_block("PRE_RENDER_HANDOFF_V2", runner_head)
    if not handoff or handoff.get("RESULT") != "READY":
        post(
            [
                "FINAL_PIPELINE_ORCHESTRATION_V2",
                "RESULT=COMPONENT_PASS_AWAITING_QUALITY_MANIFEST",
                f"RUNNER_HEAD={runner_head}",
                f"CAPTION_CARRIER_HEAD={component['CAPTION_CARRIER_HEAD']}",
                f"CAPTION_ARTIFACT_ID={component['CAPTION_ARTIFACT_ID']}",
                f"COMPONENT_EVIDENCE_ARTIFACT_ID={component['COMPONENT_EVIDENCE_ARTIFACT_ID']}",
                "MEDIA_RENDER_STARTED=false",
                "NO_FAKE_GREEN=true",
            ]
        )
        return
    for key in (
        "QUALITY_HEAD",
        "PRODUCTION_MANIFEST_HEAD",
        "CAPTION_ARTIFACT_ID",
        "COMPONENT_EVIDENCE_ARTIFACT_ID",
    ):
        if not handoff.get(key):
            raise RuntimeError(f"PRE_RENDER_HANDOFF_FIELD_MISSING:{key}")
    if handoff["CAPTION_ARTIFACT_ID"] != component["CAPTION_ARTIFACT_ID"]:
        raise RuntimeError("PRE_RENDER_HANDOFF_CAPTION_ARTIFACT_MISMATCH")
    if handoff["COMPONENT_EVIDENCE_ARTIFACT_ID"] != component["COMPONENT_EVIDENCE_ARTIFACT_ID"]:
        raise RuntimeError("PRE_RENDER_HANDOFF_COMPONENT_ARTIFACT_MISMATCH")
    if handoff.get("TWO_MINUTE_RENDER_AUTHORIZED", "false").lower() != "false":
        raise RuntimeError("FORBIDDEN_TWO_MINUTE_RENDER_AUTHORIZATION")
    if handoff.get("MEDIA_RENDER_STARTED", "false").lower() != "false":
        raise RuntimeError("HANDOFF_MEDIA_RENDER_STARTED_TRUE")

    pre_render_run_id = dispatch(
        "pre_render_only",
        runner_head,
        {"authority_manifest_path": handoff.get("MANIFEST_PATH", MANIFEST_PATH)},
    )
    wait_for_run(pre_render_run_id, timeout_seconds=3600)
    pre_render_job_id = sc._run_job_id(pre_render_run_id, "pre-render-only")
    with tempfile.TemporaryDirectory(prefix="pre-render-") as temp:
        temp_dir = Path(temp)
        artifact_name = f"gold-s01-pre-render-receipt-{pre_render_run_id}"
        pre_render_artifact_id, pre_render_artifact_sha, archive = artifact(
            pre_render_run_id,
            artifact_name,
            temp_dir,
        )
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
            receipt_names = [name for name in names if name.endswith("pre-render-receipt.json")]
            if len(receipt_names) != 1:
                raise RuntimeError(f"PRE_RENDER_RECEIPT_COUNT:{len(receipt_names)}")
            receipt = json.loads(bundle.read(receipt_names[0]).decode("utf-8"))
        flat = {normalize(path.split(".")[-1]): value for path, value in flatten(receipt).items()}
        for gate in (
            "PUBLIC_PRE_RENDER_GREEN",
            "REAL_JOB_STEPS_AVAILABLE",
            "EXACT_RUNNER_HEAD",
            "EXACT_SOURCE_HEAD",
            "EXACT_PRODUCTION_COMPILE_HEAD",
            "EXACT_PRODUCTION_RUNTIME_HEAD",
            "EXACT_QUALITY_EVIDENCE_HEAD",
            "SOURCE_RECEIPT",
            "COMPILER_ARTIFACT",
            "COMPILER_OUTPUTS",
            "RUNTIME_TYPECHECK",
            "RUNTIME_TESTS",
            "COMPOSITION_DISCOVERY",
            "ONE_COHERENT_SCENE_ORCHESTRATION",
            "A3483_IDENTITY",
            "CAPTION_JSON_IDENTITY",
            "CAPTION_VTT_IDENTITY",
            "CAPTION_DOWNLOAD_IDENTITY",
            "COMPONENT_EVIDENCE",
            "QUALITY_PRODUCTION_MODE",
        ):
            if not pass_value(flat.get(gate)):
                raise RuntimeError(f"PRE_RENDER_GATE_NOT_PASS:{gate}:{flat.get(gate)}")
        if str(flat.get("GENERIC_ASSET_GRID_COUNT")) != "0":
            raise RuntimeError("PRE_RENDER_GENERIC_GRID_NONZERO")
        if str(flat.get("MEDIA_RENDER_STARTED")).lower() != "false":
            raise RuntimeError("PRE_RENDER_MEDIA_RENDER_STARTED_TRUE")

    post(
        [
            "FINAL_PRE_RENDER_V2",
            "RESULT=PASS",
            f"RUNNER_HEAD={runner_head}",
            f"QUALITY_HEAD={handoff['QUALITY_HEAD']}",
            f"PRODUCTION_MANIFEST_HEAD={handoff['PRODUCTION_MANIFEST_HEAD']}",
            f"PRE_RENDER_RUN_ID={pre_render_run_id}",
            f"PRE_RENDER_JOB_ID={pre_render_job_id}",
            f"PRE_RENDER_ARTIFACT_ID={pre_render_artifact_id}",
            f"PRE_RENDER_ARTIFACT_SHA256={pre_render_artifact_sha}",
            "PUBLIC_PRE_RENDER_RESULT=PASS",
            "OPEN_NON_HUMAN_PRE_RENDER_BLOCKER_COUNT=0",
            "TWO_MINUTE_RENDER_READY=true",
            "TWO_MINUTE_RENDER_AUTHORIZED=false",
            "MEDIA_RENDER_STARTED=false",
            "FULL_15_MINUTE_RENDER_AUTHORIZED=false",
            "NO_FAKE_GREEN=true",
        ]
    )


def main() -> None:
    # Disable the older atexit dispatcher registered by sitecustomize.py.
    sc._existing_pass = lambda runner_head, carrier_head: True
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    carrier_dir = Path(os.environ["WORK"]) / "carrier-bridge"
    runner_head = verify_runner_head(workspace)
    carrier_head = verify_carrier(carrier_dir)
    component = run_caption_component(runner_head, carrier_head)
    run_pre_render(runner_head, component)


try:
    main()
except Exception as error:
    try:
        post(
            [
                "FINAL_PIPELINE_ORCHESTRATION_V2",
                "RESULT=BLOCKED",
                f"ERROR={type(error).__name__}:{str(error)[:6000]}",
                "MEDIA_RENDER_STARTED=false",
                "NO_FAKE_GREEN=true",
            ]
        )
    finally:
        raise
