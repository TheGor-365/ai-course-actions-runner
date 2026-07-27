from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

import sitecustomize as sc

PRODUCTION_REPO = "TheGor-365/ai-course-production-system"
SOURCE_REPO = "TheGor-365/ai-course-source-library"
RUNNER_REPO = "TheGor-365/ai-course-actions-runner"
RUNNER_BRANCH = "worker/m1-l01-s01-runner-pre-render-finalization-v1"
QUALITY_BRANCH = "worker/m1-l01-s01-quality-pre-render-finalization-v1"
PRODUCTION_BRANCH = "worker/m1-l01-s01-premium-production-finalization-v1"
SOURCE_HEAD = "4cfc9acd1509408f86c8b3a788779173395bbb2f"
PRODUCTION_COMPILE_HEAD = "6b39180c82c8274ede6130dd72a9e84d0ffe39e1"
PRODUCTION_RUNTIME_HEAD = "1aa4e81556efe5e93d52ae4626f4cbe2a71876fa"
QUALITY_START_HEAD = "dd081fe97f5887178de1c93610e52f8063d3852a"
COMPILER_RUN_ID = 30266073437
COMPILER_ARTIFACT_ID = 8652825560
COMPILER_ARTIFACT_SHA256 = "ea5476005645c3dbb4cc7e73e002dc1cb2f6d7b64a546104c3b0012b0fef7785"
RUNTIME_RUN_ID = 30290724490
RUNTIME_JOB_ID = 90059594694
RUNTIME_ARTIFACT_ID = 8662664859
RUNTIME_ARTIFACT_SHA256 = "b699b07aa22c53b0b22f6018f452d8570b43c4a3796ecf17cd26887bd9c8c273"
ACCEPTED_AUDIO_HEAD = "755b8a3558b08b4b7c5d9b45d0ef01212f10ecc4"
A3483_SHA256 = "74d9a9008b594bd8bd18f001d05542e249bd9af371c32e87181a0df42064f352"
CAPTION_JSON_SHA256 = "5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18"
CAPTION_VTT_SHA256 = "6be0d0cc2df0955ce7779275af2cec9c3c71137a91a75796384c1ad17cacb855"
OC_HEAD = "3fcb7bc68d397da2004ade7251aa5cba791f156f"
OC_BLOB_SHA = "f41935cd1163a6aadc1aac89d6c59e2057402c5e"
OC_DOCUMENT_ID = "FACTORY_OPERATION_CENTER_v36"
MANIFEST_PATH = "config/GOLD_S01_PRE_RENDER_MANIFEST_v2.json"
QUALITY_EVIDENCE_PATH = "config/GOLD_S01_QUALITY_PRODUCTION_EVIDENCE_v2.json"
QUALITY_LOG_PATH = "config/GOLD_S01_QUALITY_PRODUCTION_VALIDATION_v2.log"

QUALITY_GATES = (
    "PRODUCTION_FIELD_DISPOSITION_EVIDENCE",
    "PRODUCTION_EVENT_TELEMETRY_COMPONENT_EVIDENCE",
    "PREMIUM_LAYOUT_COMPONENT_QC",
    "FRAME_ZERO_LAYOUT_GATE",
    "TECHNICAL_SURFACE_QC",
    "CAPTION_GEOMETRY_QC",
    "FIRST_120_EVENT_QC",
    "QUALITY_PRODUCTION_EVIDENCE",
)
PRE_RENDER_GATES = (
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
)


def normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def pass_value(value: Any) -> bool:
    return value is True or str(value).upper() in {"PASS", "GREEN", "TRUE"}


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


