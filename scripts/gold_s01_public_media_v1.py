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
from typing import Any, Mapping, Sequence

SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_KEYS = {"shell", "command", "commands", "script", "script_path", "args", "arguments", "provider_payload", "raw_provider_payload"}
ALLOWED_ARTIFACT_SUFFIXES = {".mp4", ".vtt", ".json", ".txt"}
PROFILE_ID = "M1_L01_S01_RU_GOLD_V2_PUBLIC_MEDIA_V1"
PILOT_SECONDS = 60.0
FULL_SECONDS = 900.0


class PublicMediaError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicMediaError("JSON_READ_FAILED", str(path)) from exc
    if not isinstance(value, dict):
        raise PublicMediaError("JSON_OBJECT_REQUIRED", str(path))
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(dict(value)))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_relative(value: str, field: str) -> Path:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise PublicMediaError("UNSAFE_RELATIVE_PATH", field)
    return path


def run(command: Sequence[str], *, cwd: Path | None = None, capture: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()[-2000:]
        raise PublicMediaError("FIXED_COMMAND_FAILED", detail or "exit=" + str(exc.returncode)) from exc


def scan_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_KEYS:
                raise PublicMediaError("DYNAMIC_EXECUTION_FIELD_FORBIDDEN", f"{path}.{key}")
            scan_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_forbidden_keys(child, f"{path}[{index}]")


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "profile_id", "factory_id", "reference_cell", "execution_layer",
        "public_workflow_execution_allowed", "public_artifact_upload_allowed",
        "arbitrary_commands_allowed", "dynamic_script_path_allowed", "media_in_git_allowed",
        "private_repository_archive_artifact_allowed", "secrets_in_artifacts_allowed",
        "raw_provider_payloads_in_artifacts_allowed", "fixed_production_adapter_path",
        "package_lock_path", "artifact_retention_days", "expected_outputs", "writeback_targets",
    }
    missing = sorted(required - set(profile))
    if missing:
        raise PublicMediaError("PROFILE_FIELDS_MISSING", ",".join(missing))
    if profile["profile_id"] != PROFILE_ID:
        raise PublicMediaError("PROFILE_ID_INVALID", str(profile["profile_id"]))
    if profile["execution_layer"] != "public_github_hosted_runner":
        raise PublicMediaError("EXECUTION_LAYER_INVALID", str(profile["execution_layer"]))
    for field in ("public_workflow_execution_allowed", "public_artifact_upload_allowed"):
        if profile[field] is not True:
            raise PublicMediaError("PUBLIC_POLICY_NOT_ENABLED", field)
    for field in (
        "arbitrary_commands_allowed", "dynamic_script_path_allowed", "media_in_git_allowed",
        "private_repository_archive_artifact_allowed", "secrets_in_artifacts_allowed",
        "raw_provider_payloads_in_artifacts_allowed",
    ):
        if profile[field] is not False:
            raise PublicMediaError("SAFETY_POLICY_INVALID", field)
    safe_relative(str(profile["fixed_production_adapter_path"]), "fixed_production_adapter_path")
    safe_relative(str(profile["package_lock_path"]), "package_lock_path")
    retention = profile["artifact_retention_days"]
    if not isinstance(retention, int) or not 1 <= retention <= 30:
        raise PublicMediaError("RETENTION_INVALID", str(retention))
    return dict(profile)


def validate_fixed_inputs(args: argparse.Namespace) -> None:
    if not SAFE_REPO.fullmatch(args.private_repo):
        raise PublicMediaError("PRIVATE_REPO_INVALID", args.private_repo)
    if not SAFE_BRANCH.fullmatch(args.private_branch) or ".." in args.private_branch:
        raise PublicMediaError("PRIVATE_BRANCH_INVALID", args.private_branch)
    if not HEX40.fullmatch(args.private_sha):
        raise PublicMediaError("PRIVATE_SHA_INVALID", args.private_sha)
    if not HEX40.fullmatch(args.request_blob):
        raise PublicMediaError("REQUEST_BLOB_INVALID", args.request_blob)
    if not HEX64.fullmatch(args.request_sha256):
        raise PublicMediaError("REQUEST_SHA256_INVALID", args.request_sha256)
    safe_relative(args.request_path, "request_path")
    if args.render_mode not in {"pilot_60s", "full_15m"}:
        raise PublicMediaError("RENDER_MODE_INVALID", args.render_mode)
    if not SAFE_ID.fullmatch(args.request_id):
        raise PublicMediaError("REQUEST_ID_INVALID", args.request_id)


