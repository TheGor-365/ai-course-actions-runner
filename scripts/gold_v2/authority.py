#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .common import (
    MODE_RANK, RunnerError, canonical_json_bytes, parse_utc, require_keys, require_relpath,
    require_sha40, require_sha64, scan_sensitive, sha256_bytes,
)

COMMAND_REPOS = {"source", "shared_source", "production", "runner", "compiler", "runtime"}


def _command(name: str, value: Any) -> None:
    if not isinstance(value, dict):
        raise RunnerError(f"COMMAND_OBJECT_REQUIRED:{name}")
    require_keys(value, ("repo", "argv"), f"COMMAND_{name}")
    if set(value) != {"repo", "argv"}:
        raise RunnerError(f"COMMAND_UNKNOWN_FIELDS:{name}")
    if value["repo"] not in COMMAND_REPOS:
        raise RunnerError(f"COMMAND_REPO_INVALID:{name}")
    argv = value["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
        raise RunnerError(f"COMMAND_ARGV_INVALID:{name}")
    if any(any(secret in item for secret in ("${{", "GITHUB_TOKEN", "GH_TOKEN", "PRIVATE_REPO_PAT")) for item in argv):
        raise RunnerError(f"COMMAND_SECRET_REFERENCE_FORBIDDEN:{name}")


def _binding(binding: Any, context: str, *, media: bool = False) -> None:
    if not isinstance(binding, dict):
        raise RunnerError(f"{context}_OBJECT_REQUIRED")
    keys = ("kind", "repo", "path", "sha256", "git_blob_sha") if media else ("repo", "path", "sha256", "git_blob_sha")
    require_keys(binding, keys, context)
    if set(binding) - {"kind", "repo", "path", "sha256", "git_blob_sha", "result"}:
        raise RunnerError(f"{context}_UNKNOWN_FIELDS")
    allowed = {"production", "runtime"} if media else COMMAND_REPOS
    if binding["repo"] not in allowed:
        raise RunnerError(f"{context}_REPO_INVALID")
    require_relpath(binding["path"], f"{context}_PATH_INVALID")
    require_sha64(binding["sha256"], f"{context}_SHA256_INVALID")
    require_sha40(binding["git_blob_sha"], f"{context}_BLOB_INVALID")


def validate_manifest(manifest: Mapping[str, Any], requested_mode: str, *, now: datetime | None = None) -> dict[str, Any]:
    if requested_mode not in MODE_RANK:
        raise RunnerError("REQUESTED_MODE_INVALID")
    scan_sensitive("authorization_manifest.json", canonical_json_bytes(manifest))
    required = (
        "schema_version", "manifest_id", "runner_role", "production_authority", "oc_document_id",
        "control_repository", "control_head", "control_branch", "control_path", "oc_blob_sha",
        "authorization_payload_sha256", "mode", "source_repository", "source_head",
        "source_package_path", "source_package_sha256", "shared_source_repository", "shared_source_head",
        "production_repository", "production_head", "runner_repository", "runner_head",
        "execution_authorizations", "commands", "bindings", "schema_bindings", "expected_outputs",
        "artifact_class", "acceptance_state", "human_review_gates", "no_fake_green",
    )
    require_keys(manifest, required, "AUTHORIZATION_MANIFEST")
    optional = {
        "expires_at_utc", "single_use_id", "source_required_ancestor", "shared_source_required_ancestor",
        "production_required_ancestor", "runner_required_ancestor", "compiler_required_ancestor",
        "runtime_required_ancestor", "compiler_head", "compiler_artifact_path",
        "compiler_artifact_sha256", "runtime_head", "audio_sha256", "timing_sha256",
        "caption_json_sha256", "caption_vtt_sha256", "accepted_media_bindings",
        "composition_id", "duration_ms", "quality_receipt", "coordinator_receipt",
    }
    unknown = sorted(set(manifest) - set(required) - optional)
    if unknown:
        raise RunnerError(f"AUTHORIZATION_UNKNOWN_FIELDS:{','.join(unknown)}")
    if manifest["schema_version"] != "gold_v2_runner_authorization.v1":
        raise RunnerError("AUTHORIZATION_SCHEMA_VERSION_UNSUPPORTED")
    if not manifest["manifest_id"] or manifest["runner_role"] != "EXECUTION_EVIDENCE_ONLY" or manifest["production_authority"] is not False:
        raise RunnerError("RUNNER_ROLE_BOUNDARY_VIOLATION")
    if manifest["mode"] != requested_mode:
        raise RunnerError("AUTHORIZATION_MODE_MISMATCH")
    if manifest["no_fake_green"] is not True:
        raise RunnerError("NO_FAKE_GREEN_REQUIRED")

    for field in ("control_head", "source_head", "shared_source_head", "production_head", "runner_head"):
        require_sha40(manifest[field], f"{field.upper()}_INVALID")
    require_sha40(manifest["oc_blob_sha"], "OC_BLOB_SHA_INVALID")
    require_sha64(manifest["authorization_payload_sha256"], "AUTHORIZATION_PAYLOAD_SHA256_INVALID")
    require_sha64(manifest["source_package_sha256"], "SOURCE_PACKAGE_SHA256_INVALID")
    require_relpath(manifest["control_path"], "CONTROL_PATH_INVALID")
    require_relpath(manifest["source_package_path"], "SOURCE_PACKAGE_PATH_INVALID")

    payload = dict(manifest)
    for field in ("authorization_payload_sha256", "control_head", "oc_blob_sha"):
        payload.pop(field, None)
    if sha256_bytes(canonical_json_bytes(payload)) != manifest["authorization_payload_sha256"]:
        raise RunnerError("AUTHORIZATION_PAYLOAD_SHA256_MISMATCH")

    expires, single = manifest.get("expires_at_utc"), manifest.get("single_use_id")
    if expires is None and single is None:
        raise RunnerError("AUTHORIZATION_EXPIRY_OR_SINGLE_USE_REQUIRED")
    if expires is not None and parse_utc(expires) <= (now or datetime.now(timezone.utc)).astimezone(timezone.utc):
        raise RunnerError("AUTHORIZATION_EXPIRED")
    if single is not None and (not isinstance(single, str) or not single.strip()):
        raise RunnerError("AUTHORIZATION_SINGLE_USE_ID_INVALID")

    authz = manifest["execution_authorizations"]
    flags = ("validate_only", "compile", "pre_render_evidence", "dom_evidence", "still_evidence", "render")
    if not isinstance(authz, dict) or any(authz.get(flag) not in (True, False) for flag in flags):
        raise RunnerError("EXECUTION_AUTHORIZATION_FLAGS_INVALID")
    needed = ["validate_only"]
    if MODE_RANK[requested_mode] >= 1:
        needed.append("compile")
    if MODE_RANK[requested_mode] >= 2:
        needed += ["pre_render_evidence", "dom_evidence", "still_evidence"]
    if requested_mode == "render":
        needed.append("render")
    denied = [flag for flag in needed if authz[flag] is not True]
    if denied:
        raise RunnerError(f"MODE_NOT_AUTHORIZED:{','.join(denied)}")

    commands = manifest["commands"]
    names = ["source_materialize", "source_validate", "shared_id_validate", "schema_validate", "archive_prereq_validate"]
    if MODE_RANK[requested_mode] >= 1:
        names.append("compiler")
    if MODE_RANK[requested_mode] >= 2:
        names += ["runtime_discovery", "runtime_typecheck", "runtime_tests", "audio_timing_validate", "quality_materialize", "dom_evidence", "still_evidence"]
    if requested_mode == "render":
        names.append("video_render")
    require_keys(commands, names, "COMMANDS")
    for name in names:
        _command(name, commands[name])

    for list_name in ("bindings", "schema_bindings"):
        values = manifest[list_name]
        if not isinstance(values, list) or not values:
            raise RunnerError(f"{list_name.upper()}_NONEMPTY_ARRAY_REQUIRED")
        for index, value in enumerate(values):
            _binding(value, f"{list_name.upper()}_{index}")

    if MODE_RANK[requested_mode] >= 1:
        require_sha40(manifest.get("compiler_head"), "COMPILER_HEAD_INVALID")
        require_sha64(manifest.get("compiler_artifact_sha256"), "COMPILER_ARTIFACT_SHA256_INVALID")
        artifact_path = require_relpath(manifest.get("compiler_artifact_path"), "COMPILER_ARTIFACT_PATH_INVALID")
        files = manifest["expected_outputs"].get("compiler_files")
        if not isinstance(files, list) or not files or len(files) != len(set(files)):
            raise RunnerError("EXPECTED_COMPILER_FILE_SET_INVALID")
        for path in files:
            require_relpath(path, "EXPECTED_COMPILER_FILE_PATH_INVALID")
        if artifact_path not in files:
            raise RunnerError("COMPILER_ARTIFACT_NOT_IN_EXPECTED_FILE_SET")

    if MODE_RANK[requested_mode] >= 2:
        require_sha40(manifest.get("runtime_head"), "RUNTIME_HEAD_INVALID")
        top = {kind: manifest.get(field) for kind, field in (
            ("audio", "audio_sha256"), ("timing", "timing_sha256"),
            ("caption_json", "caption_json_sha256"), ("caption_vtt", "caption_vtt_sha256"),
        )}
        for kind, digest in top.items():
            require_sha64(digest, f"{kind.upper()}_SHA256_INVALID")
        media = manifest.get("accepted_media_bindings")
        if not isinstance(media, list) or len(media) != 4:
            raise RunnerError("ACCEPTED_MEDIA_BINDINGS_INVALID")
        seen: set[str] = set()
        for index, value in enumerate(media):
            _binding(value, f"MEDIA_BINDING_{index}", media=True)
            kind = value["kind"]
            if kind not in top or kind in seen or value["sha256"] != top[kind]:
                raise RunnerError(f"MEDIA_BINDING_KIND_OR_IDENTITY_INVALID:{index}")
            seen.add(kind)
        if seen != set(top):
            raise RunnerError("ACCEPTED_MEDIA_BINDING_KIND_SET_INVALID")
        if not manifest.get("composition_id") or not isinstance(manifest.get("duration_ms"), int) or manifest["duration_ms"] <= 0:
            raise RunnerError("COMPOSITION_OR_DURATION_INVALID")

    if requested_mode == "render":
        for name in ("quality_receipt", "coordinator_receipt"):
            value = manifest.get(name)
            _binding(value, name.upper())
            if value.get("repo") != "production":
                raise RunnerError(f"{name.upper()}_PRODUCTION_REPO_REQUIRED")
            if value.get("result") != "PASS":
                raise RunnerError(f"{name.upper()}_PASS_REQUIRED")

    artifact_class, state = manifest["artifact_class"], manifest["acceptance_state"]
    if artifact_class not in {"EVIDENCE", "PREVIEW", "PRODUCTION"}:
        raise RunnerError("ARTIFACT_CLASS_INVALID")
    if artifact_class == "PREVIEW" and state != "NON_ACCEPTED_RECORDING_CANDIDATE":
        raise RunnerError("PREVIEW_ACCEPTANCE_STATE_INVALID")
    if state == "ACCEPTED" and requested_mode != "render":
        raise RunnerError("ACCEPTED_STATE_REQUIRES_RENDER_MODE")

    gates = manifest["human_review_gates"]
    if not isinstance(gates, list):
        raise RunnerError("HUMAN_REVIEW_GATES_ARRAY_REQUIRED")
    for index, gate in enumerate(gates):
        require_keys(gate, ("gate_id", "frame", "scene_event", "expected", "observed", "reviewer_action"), f"HUMAN_REVIEW_GATE_{index}")
        if gate.get("status", "REVIEW_REQUIRED") == "PASS":
            raise RunnerError(f"AUTOMATIC_AESTHETIC_PASS_FORBIDDEN:{index}")
    if state == "ACCEPTED" and gates:
        raise RunnerError("ACCEPTED_STATE_WITH_UNRESOLVED_HUMAN_GATES")
    return dict(manifest)