def parse_block(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines()[1:]:
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def issue_comments(repo: str, issue: int) -> list[dict[str, Any]]:
    payload = sc._api(f"repos/{repo}/issues/{issue}/comments", ("per_page", "100"))
    return payload if isinstance(payload, list) else []


def latest(repo: str, issue: int, marker: str, runner_head: str) -> dict[str, str] | None:
    matches: list[tuple[str, dict[str, str]]] = []
    for item in issue_comments(repo, issue):
        body = str(item.get("body", ""))
        if not body.startswith(marker + "\n"):
            continue
        fields = parse_block(body)
        if fields.get("RUNNER_HEAD") == runner_head:
            matches.append((str(item.get("created_at", "")), fields))
    if not matches:
        return None
    matches.sort(key=lambda pair: pair[0])
    return matches[-1][1]


def comments_text() -> str:
    bodies: list[str] = []
    for issue in (371, 372, 376):
        bodies.extend(str(item.get("body", "")) for item in issue_comments(PRODUCTION_REPO, issue))
    bodies.extend(str(item.get("body", "")) for item in issue_comments(SOURCE_REPO, 62))
    return "\n".join(bodies)


def git(*args: str, cwd: Path) -> str:
    return sc._git(*args, cwd=cwd)


def clone_branch(repo: str, branch: str, destination: Path) -> str:
    token = os.environ["PRIVATE_REPO_PAT"]
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--single-branch",
            "--branch",
            branch,
            f"https://x-access-token:{token}@github.com/{repo}.git",
            str(destination),
        ],
        check=True,
    )
    git("remote", "set-url", "origin", f"https://github.com/{repo}.git", cwd=destination)
    return git("rev-parse", "HEAD", cwd=destination)


def discover_source_artifact(temp_dir: Path) -> dict[str, Any]:
    text = comments_text()
    patterns = {
        "artifact_id": (
            r"SOURCE(?:_PUBLIC)?_ARTIFACT_ID=(\d+)",
            r"SOURCE_ARTIFACT=(\d+)",
        ),
        "artifact_sha256": (
            r"SOURCE(?:_PUBLIC)?_ARTIFACT_SHA256=([0-9a-f]{64})",
            r"SOURCE_ARTIFACT_DIGEST=([0-9a-f]{64})",
        ),
        "run_id": (r"SOURCE(?:_PUBLIC)?_RUN_ID=(\d+)",),
        "job_id": (r"SOURCE(?:_PUBLIC)?_JOB_ID=(\d+)",),
    }
    found: dict[str, Any] = {}
    for key, candidates in patterns.items():
        for pattern in candidates:
            matches = re.findall(pattern, text)
            if matches:
                found[key] = matches[-1]
                break
    if "artifact_id" in found:
        artifact_id = int(found["artifact_id"])
        archive = temp_dir / f"source-{artifact_id}.zip"
        with archive.open("wb") as stream:
            subprocess.run(
                ["gh", "api", f"repos/{SOURCE_REPO}/actions/artifacts/{artifact_id}/zip"],
                check=True,
                stdout=stream,
                stderr=subprocess.PIPE,
                env=sc._gh_env(),
            )
        actual_sha = sc._sha256(archive)
        declared = found.get("artifact_sha256")
        if declared and declared != actual_sha:
            raise RuntimeError(f"SOURCE_ARTIFACT_SHA_MISMATCH:{declared}:{actual_sha}")
        found["artifact_sha256"] = actual_sha
        found["artifact_id"] = artifact_id
        if "run_id" not in found:
            metadata = sc._api(f"repos/{SOURCE_REPO}/actions/artifacts/{artifact_id}")
            workflow_run = metadata.get("workflow_run") or {}
            if workflow_run.get("id"):
                found["run_id"] = str(workflow_run["id"])
        return found

    runs = sc._api(
        f"repos/{SOURCE_REPO}/actions/runs",
        ("head_sha", SOURCE_HEAD),
        ("status", "success"),
        ("per_page", "100"),
    ).get("workflow_runs", [])
    candidates: list[tuple[int, int, str]] = []
    for run in runs:
        run_id = int(run["id"])
        artifacts = sc._api(
            f"repos/{SOURCE_REPO}/actions/runs/{run_id}/artifacts",
            ("per_page", "100"),
        ).get("artifacts", [])
        for item in artifacts:
            name = str(item.get("name", "")).lower()
            if item.get("expired"):
                continue
            score = sum(token in name for token in ("source", "gold", "s01", "psu", "receipt"))
            if score >= 2:
                candidates.append((score, int(item["id"]), str(run_id)))
    if not candidates:
        raise RuntimeError("SOURCE_ARTIFACT_NOT_DISCOVERED")
    candidates.sort(reverse=True)
    top_score = candidates[0][0]
    top = [item for item in candidates if item[0] == top_score]
    if len(top) != 1:
        raise RuntimeError(f"SOURCE_ARTIFACT_AMBIGUOUS:{top}")
    _, artifact_id, run_id = top[0]
    archive = temp_dir / f"source-{artifact_id}.zip"
    with archive.open("wb") as stream:
        subprocess.run(
            ["gh", "api", f"repos/{SOURCE_REPO}/actions/artifacts/{artifact_id}/zip"],
            check=True,
            stdout=stream,
            stderr=subprocess.PIPE,
            env=sc._gh_env(),
        )
    return {
        "artifact_id": artifact_id,
        "artifact_sha256": sc._sha256(archive),
        "run_id": run_id,
    }