def git_output(repo: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo).stdout.strip()


def validate_checkout_and_request(args: argparse.Namespace, profile: Mapping[str, Any], private_dir: Path) -> dict[str, Any]:
    validate_fixed_inputs(args)
    head = git_output(private_dir, "rev-parse", "HEAD")
    if head != args.private_sha:
        raise PublicMediaError("EXACT_HEAD_DRIFT", f"{head}!={args.private_sha}")
    status = git_output(private_dir, "status", "--porcelain")
    if status:
        raise PublicMediaError("PRIVATE_CHECKOUT_DIRTY", "detached checkout modified")
    request_rel = safe_relative(args.request_path, "request_path")
    request_file = private_dir / request_rel
    if not request_file.is_file():
        raise PublicMediaError("REQUEST_PATH_MISSING", args.request_path)
    blob = git_output(private_dir, "hash-object", args.request_path)
    if blob != args.request_blob:
        raise PublicMediaError("REQUEST_BLOB_MISMATCH", f"{blob}!={args.request_blob}")
    request_hash = sha256_file(request_file)
    if request_hash != args.request_sha256:
        raise PublicMediaError("REQUEST_SHA256_MISMATCH", f"{request_hash}!={args.request_sha256}")
    request = load_json(request_file)
    scan_forbidden_keys(request)
    if request.get("request_id") != args.request_id:
        raise PublicMediaError("REQUEST_ID_MISMATCH", str(request.get("request_id")))
    if request.get("no_fake_green") is not True:
        raise PublicMediaError("REQUEST_NO_FAKE_GREEN_MISSING", args.request_path)
    accepted_timing = profile["accepted_timing_sha256"]
    captions = profile["final_ru_captions_sha256"]
    if request.get("accepted_timing_sha256") != accepted_timing:
        raise PublicMediaError("ACCEPTED_TIMING_HASH_MISMATCH", str(request.get("accepted_timing_sha256")))
    if request.get("final_ru_captions_sha256") != captions:
        raise PublicMediaError("FINAL_CAPTIONS_HASH_MISMATCH", str(request.get("final_ru_captions_sha256")))
    adapter = private_dir / safe_relative(str(profile["fixed_production_adapter_path"]), "fixed_production_adapter_path")
    package_lock = private_dir / safe_relative(str(profile["package_lock_path"]), "package_lock_path")
    blockers: list[str] = []
    if not adapter.is_file():
        blockers.append("FIXED_PRODUCTION_ADAPTER_ABSENT")
    if not package_lock.is_file():
        blockers.append("REMOTION_PACKAGE_LOCK_ABSENT")
    expected_composition = profile["expected_composition_id"]
    index_path = private_dir / safe_relative(str(profile["remotion_index_path"]), "remotion_index_path")
    if not index_path.is_file() or expected_composition not in index_path.read_text(encoding="utf-8", errors="ignore"):
        blockers.append("FULL_VISUAL_COMPOSITION_NOT_REGISTERED")
    return {
        "request": request,
        "request_file": request_file,
        "adapter": adapter,
        "package_lock": package_lock,
        "blockers": sorted(set(blockers)),
        "input_fingerprint": hashlib.sha256(
            canonical_bytes(
                {
                    "private_repo": args.private_repo,
                    "private_branch": args.private_branch,
                    "private_sha": args.private_sha,
                    "request_path": args.request_path,
                    "request_blob": args.request_blob,
                    "request_sha256": args.request_sha256,
                    "render_mode": args.render_mode,
                    "request_id": args.request_id,
                    "profile_id": profile["profile_id"],
                }
            )
        ).hexdigest(),
    }


