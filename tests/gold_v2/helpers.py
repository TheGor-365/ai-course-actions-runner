from __future__ import annotations

import hashlib
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.gold_v2.common import canonical_json_bytes, sha256_bytes, sha256_file


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def make_repo(root: Path, name: str, files: dict[str, bytes | str]) -> tuple[Path, str]:
    repo = root / name
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", "--quiet"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
    for relative, value in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=repo, check=True)
    return repo, git(repo, "rev-parse", "HEAD")


def blob(repo: Path, path: str) -> str:
    return git(repo, "rev-parse", f"HEAD:{path}")


def binding(repo_key: str, repo: Path, path: str) -> dict[str, Any]:
    return {"repo": repo_key, "path": path, "sha256": sha256_file(repo / path), "git_blob_sha": blob(repo, path)}


def seal(manifest: dict[str, Any]) -> dict[str, Any]:
    payload = dict(manifest)
    for field in ("authorization_payload_sha256", "control_head", "oc_blob_sha"):
        payload.pop(field, None)
    manifest["authorization_payload_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return manifest


def base_manifest(root: Path, mode: str = "validate-only") -> tuple[dict[str, Any], dict[str, Path]]:
    source, source_head = make_repo(root, "source", {"package.json": '{"package":"gold-v2"}\n', "shared.txt": "source\n"})
    shared, shared_head = make_repo(root, "shared", {"ids.json": '{"id":"shared"}\n'})
    production, production_head = make_repo(root, "production", {
        "schema.json": '{"schema":"v1"}\n',
        "audio.bin": b"audio", "timing.json": "{}\n", "captions.json": "{}\n", "captions.vtt": "WEBVTT\n",
        "quality.json": '{"result":"PASS"}\n', "coordinator.json": '{"result":"PASS"}\n',
    })
    runner, runner_head = make_repo(root, "runner", {"runner.txt": "runner\n"})
    noop = {"repo": "production", "argv": ["python3", "-c", "pass"]}
    commands = {name: dict(noop) for name in (
        "source_materialize", "source_validate", "shared_id_validate", "schema_validate", "archive_prereq_validate",
    )}
    expected_outputs: dict[str, Any] = {}
    if mode in ("compile", "pre-render-evidence", "render"):
        compiler_script = (
            "import pathlib; p=pathlib.Path(r'{output_dir}'); p.mkdir(parents=True,exist_ok=True); "
            "(p/'artifact.bin').write_bytes(b'fixed'); (p/'manifest.json').write_text('ok\\n',encoding='utf-8')"
        )
        commands["compiler"] = {"repo": "compiler", "argv": ["python3", "-c", compiler_script]}
        expected_outputs["compiler_files"] = ["artifact.bin", "manifest.json"]
    if mode in ("pre-render-evidence", "render"):
        commands.update({name: dict(noop) for name in (
            "runtime_discovery", "runtime_typecheck", "runtime_tests", "audio_timing_validate", "quality_materialize",
            "dom_evidence", "still_evidence",
        )})
        expected_outputs["pre_render_files"] = ["evidence.json"]
    if mode == "render":
        commands["video_render"] = dict(noop)
        expected_outputs.update({
            "render_files": ["video.mp4", "render_receipt.json"],
            "render_receipt": "render_receipt.json",
            "render_receipt_schema_version": "fixture.render_receipt.v1",
        })
    package_sha = sha256_file(source / "package.json")
    manifest: dict[str, Any] = {
        "schema_version": "gold_v2_runner_authorization.v1",
        "manifest_id": f"fixture-{mode}",
        "runner_role": "EXECUTION_EVIDENCE_ONLY",
        "production_authority": False,
        "oc_document_id": "FACTORY_OPERATION_CENTER_TEST",
        "control_repository": str(root / "control"),
        "control_head": "0" * 40,
        "control_branch": "main",
        "control_path": "FACTORY_OPERATION_CENTER.md",
        "oc_blob_sha": "0" * 40,
        "authorization_payload_sha256": "0" * 64,
        "mode": mode,
        "source_repository": str(source), "source_head": source_head,
        "source_package_path": "package.json", "source_package_sha256": package_sha,
        "source_package_git_blob_sha": blob(source, "package.json"),
        "shared_source_repository": str(shared), "shared_source_head": shared_head,
        "production_repository": str(production), "production_head": production_head,
        "runner_repository": str(runner), "runner_head": runner_head,
        "execution_authorizations": {
            "validate_only": True,
            "compile": mode in ("compile", "pre-render-evidence", "render"),
            "pre_render_evidence": mode in ("pre-render-evidence", "render"),
            "dom_evidence": mode in ("pre-render-evidence", "render"),
            "still_evidence": mode in ("pre-render-evidence", "render"),
            "render": mode == "render",
        },
        "commands": commands,
        "bindings": [binding("source", source, "shared.txt"), binding("shared_source", shared, "ids.json")],
        "schema_bindings": [binding("production", production, "schema.json")],
        "expected_outputs": expected_outputs,
        "artifact_class": "EVIDENCE",
        "acceptance_state": "UNACCEPTED_EXECUTION_EVIDENCE",
        "human_review_gates": [{
            "gate_id": "aesthetic-1", "frame": 42, "scene_event": "scene-1:event-1",
            "expected": "intentional composition", "observed": "pending", "reviewer_action": "review frame",
        }],
        "expires_at_utc": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "no_fake_green": True,
    }
    if mode in ("compile", "pre-render-evidence", "render"):
        manifest.update({
            "compiler_head": production_head,
            "compiler_artifact_path": "artifact.bin",
            "compiler_artifact_sha256": hashlib.sha256(b"fixed").hexdigest(),
        })
    if mode in ("pre-render-evidence", "render"):
        media = [
            {"kind": "audio", **binding("production", production, "audio.bin")},
            {"kind": "timing", **binding("production", production, "timing.json")},
            {"kind": "caption_json", **binding("production", production, "captions.json")},
            {"kind": "caption_vtt", **binding("production", production, "captions.vtt")},
        ]
        manifest.update({
            "runtime_head": production_head,
            "audio_sha256": media[0]["sha256"], "timing_sha256": media[1]["sha256"],
            "caption_json_sha256": media[2]["sha256"], "caption_vtt_sha256": media[3]["sha256"],
            "accepted_media_bindings": media,
            "composition_id": "GoldV2Diamond15Min", "duration_ms": 899000,
        })
    if mode == "render":
        manifest["human_review_gates"] = []
        manifest.update({
            "artifact_class": "PRODUCTION", "acceptance_state": "ACCEPTED",
            "quality_receipt": {"result": "PASS", **binding("production", production, "quality.json")},
            "coordinator_receipt": {"result": "PASS", **binding("production", production, "coordinator.json")},
        })
    seal(manifest)
    oc_text = (
        "# fixture\n"
        f"DOCUMENT_ID={manifest['oc_document_id']}\n"
        f"RUNNER_AUTHORIZATION_MANIFEST_ID={manifest['manifest_id']}\n"
        f"RUNNER_AUTHORIZED_MODE={mode}\n"
        f"RUNNER_AUTHORIZATION_PAYLOAD_SHA256={manifest['authorization_payload_sha256']}\n"
    )
    control, control_head = make_repo(root, "control", {"FACTORY_OPERATION_CENTER.md": oc_text})
    manifest["control_repository"] = str(control)
    manifest["control_head"] = control_head
    manifest["oc_blob_sha"] = blob(control, "FACTORY_OPERATION_CENTER.md")
    assert seal(manifest)["authorization_payload_sha256"] in oc_text
    return manifest, {"source": source, "shared": shared, "production": production, "runner": runner, "control": control}


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.write_bytes(canonical_json_bytes(manifest))


def rebind_oc(manifest: dict[str, Any], repos: dict[str, Path]) -> None:
    seal(manifest)
    control = repos["control"]
    text = (
        "# fixture\n"
        f"DOCUMENT_ID={manifest['oc_document_id']}\n"
        f"RUNNER_AUTHORIZATION_MANIFEST_ID={manifest['manifest_id']}\n"
        f"RUNNER_AUTHORIZED_MODE={manifest['mode']}\n"
        f"RUNNER_AUTHORIZATION_PAYLOAD_SHA256={manifest['authorization_payload_sha256']}\n"
    )
    (control / manifest["control_path"]).write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", manifest["control_path"]], cwd=control, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "rebind authority"], cwd=control, check=True)
    manifest["control_head"] = git(control, "rev-parse", "HEAD")
    manifest["oc_blob_sha"] = blob(control, manifest["control_path"])
    seal(manifest)


def valid_archive(path: Path, *, secret: bool = False, private_path: bool = False) -> tuple[set[str], dict[str, str]]:
    receipt_name = "receipt.json"
    data_name = "private_media/client.bin" if private_path else "data.txt"
    receipt = b'{"schema_version":"fixture.receipt.v1"}\n'
    data = b"github_pat_forbidden" if secret else b"data\n"
    hashes = {receipt_name: hashlib.sha256(receipt).hexdigest(), data_name: hashlib.sha256(data).hexdigest()}
    sums = "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())).encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(receipt_name, receipt)
        archive.writestr(data_name, data)
        archive.writestr("SHA256SUMS", sums)
    return {receipt_name, data_name, "SHA256SUMS"}, hashes


def mark_zip_encrypted(path: Path) -> None:
    raw = bytearray(path.read_bytes())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        start = 0
        while True:
            index = raw.find(signature, start)
            if index < 0:
                break
            flags = int.from_bytes(raw[index + flag_offset:index + flag_offset + 2], "little") | 1
            raw[index + flag_offset:index + flag_offset + 2] = flags.to_bytes(2, "little")
            start = index + 4
    path.write_bytes(raw)