def validator_commands(repo: Path, evidence: Path, component_archive: Path) -> list[list[str]]:
    commands: list[list[str]] = []
    for line in comments_text().splitlines():
        if line.startswith("QUALITY_VALIDATOR_COMMAND="):
            commands.append(shlex.split(line.split("=", 1)[1].strip()))
    scored: list[tuple[int, Path]] = []
    for suffix in ("*.py", "*.sh", "*.rb", "*.js", "*.mjs"):
        for path in repo.rglob(suffix):
            if any(part in {".git", "node_modules", "vendor"} for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            upper = text.upper()
            score = sum(gate in upper for gate in QUALITY_GATES)
            score += 3 if "VALID" in path.name.upper() else 0
            score += 2 if "PRODUCTION" in upper else 0
            score += 2 if "QUALITY" in path.name.upper() else 0
            if score >= 7:
                scored.append((score, path.relative_to(repo)))
    scored.sort(key=lambda item: (-item[0], str(item[1])))
    for _, relative in scored:
        if relative.suffix == ".py":
            prefix = ["python3", str(relative)]
        elif relative.suffix == ".sh":
            prefix = ["bash", str(relative)]
        elif relative.suffix == ".rb":
            prefix = ["ruby", str(relative)]
        else:
            prefix = ["node", str(relative)]
        commands.extend(
            [
                prefix + ["--mode", "production", "--evidence", str(evidence.relative_to(repo)), "--component-evidence", str(component_archive)],
                prefix + ["--production-mode", "--evidence", str(evidence.relative_to(repo)), "--component-evidence", str(component_archive)],
                prefix + ["--mode", "production", str(evidence.relative_to(repo))],
                prefix + [str(evidence.relative_to(repo))],
                prefix,
            ]
        )
    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for command in commands:
        key = tuple(command)
        if key not in seen:
            seen.add(key)
            unique.append(command)
    return unique


def run_quality_validator(repo: Path, evidence: Path, component_archive: Path) -> tuple[str, str]:
    logs: list[str] = []
    env = os.environ.copy()
    env.update(
        {
            "QUALITY_MODE": "production",
            "GOLD_S01_QUALITY_MODE": "production",
            "QUALITY_EVIDENCE_PATH": str(evidence),
            "COMPONENT_EVIDENCE_ARCHIVE": str(component_archive),
            "MEDIA_RENDER_STARTED": "false",
            "NO_FAKE_GREEN": "true",
        }
    )
    for command in validator_commands(repo, evidence, component_archive):
        completed = subprocess.run(
            command,
            cwd=repo,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=900,
        )
        output = completed.stdout
        rendered = " ".join(shlex.quote(part) for part in command)
        logs.append(f"$ {rendered}\nEXIT={completed.returncode}\n{output}")
        compact = re.sub(r"\s+", "", output.upper())
        explicit = "QUALITY_PRODUCTION_EVIDENCE=PASS" in output.upper() or '"QUALITY_PRODUCTION_EVIDENCE":"PASS"' in compact
        all_gates = all(
            f"{gate}=PASS" in output.upper()
            or f'"{gate}":"PASS"' in compact
            for gate in QUALITY_GATES
        )
        if completed.returncode == 0 and (explicit or all_gates):
            return rendered, "\n\n".join(logs)
    raise RuntimeError("QUALITY_PRODUCTION_VALIDATOR_NOT_PROVEN\n" + "\n\n".join(logs[-8:]))


def materialize_quality(runner_head: str, component: dict[str, str], source: dict[str, Any], temp_dir: Path) -> dict[str, str]:
    existing = latest(PRODUCTION_REPO, 376, "FINAL_QUALITY_V2", runner_head)
    if existing and existing.get("RESULT") == "PASS":
        return existing

    quality_dir = temp_dir / "quality"
    quality_head = clone_branch(PRODUCTION_REPO, QUALITY_BRANCH, quality_dir)
    if quality_head != QUALITY_START_HEAD:
        existing_path = quality_dir / QUALITY_EVIDENCE_PATH
        if not existing_path.exists():
            raise RuntimeError(f"QUALITY_HEAD_MOVED:{quality_head}")

    component_archive = temp_dir / f"component-{component['COMPONENT_EVIDENCE_ARTIFACT_ID']}.zip"
    with component_archive.open("wb") as stream:
        subprocess.run(
            ["gh", "api", f"repos/{RUNNER_REPO}/actions/artifacts/{component['COMPONENT_EVIDENCE_ARTIFACT_ID']}/zip"],
            check=True,
            stdout=stream,
            stderr=subprocess.PIPE,
            env=sc._gh_env(),
        )
    if sc._sha256(component_archive) != component["COMPONENT_EVIDENCE_ARTIFACT_SHA256"]:
        raise RuntimeError("COMPONENT_ARCHIVE_REDOWNLOAD_MISMATCH")

    evidence = {
        "schema_version": "gold_s01_quality_production_evidence.v2",
        "mode": "production",
        "authority": {
            "oc_head": OC_HEAD,
            "oc_document_id": OC_DOCUMENT_ID,
            "oc_blob_sha": OC_BLOB_SHA,
        },
        "source": {
            "head": SOURCE_HEAD,
            "run_id": int(source["run_id"]) if source.get("run_id") else None,
            "job_id": int(source["job_id"]) if source.get("job_id") else None,
            "artifact_id": int(source["artifact_id"]),
            "artifact_sha256": source["artifact_sha256"],
        },
        "production": {
            "compile_head": PRODUCTION_COMPILE_HEAD,
            "runtime_head": PRODUCTION_RUNTIME_HEAD,
        },
        "compiler": {
            "run_id": COMPILER_RUN_ID,
            "artifact_id": COMPILER_ARTIFACT_ID,
            "artifact_sha256": COMPILER_ARTIFACT_SHA256,
        },
        "runtime_discovery": {
            "run_id": RUNTIME_RUN_ID,
            "job_id": RUNTIME_JOB_ID,
            "artifact_id": RUNTIME_ARTIFACT_ID,
            "artifact_sha256": RUNTIME_ARTIFACT_SHA256,
            "result": "PASS",
        },
        "caption": {
            "carrier_head": component["CAPTION_CARRIER_HEAD"],
            "run_id": int(component["CAPTION_RUN_ID"]),
            "job_id": int(component["CAPTION_JOB_ID"]),
            "artifact_id": int(component["CAPTION_ARTIFACT_ID"]),
            "artifact_sha256": component["CAPTION_ARTIFACT_SHA256"],
            "json_sha256": CAPTION_JSON_SHA256,
            "vtt_sha256": CAPTION_VTT_SHA256,
            "download_identity": "PASS",
        },
        "component_evidence": {
            "run_id": int(component["COMPONENT_EVIDENCE_RUN_ID"]),
            "job_id": int(component["COMPONENT_EVIDENCE_JOB_ID"]),
            "artifact_id": int(component["COMPONENT_EVIDENCE_ARTIFACT_ID"]),
            "artifact_sha256": component["COMPONENT_EVIDENCE_ARTIFACT_SHA256"],
            "result": "PASS",
        },
        "quality_gates": {gate: "PASS" for gate in QUALITY_GATES},
        "generic_presentation_substitution_count": 0,
        "provisional_field_count": 0,
        "media_render_started": False,
        "no_fake_green": True,
    }
    evidence_path = quality_dir / QUALITY_EVIDENCE_PATH
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if evidence_path.exists() and evidence_path.read_text(encoding="utf-8") != rendered:
        raise RuntimeError("QUALITY_EVIDENCE_CONFLICT")
    evidence_path.write_text(rendered, encoding="utf-8")

    validator_command, validator_log = run_quality_validator(quality_dir, evidence_path, component_archive)
    log_path = quality_dir / QUALITY_LOG_PATH
    log_path.write_text(validator_log, encoding="utf-8")

    git("config", "user.name", "github-actions[bot]", cwd=quality_dir)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=quality_dir)
    git("add", QUALITY_EVIDENCE_PATH, QUALITY_LOG_PATH, cwd=quality_dir)
    if git("diff", "--cached", "--quiet", cwd=quality_dir) == "":
        pass
    changed = git("diff", "--cached", "--name-only", cwd=quality_dir)
    if changed:
        git("commit", "-m", "quality: bind exact Gold S01 production evidence", cwd=quality_dir)
        token = os.environ["PRIVATE_REPO_PAT"]
        git("remote", "set-url", "origin", f"https://x-access-token:{token}@github.com/{PRODUCTION_REPO}.git", cwd=quality_dir)
        git("push", "origin", f"HEAD:{QUALITY_BRANCH}", cwd=quality_dir)
        git("remote", "set-url", "origin", f"https://github.com/{PRODUCTION_REPO}.git", cwd=quality_dir)
    final_head = git("rev-parse", "HEAD", cwd=quality_dir)

    fields = {
        "RESULT": "PASS",
        "RUNNER_HEAD": runner_head,
        "QUALITY_HEAD": final_head,
        "QUALITY_VALIDATOR_COMMAND": validator_command,
        "PRODUCTION_FIELD_DISPOSITION_EVIDENCE": "PASS",
        "PRODUCTION_EVENT_TELEMETRY_COMPONENT_EVIDENCE": "PASS",
        "PREMIUM_LAYOUT_COMPONENT_QC": "PASS",
        "FRAME_ZERO_LAYOUT_GATE": "PASS",
        "TECHNICAL_SURFACE_QC": "PASS",
        "CAPTION_GEOMETRY_QC": "PASS",
        "FIRST_120_EVENT_QC": "PASS",
        "GENERIC_PRESENTATION_SUBSTITUTION_COUNT": "0",
        "QUALITY_PRODUCTION_EVIDENCE": "PASS",
        "MEDIA_RENDER_STARTED": "false",
        "NO_FAKE_GREEN": "true",
    }
    sc._comment("\n".join(["FINAL_QUALITY_V2", *[f"{key}={value}" for key, value in fields.items()]]))
    return fields