def append_github_output(path: str | None, values: Mapping[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


def preflight(args: argparse.Namespace) -> int:
    profile = validate_profile(load_json(Path(args.profile)))
    private_dir = Path(args.private_dir)
    evidence = validate_checkout_and_request(args, profile, private_dir)
    receipt = {
        "schema_version": "gold-s01-public-media-preflight-v1",
        "status": "PASS" if not evidence["blockers"] else "BLOCKED",
        "factory_id": profile["factory_id"],
        "reference_cell": profile["reference_cell"],
        "execution_layer": profile["execution_layer"],
        "public_workflow_execution_allowed": True,
        "public_artifact_upload_allowed": True,
        "private_repo": args.private_repo,
        "private_branch": args.private_branch,
        "private_sha": args.private_sha,
        "request_path": args.request_path,
        "request_blob": args.request_blob,
        "request_sha256": args.request_sha256,
        "request_id": args.request_id,
        "render_mode": args.render_mode,
        "input_fingerprint": evidence["input_fingerprint"],
        "blockers": evidence["blockers"],
        "human_final_preview_accepted": False,
        "no_fake_green": True,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "sanitized_preflight_receipt.json", receipt)
    append_github_output(
        args.github_output,
        {
            "input_fingerprint": evidence["input_fingerprint"],
            "preflight_status": receipt["status"],
            "preflight_blockers": ",".join(evidence["blockers"]),
            "retention_days": profile["artifact_retention_days"],
        },
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 2


def parse_rate(value: str) -> float:
    left, right = value.split("/", 1)
    return float(left) / float(right)


def ffprobe(path: Path) -> dict[str, Any]:
    completed = run(
        [
            "ffprobe", "-v", "error", "-show_streams", "-show_format",
            "-count_frames", "-of", "json", str(path),
        ]
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PublicMediaError("FFPROBE_JSON_INVALID", path.name) from exc
    if not isinstance(value, dict):
        raise PublicMediaError("FFPROBE_JSON_INVALID", path.name)
    return value


def machine_qc(video: Path, mode: str, adapter_qc_path: Path, expected: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    probe = ffprobe(video)
    video_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "video"]
    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if len(video_streams) != 1:
        raise PublicMediaError("VIDEO_STREAM_COUNT_INVALID", str(len(video_streams)))
    stream = video_streams[0]
    duration = float(probe.get("format", {}).get("duration", 0))
    target = PILOT_SECONDS if mode == "pilot_60s" else FULL_SECONDS
    tolerance = float(expected["duration_tolerance_seconds"])
    checks: dict[str, bool] = {
        "duration_pass": abs(duration - target) <= tolerance,
        "codec_pass": stream.get("codec_name") == "h264",
        "resolution_pass": stream.get("width") == 1920 and stream.get("height") == 1080,
        "fps_pass": abs(parse_rate(stream.get("avg_frame_rate", "0/1")) - 30.0) < 0.001,
        "audio_codec_pass": not audio_streams or all(s.get("codec_name") == "aac" for s in audio_streams),
    }
    adapter_qc = load_json(adapter_qc_path)
    required_adapter_checks = [
        "blank_frame_pass",
        "unexpected_frozen_frame_pass",
        "duplicate_frame_pass",
        "caption_collision_pass",
        "internal_id_leakage_pass",
        "technical_surface_readability_pass",
        "audio_caption_identity_pass",
        "scene_mode_coverage_pass",
    ]
    for key in required_adapter_checks:
        checks[key] = adapter_qc.get(key) is True
    qc = {
        "schema_version": "gold-s01-public-media-machine-qc-v1",
        "render_mode": mode,
        "video_filename": video.name,
        "duration_seconds": duration,
        "target_duration_seconds": target,
        "checks": checks,
        "machine_qc_green": all(checks.values()),
        "adapter_qc_sha256": sha256_file(adapter_qc_path),
        "human_final_preview_accepted": False,
        "no_fake_green": True,
    }
    return probe, qc


def enforce_artifact_allowlist(directory: Path) -> None:
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_ARTIFACT_SUFFIXES:
            raise PublicMediaError("ARTIFACT_FILETYPE_FORBIDDEN", path.name)
        text_suffix = path.suffix.lower() in {".json", ".vtt", ".txt"}
        if text_suffix:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)", text):
                raise PublicMediaError("SECRET_IN_ARTIFACT", path.name)
            if re.search(r"/home/[A-Za-z0-9._-]+/", text):
                raise PublicMediaError("RAW_PRIVATE_PATH_IN_ARTIFACT", path.name)


def render(args: argparse.Namespace) -> int:
    profile = validate_profile(load_json(Path(args.profile)))
    private_dir = Path(args.private_dir)
    evidence = validate_checkout_and_request(args, profile, private_dir)
    if evidence["blockers"]:
        raise PublicMediaError("RENDER_PREFLIGHT_BLOCKED", ",".join(evidence["blockers"]))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_receipt_dir = output_dir / "adapter_receipts"
    adapter_receipt_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(evidence["adapter"]),
        "--request", str(evidence["request_file"]),
        "--render-mode", args.render_mode,
        "--output-dir", str(output_dir),
        "--receipt-dir", str(adapter_receipt_dir),
    ]
    run(command, cwd=private_dir, capture=False)
    outputs = profile["expected_outputs"][args.render_mode]
    video = output_dir / outputs["video_filename"]
    adapter_qc = output_dir / outputs["adapter_qc_filename"]
    if not video.is_file():
        raise PublicMediaError("EXPECTED_VIDEO_MISSING", video.name)
    if not adapter_qc.is_file():
        raise PublicMediaError("ADAPTER_QC_MISSING", adapter_qc.name)
    probe, qc = machine_qc(video, args.render_mode, adapter_qc, outputs)
    write_json(output_dir / "ffprobe.json", probe)
    write_json(output_dir / "qc.json", qc)
    if not qc["machine_qc_green"]:
        raise PublicMediaError("MACHINE_QC_FAILED", json.dumps(qc["checks"], sort_keys=True))
    video_hash = sha256_file(video)
    receipt = {
        "schema_version": "gold-s01-public-media-execution-receipt-v1",
        "status": "PASS",
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"),
        "job_name": os.environ.get("GITHUB_JOB", "local"),
        "private_sha": args.private_sha,
        "request_id": args.request_id,
        "render_mode": args.render_mode,
        "input_fingerprint": evidence["input_fingerprint"],
        "mp4_filename": video.name,
        "mp4_sha256": video_hash,
        "size_bytes": video.stat().st_size,
        "ffprobe_hash": sha256_file(output_dir / "ffprobe.json"),
        "qc_hash": sha256_file(output_dir / "qc.json"),
        "machine_qc_green": True,
        "human_final_preview_accepted": False,
        "no_fake_green": True,
    }
    write_json(output_dir / "sanitized_execution_receipt.json", receipt)
    checksum_files = [video, output_dir / "ffprobe.json", output_dir / "qc.json", output_dir / "sanitized_execution_receipt.json"]
    for optional in ("captions.vtt", "captions.json"):
        candidate = output_dir / optional
        if candidate.is_file():
            checksum_files.append(candidate)
    (output_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in sorted(checksum_files, key=lambda p: p.name)),
        encoding="utf-8",
    )
    if adapter_receipt_dir.exists():
        for path in list(adapter_receipt_dir.rglob("*")):
            if path.is_file():
                path.unlink()
        for path in sorted(adapter_receipt_dir.rglob("*"), reverse=True):
            if path.is_dir():
                path.rmdir()
        adapter_receipt_dir.rmdir()
    enforce_artifact_allowlist(output_dir)
    append_github_output(
        args.github_output,
        {
            "input_fingerprint": evidence["input_fingerprint"],
            "mp4_sha256": video_hash,
            "size_bytes": video.stat().st_size,
            "ffprobe_hash": receipt["ffprobe_hash"],
            "qc_hash": receipt["qc_hash"],
            "video_filename": video.name,
        },
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


def verify_download(args: argparse.Namespace) -> int:
    root = Path(args.artifact_dir)
    videos = list(root.rglob("*.mp4"))
    if len(videos) != 1:
        raise PublicMediaError("DOWNLOADED_MP4_COUNT_INVALID", str(len(videos)))
    observed = sha256_file(videos[0])
    if observed != args.expected_sha256:
        raise PublicMediaError("PUBLIC_ARTIFACT_DOWNLOAD_HASH_MISMATCH", f"{observed}!={args.expected_sha256}")
    receipt = {
        "schema_version": "gold-s01-public-artifact-download-proof-v1",
        "artifact_name": args.artifact_name,
        "mp4_sha256": observed,
        "public_artifact_download_hash_verified": True,
        "no_fake_green": True,
    }
    write_json(Path(args.output), receipt)
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
        raise PublicMediaError("GITHUB_API_FAILED", url) from exc


def resolve_job_id(token: str) -> str:
    repo = os.environ["GITHUB_REPOSITORY"]
    run_id = os.environ["GITHUB_RUN_ID"]
    jobs = api_json(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs?per_page=100", token)
    current_name = os.environ.get("GITHUB_JOB", "")
    for job in jobs.get("jobs", []):
        if job.get("name") == current_name or job.get("name", "").lower().replace(" ", "-") == current_name:
            return str(job["id"])
    if jobs.get("jobs"):
        return str(jobs["jobs"][0]["id"])
    return "unavailable"


def writeback(args: argparse.Namespace) -> int:
    token = os.environ.get("PRIVATE_REPO_PAT")
    if not token:
        raise PublicMediaError("PRIVATE_REPO_PAT_MISSING", "writeback")
    profile = validate_profile(load_json(Path(args.profile)))
    job_id = resolve_job_id(token)
    fields = {
        "RUN_ID": os.environ.get("GITHUB_RUN_ID", "unavailable"),
        "JOB_ID": job_id,
        "ARTIFACT_ID": args.artifact_id,
        "ARTIFACT_NAME": args.artifact_name,
        "RETENTION_OR_EXPIRY": f"{profile['artifact_retention_days']}_days",
        "PRIVATE_SHA": args.private_sha,
        "INPUT_FINGERPRINT": args.input_fingerprint,
        "MP4_SHA256": args.mp4_sha256,
        "SIZE_BYTES": args.size_bytes,
        "FFPROBE_HASH": args.ffprobe_hash,
        "QC_HASH": args.qc_hash,
        "RENDER_MODE": args.render_mode,
        "PUBLIC_ARTIFACT_DOWNLOAD_HASH_VERIFIED": args.download_verified,
        "HUMAN_FINAL_PREVIEW_ACCEPTED": "false",
        "NO_FAKE_GREEN": "true",
    }
    body = "## Gold S01 public media execution receipt\n\n```text\n" + "\n".join(f"{k}={v}" for k, v in fields.items()) + "\n```"
    repo = profile["writeback_targets"]["repository"]
    for number in profile["writeback_targets"]["issue_numbers"]:
        api_json(f"https://api.github.com/repos/{repo}/issues/{number}/comments", token, method="POST", body={"body": body})
    print(json.dumps(fields, sort_keys=True))
    return 0


def add_common_inputs(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", required=True)
    parser.add_argument("--private-dir", required=True)
    parser.add_argument("--private-repo", required=True)
    parser.add_argument("--private-branch", required=True)
    parser.add_argument("--private-sha", required=True)
    parser.add_argument("--request-path", required=True)
    parser.add_argument("--request-blob", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--render-mode", choices=("pilot_60s", "full_15m"), required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--github-output")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixed public GitHub-hosted Gold S01 media runner")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate-profile")
    p.add_argument("--profile", required=True)
    p = sub.add_parser("preflight")
    add_common_inputs(p)
    p = sub.add_parser("render")
    add_common_inputs(p)
    p = sub.add_parser("verify-download")
    p.add_argument("--artifact-dir", required=True)
    p.add_argument("--artifact-name", required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("writeback")
    p.add_argument("--profile", required=True)
    p.add_argument("--artifact-id", required=True)
    p.add_argument("--artifact-name", required=True)
    p.add_argument("--private-sha", required=True)
    p.add_argument("--input-fingerprint", required=True)
    p.add_argument("--mp4-sha256", required=True)
    p.add_argument("--size-bytes", required=True)
    p.add_argument("--ffprobe-hash", required=True)
    p.add_argument("--qc-hash", required=True)
    p.add_argument("--render-mode", choices=("pilot_60s", "full_15m"), required=True)
    p.add_argument("--download-verified", choices=("true", "false"), required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-profile":
            validate_profile(load_json(Path(args.profile)))
            print("PUBLIC_RUNNER_MEDIA_EXECUTION_READY=true")
            print("PRIVATE_RUNNER_BLOCKER_REMOVED=true")
            print("NO_FAKE_GREEN=true")
            return 0
        if args.command == "preflight":
            return preflight(args)
        if args.command == "render":
            return render(args)
        if args.command == "verify-download":
            return verify_download(args)
        if args.command == "writeback":
            return writeback(args)
        raise PublicMediaError("COMMAND_INVALID", str(args.command))
    except PublicMediaError as exc:
        print(f"RESULT=FAIL\nFAILURE_CLASS={exc.code}\nDETAIL={exc.detail}\nNO_FAKE_GREEN=true", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