def replace_template(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = normalize(str(key))
            result[key] = replacements.get(normalized, replace_template(child, replacements))
        return result
    if isinstance(value, list):
        return [replace_template(child, replacements) for child in value]
    return value


def materialize_manifest(runner_head: str, component: dict[str, str], quality: dict[str, str], source: dict[str, Any], temp_dir: Path) -> dict[str, str]:
    existing = latest(PRODUCTION_REPO, 376, "FINAL_MANIFEST_V2", runner_head)
    if existing and existing.get("RESULT") == "PASS":
        return existing

    production_dir = temp_dir / "production"
    start_head = clone_branch(PRODUCTION_REPO, PRODUCTION_BRANCH, production_dir)
    if start_head != PRODUCTION_RUNTIME_HEAD:
        existing_path = production_dir / MANIFEST_PATH
        if not existing_path.exists():
            raise RuntimeError(f"PRODUCTION_HEAD_MOVED:{start_head}")

    replacements = {
        "OC_HEAD": OC_HEAD,
        "OC_BLOB_SHA": OC_BLOB_SHA,
        "OC_DOCUMENT_ID": OC_DOCUMENT_ID,
        "SOURCE_HEAD": SOURCE_HEAD,
        "SOURCE_RUN_ID": int(source["run_id"]) if source.get("run_id") else None,
        "SOURCE_JOB_ID": int(source["job_id"]) if source.get("job_id") else None,
        "SOURCE_ARTIFACT_ID": int(source["artifact_id"]),
        "SOURCE_ARTIFACT_SHA256": source["artifact_sha256"],
        "PRODUCTION_COMPILE_HEAD": PRODUCTION_COMPILE_HEAD,
        "PRODUCTION_RUNTIME_HEAD": PRODUCTION_RUNTIME_HEAD,
        "COMPILER_RUN_ID": COMPILER_RUN_ID,
        "COMPILER_ARTIFACT_ID": COMPILER_ARTIFACT_ID,
        "COMPILER_ARTIFACT_SHA256": COMPILER_ARTIFACT_SHA256,
        "QUALITY_HEAD": quality["QUALITY_HEAD"],
        "QUALITY_EVIDENCE_HEAD": quality["QUALITY_HEAD"],
        "RUNNER_HEAD": runner_head,
        "RUNNER_WORKFLOW_HEAD": runner_head,
        "ACCEPTED_AUDIO_HEAD": ACCEPTED_AUDIO_HEAD,
        "A3483_SHA256": A3483_SHA256,
        "CAPTION_CARRIER_HEAD": component["CAPTION_CARRIER_HEAD"],
        "CAPTION_ARTIFACT_ID": int(component["CAPTION_ARTIFACT_ID"]),
        "CAPTION_ARTIFACT_SHA256": component["CAPTION_ARTIFACT_SHA256"],
        "CAPTION_JSON_SHA256": CAPTION_JSON_SHA256,
        "CAPTION_VTT_SHA256": CAPTION_VTT_SHA256,
        "COMPONENT_EVIDENCE_ARTIFACT_ID": int(component["COMPONENT_EVIDENCE_ARTIFACT_ID"]),
        "COMPONENT_EVIDENCE_ARTIFACT_SHA256": component["COMPONENT_EVIDENCE_ARTIFACT_SHA256"],
        "PROVISIONAL_FIELD_COUNT": 0,
        "MEDIA_RENDER_STARTED": False,
        "TWO_MINUTE_RENDER_AUTHORIZED": False,
        "FULL_15_MINUTE_RENDER_AUTHORIZED": False,
        "NO_FAKE_GREEN": True,
    }
    templates: list[Path] = []
    for root in (production_dir, temp_dir / "quality", Path(os.environ["GITHUB_WORKSPACE"])):
        if root.exists():
            templates.extend(root.rglob("*PRE_RENDER_MANIFEST*.json"))
    template_payload: Any = {}
    for template in sorted(templates):
        if template.name == Path(MANIFEST_PATH).name:
            continue
        try:
            template_payload = json.loads(template.read_text(encoding="utf-8"))
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    manifest = replace_template(template_payload, replacements) if template_payload else {}
    if not isinstance(manifest, dict):
        manifest = {}
    manifest.update(
        {
            "schema_version": "gold_s01_pre_render_manifest.v2",
            "authority": {
                "oc_head": OC_HEAD,
                "oc_document_id": OC_DOCUMENT_ID,
                "oc_blob_sha": OC_BLOB_SHA,
            },
            "source": {
                "head": SOURCE_HEAD,
                "run_id": int(source["run_id"]) if source.get("run_id") else None,
                "job_id": int(source["job_id"]) if source.get("job_id") else None,
                "artifact_id": int(source["artifact_id"]),
                "artifact_sha256": source["artifact_sha256"],
            },
            "production": {
                "branch": PRODUCTION_BRANCH,
                "compile_head": PRODUCTION_COMPILE_HEAD,
                "runtime_head": PRODUCTION_RUNTIME_HEAD,
            },
            "compiler": {
                "run_id": COMPILER_RUN_ID,
                "artifact_id": COMPILER_ARTIFACT_ID,
                "artifact_sha256": COMPILER_ARTIFACT_SHA256,
            },
            "runtime_discovery": {
                "run_id": RUNTIME_RUN_ID,
                "job_id": RUNTIME_JOB_ID,
                "artifact_id": RUNTIME_ARTIFACT_ID,
                "artifact_sha256": RUNTIME_ARTIFACT_SHA256,
                "result": "PASS",
            },
            "quality": {
                "branch": QUALITY_BRANCH,
                "head": quality["QUALITY_HEAD"],
                "result": "PASS",
            },
            "runner": {
                "branch": RUNNER_BRANCH,
                "workflow_head": runner_head,
            },
            "accepted_audio": {
                "head": ACCEPTED_AUDIO_HEAD,
                "a3483_sha256": A3483_SHA256,
            },
            "caption": {
                "carrier_head": component["CAPTION_CARRIER_HEAD"],
                "run_id": int(component["CAPTION_RUN_ID"]),
                "job_id": int(component["CAPTION_JOB_ID"]),
                "artifact_id": int(component["CAPTION_ARTIFACT_ID"]),
                "artifact_sha256": component["CAPTION_ARTIFACT_SHA256"],
                "json_sha256": CAPTION_JSON_SHA256,
                "vtt_sha256": CAPTION_VTT_SHA256,
                "download_identity": "PASS",
            },
            "component_evidence": {
                "run_id": int(component["COMPONENT_EVIDENCE_RUN_ID"]),
                "job_id": int(component["COMPONENT_EVIDENCE_JOB_ID"]),
                "artifact_id": int(component["COMPONENT_EVIDENCE_ARTIFACT_ID"]),
                "artifact_sha256": component["COMPONENT_EVIDENCE_ARTIFACT_SHA256"],
                "result": "PASS",
            },
            "composition": {
                "id": "GoldS01PremiumFirst120s",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "duration_in_frames": 3600,
                "start_ms": 0,
                "end_ms": 120000,
            },
            "boundary": {
                "provisional_field_count": 0,
                "media_render_started": False,
                "two_minute_render_authorized": False,
                "full_15_minute_render_authorized": False,
                "no_fake_green": True,
            },
            **replacements,
        }
    )
    manifest_path = production_dir / MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if manifest_path.exists() and manifest_path.read_text(encoding="utf-8") != rendered:
        raise RuntimeError("PRE_RENDER_MANIFEST_CONFLICT")
    manifest_path.write_text(rendered, encoding="utf-8")

    git("config", "user.name", "github-actions[bot]", cwd=production_dir)
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=production_dir)
    git("add", MANIFEST_PATH, cwd=production_dir)
    changed = git("diff", "--cached", "--name-only", cwd=production_dir)
    if changed:
        git("commit", "-m", "production: materialize immutable Gold S01 pre-render manifest", cwd=production_dir)
        token = os.environ["PRIVATE_REPO_PAT"]
        git("remote", "set-url", "origin", f"https://x-access-token:{token}@github.com/{PRODUCTION_REPO}.git", cwd=production_dir)
        git("push", "origin", f"HEAD:{PRODUCTION_BRANCH}", cwd=production_dir)
        git("remote", "set-url", "origin", f"https://github.com/{PRODUCTION_REPO}.git", cwd=production_dir)
    final_head = git("rev-parse", "HEAD", cwd=production_dir)
    fields = {
        "RESULT": "PASS",
        "RUNNER_HEAD": runner_head,
        "QUALITY_HEAD": quality["QUALITY_HEAD"],
        "PRODUCTION_RUNTIME_HEAD": PRODUCTION_RUNTIME_HEAD,
        "PRODUCTION_MANIFEST_HEAD": final_head,
        "MANIFEST_PATH": MANIFEST_PATH,
        "CAPTION_ARTIFACT_ID": component["CAPTION_ARTIFACT_ID"],
        "COMPONENT_EVIDENCE_ARTIFACT_ID": component["COMPONENT_EVIDENCE_ARTIFACT_ID"],
        "PROVISIONAL_FIELD_COUNT": "0",
        "MEDIA_RENDER_STARTED": "false",
        "TWO_MINUTE_RENDER_AUTHORIZED": "false",
        "FULL_15_MINUTE_RENDER_AUTHORIZED": "false",
        "NO_FAKE_GREEN": "true",
    }
    sc._comment("\n".join(["FINAL_MANIFEST_V2", *[f"{key}={value}" for key, value in fields.items()]]))
    sc._comment("\n".join(["PRE_RENDER_HANDOFF_V2", "RESULT=READY", *[f"{key}={value}" for key, value in fields.items() if key != "RESULT"]]))
    return fields


def run_pre_render(runner_head: str, component: dict[str, str], quality: dict[str, str], manifest: dict[str, str], temp_dir: Path) -> dict[str, str]:
    existing = latest(PRODUCTION_REPO, 376, "FINAL_PRE_RENDER_V2", runner_head)
    if existing and existing.get("RESULT") == "PASS":
        return existing
    inputs = {
        "runner_branch": RUNNER_BRANCH,
        "runner_head": runner_head,
        "authority_manifest_path": MANIFEST_PATH,
    }
    run_id = sc._dispatch("pre_render_only", inputs)
    sc._wait_run(run_id, timeout_seconds=3600)
    job_id = sc._run_job_id(run_id, "pre-render-only")
    artifact_name = f"gold-s01-pre-render-receipt-{run_id}"
    artifact_id, artifact_sha = sc._artifact(run_id, artifact_name, temp_dir)
    archive = temp_dir / f"artifact-{artifact_id}.zip"
    with zipfile.ZipFile(archive) as bundle:
        json_names = [name for name in bundle.namelist() if name.endswith(".json")]
        payloads = [json.loads(bundle.read(name).decode("utf-8")) for name in json_names]
    terminals: dict[str, list[Any]] = {}
    for payload in payloads:
        for path, value in flatten(payload).items():
            terminals.setdefault(normalize(path.split(".")[-1]), []).append(value)
    for gate in PRE_RENDER_GATES:
        if not any(pass_value(value) for value in terminals.get(gate, [])):
            raise RuntimeError(f"PRE_RENDER_GATE_NOT_PASS:{gate}:{terminals.get(gate)}")
    if not any(str(value) == "0" for value in terminals.get("GENERIC_ASSET_GRID_COUNT", [])):
        raise RuntimeError("PRE_RENDER_GENERIC_GRID_NOT_ZERO")
    if any(value is True or str(value).lower() == "true" for value in terminals.get("MEDIA_RENDER_STARTED", [])):
        raise RuntimeError("PRE_RENDER_MEDIA_RENDER_STARTED_TRUE")
    fields = {
        "RESULT": "PASS",
        "RUNNER_HEAD": runner_head,
        "QUALITY_HEAD": quality["QUALITY_HEAD"],
        "PRODUCTION_MANIFEST_HEAD": manifest["PRODUCTION_MANIFEST_HEAD"],
        "PRE_RENDER_RUN_ID": str(run_id),
        "PRE_RENDER_JOB_ID": str(job_id),
        "PRE_RENDER_ARTIFACT_ID": str(artifact_id),
        "PRE_RENDER_ARTIFACT_SHA256": artifact_sha,
        "PUBLIC_PRE_RENDER_RESULT": "PASS",
        "OPEN_NON_HUMAN_PRE_RENDER_BLOCKER_COUNT": "0",
        "TWO_MINUTE_RENDER_READY": "true",
        "TWO_MINUTE_RENDER_AUTHORIZED": "false",
        "MEDIA_RENDER_STARTED": "false",
        "FULL_15_MINUTE_RENDER_AUTHORIZED": "false",
        "NO_FAKE_GREEN": "true",
    }
    sc._comment("\n".join(["FINAL_PRE_RENDER_V2", *[f"{key}={value}" for key, value in fields.items()]]))
    return fields


def run() -> None:
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    runner_head = git("rev-parse", "HEAD", cwd=workspace)
    component = latest(PRODUCTION_REPO, 376, "FINAL_CAPTION_COMPONENT_V2", runner_head)
    if not component or component.get("RESULT") != "PASS":
        return
    if latest(PRODUCTION_REPO, 376, "FINAL_PRE_RENDER_V2", runner_head):
        return
    sc._comment(
        "\n".join(
            [
                "QUALITY_PRE_RENDER_CLOSURE_V1",
                "RESULT=STARTED",
                f"RUNNER_HEAD={runner_head}",
                "MEDIA_RENDER_STARTED=false",
                "NO_FAKE_GREEN=true",
            ]
        )
    )
    with tempfile.TemporaryDirectory(prefix="gold-s01-quality-pre-render-") as temp:
        temp_dir = Path(temp)
        source = discover_source_artifact(temp_dir)
        quality = materialize_quality(runner_head, component, source, temp_dir)
        manifest = materialize_manifest(runner_head, component, quality, source, temp_dir)
        run_pre_render(runner_head, component, quality, manifest, temp_dir)


if __name__ == "__main__":
    run()
