from __future__ import annotations

from .common import *


def _is_zero(value: Any, length: int) -> bool:
    return isinstance(value, str) and value == "0" * length


def _optional_hex(value: Any, length: int, field: str, allow_provisional: bool) -> str | None:
    # Missing exact identities are classified by the final-input gate below.
    # Malformed non-empty identities remain immediate contract errors.
    if value is None:
        return None
    return require_hex(value, length, field)


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    require_fields(profile, {"schema_version", "profile_id", "scope", "stations", "runtime_lock", "host_lock_policy", "expected_outputs"}, "profile")
    if profile["profile_id"] != PROFILE_ID:
        raise PreviewError("PROFILE_ID_INVALID", str(profile.get("profile_id")))
    for field in ("arbitrary_commands_allowed", "dynamic_script_path_allowed", "network_provider_calls_default", "public_workflow_execution_allowed", "public_artifact_upload_allowed", "media_in_git_allowed"):
        if profile.get(field) is not False:
            raise PreviewError("PROFILE_POLICY_INVALID", field)
    safe_relative(profile.get("fixed_production_adapter_path"), "fixed_production_adapter_path")
    if not isinstance(profile.get("minimum_free_bytes"), int) or profile["minimum_free_bytes"] < 1:
        raise PreviewError("PROFILE_FREE_SPACE_INVALID", "minimum_free_bytes")
    if not isinstance(profile.get("max_station_retries"), int) or not 1 <= profile["max_station_retries"] <= 5:
        raise PreviewError("PROFILE_RETRY_INVALID", "max_station_retries")
    stations = profile.get("stations")
    if not isinstance(stations, list) or len(stations) != 15 or len(stations) != len(set(stations)):
        raise PreviewError("PROFILE_STATIONS_INVALID", "stations")
    lock = profile["runtime_lock"]
    require_fields(lock, {"package_manager", "install_command", "package_lock_path", "package_lock_git_blob_sha", "package_lock_sha256", "package_lock_size_bytes", "resolved_versions", "ffmpeg_version", "ffprobe_version"}, "runtime_lock")
    if lock["package_manager"] != "npm" or lock["install_command"] != ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]:
        raise PreviewError("INSTALL_PLAN_NOT_FIXED", "npm")
    safe_relative(lock["package_lock_path"], "package_lock_path")
    require_hex(lock["package_lock_git_blob_sha"], 40, "package_lock_git_blob_sha")
    require_hex(lock["package_lock_sha256"], 64, "package_lock_sha256")
    policy = profile["host_lock_policy"]
    require_fields(policy, {"required_commands", "browser_candidates", "required_font_aliases", "store_probe_bytes"}, "host_lock_policy")
    if policy["required_commands"] != ["python3", "node", "npm", "ffmpeg", "ffprobe"]:
        raise PreviewError("HOST_COMMAND_SET_INVALID", "required_commands")
    if not isinstance(policy["browser_candidates"], list) or not policy["browser_candidates"]:
        raise PreviewError("HOST_BROWSER_SET_INVALID", "browser_candidates")
    if not isinstance(policy["required_font_aliases"], list) or set(policy["required_font_aliases"]) != {"sans-serif", "monospace"}:
        raise PreviewError("HOST_FONT_SET_INVALID", "required_font_aliases")
    if not isinstance(policy["store_probe_bytes"], int) or not 1024 <= policy["store_probe_bytes"] <= 1048576:
        raise PreviewError("STORE_PROBE_SIZE_INVALID", "store_probe_bytes")
    return copy.deepcopy(dict(profile))


def validate_request(request: Mapping[str, Any], profile: Mapping[str, Any], *, allow_provisional: bool = False) -> dict[str, Any]:
    profile = validate_profile(profile)
    required = {"schema_version", "request_id", "profile_id", "scope", "runner", "control", "production", "visual", "visual_gate", "timing", "captions", "audio", "host_authority", "store_probe_authority", "execution_authorized", "output_profile", "store_policy", "owner_delivery_class", "public_workflow_execution_allowed", "public_artifact_upload_allowed", "media_in_git_allowed", "network_provider_calls_allowed", "arbitrary_commands_allowed", "dynamic_script_path_allowed", "restore_verification_required", "no_fake_green"}
    require_fields(request, required, "request")
    scan_forbidden_keys(request)
    if request["schema_version"] != REQUEST_SCHEMA or request["profile_id"] != profile["profile_id"] or request["scope"] != profile["scope"]:
        raise PreviewError("REQUEST_PROFILE_MISMATCH", "schema/profile/scope")
    if not isinstance(request["request_id"], str) or not SAFE_ID.fullmatch(request["request_id"]):
        raise PreviewError("REQUEST_ID_UNSAFE", "request_id")
    for field in ("public_workflow_execution_allowed", "public_artifact_upload_allowed", "media_in_git_allowed", "network_provider_calls_allowed", "arbitrary_commands_allowed", "dynamic_script_path_allowed"):
        if request[field] is not False:
            raise PreviewError("REQUEST_POLICY_INVALID", field)
    if request["restore_verification_required"] is not True or request["no_fake_green"] is not True:
        raise PreviewError("REQUEST_TRUTH_BOUNDARY_INVALID", "restore/no_fake_green")

    runner, control, production = request["runner"], request["control"], request["production"]
    for block, name in ((runner, "runner"), (control, "control"), (production, "production")):
        if not isinstance(block, Mapping):
            raise PreviewError("REQUEST_BLOCK_INVALID", name)
        require_fields(block, {"repository", "branch", "sha"}, name)
        require_hex(block["sha"], 40, f"{name}.sha")
    if runner["repository"] != "TheGor-365/ai-course-actions-runner" or production["repository"] != "TheGor-365/ai-course-production-system" or control["repository"] != production["repository"]:
        raise PreviewError("REPOSITORY_AUTHORITY_INVALID", "runner/control/production")
    require_fields(control, {"request_path", "binding_mode"}, "control")
    safe_relative(control["request_path"], "control.request_path")
    if control["binding_mode"] != CONTROL_BINDING_MODE:
        raise PreviewError("CONTROL_BINDING_MODE_INVALID", str(control.get("binding_mode")))

    visual = request["visual"]
    require_fields(visual, {"visual_runtime_head", "production_adapter_git_blob_sha", "no_render_manifest", "shot_ir_count", "scene_ir_count", "visual_input_fingerprint"}, "visual")
    if visual["visual_runtime_head"] != production["sha"]:
        raise PreviewError("VISUAL_HEAD_MISMATCH", "visual_runtime_head")
    require_hex(visual["production_adapter_git_blob_sha"], 40, "visual.production_adapter_git_blob_sha")
    require_hex(visual["visual_input_fingerprint"], 64, "visual.visual_input_fingerprint")
    if visual["shot_ir_count"] != 26 or visual["scene_ir_count"] != 26:
        raise PreviewError("VISUAL_SCENE_COUNT_MISMATCH", "26/26 required")
    manifest = visual["no_render_manifest"]
    require_fields(manifest, {"path", "git_blob_sha", "sha256", "visual_input_fingerprint", "provisional"}, "visual.no_render_manifest")
    safe_relative(manifest["path"], "visual.no_render_manifest.path")
    require_hex(manifest["git_blob_sha"], 40, "visual.no_render_manifest.git_blob_sha")
    require_hex(manifest["sha256"], 64, "visual.no_render_manifest.sha256")
    require_hex(manifest["visual_input_fingerprint"], 64, "visual.no_render_manifest.visual_input_fingerprint")
    if manifest["visual_input_fingerprint"] != visual["visual_input_fingerprint"]:
        raise PreviewError("ASSET_FINGERPRINT_MISMATCH", "no-render manifest")

    visual_gate = request["visual_gate"]
    require_fields(visual_gate, {"runner_pr", "runner_head", "private_pr", "private_sha", "result", "no_render_manifest_sha256", "visual_input_fingerprint", "private_render_request_sha256"}, "visual_gate")
    _optional_hex(visual_gate.get("runner_head"), 40, "visual_gate.runner_head", allow_provisional)
    _optional_hex(visual_gate.get("private_sha"), 40, "visual_gate.private_sha", allow_provisional)
    _optional_hex(visual_gate.get("no_render_manifest_sha256"), 64, "visual_gate.no_render_manifest_sha256", allow_provisional)
    _optional_hex(visual_gate.get("visual_input_fingerprint"), 64, "visual_gate.visual_input_fingerprint", allow_provisional)
    _optional_hex(visual_gate.get("private_render_request_sha256"), 64, "visual_gate.private_render_request_sha256", allow_provisional)
    if visual_gate.get("private_sha") not in (None, production["sha"]):
        raise PreviewError("VISUAL_GATE_HEAD_MISMATCH", str(visual_gate.get("private_sha")))
    if visual_gate.get("no_render_manifest_sha256") not in (None, manifest["sha256"]):
        raise PreviewError("VISUAL_GATE_MANIFEST_MISMATCH", str(visual_gate.get("no_render_manifest_sha256")))
    if visual_gate.get("visual_input_fingerprint") not in (None, visual["visual_input_fingerprint"]):
        raise PreviewError("VISUAL_GATE_FINGERPRINT_MISMATCH", str(visual_gate.get("visual_input_fingerprint")))

    timing, captions, audio = request["timing"], request["captions"], request["audio"]
    require_fields(timing, {"accepted_contract_path", "accepted_contract_sha256", "timing_authority_accepted", "unresolved_rows", "provisional", "authority_head"}, "timing")
    require_fields(captions, {"path", "sha256", "final", "provisional", "authority_head"}, "captions")
    require_fields(audio, {"artifact_id", "sha256"}, "audio")
    if audio["artifact_id"] != "A3483" or audio["sha256"] != A3483_SHA256:
        raise PreviewError("A3483_IDENTITY_MISMATCH", "audio")
    for head, field in ((timing.get("authority_head"), "timing.authority_head"), (captions.get("authority_head"), "captions.authority_head")):
        _optional_hex(head, 40, field, allow_provisional)

    host_authority, store_authority = request["host_authority"], request["store_probe_authority"]
    require_fields(host_authority, {"status", "receipt_hash", "lock_fingerprint"}, "host_authority")
    require_fields(store_authority, {"status", "receipt_hash", "primary_class", "replica_class"}, "store_probe_authority")
    _optional_hex(host_authority.get("receipt_hash"), 64, "host_authority.receipt_hash", allow_provisional)
    _optional_hex(host_authority.get("lock_fingerprint"), 64, "host_authority.lock_fingerprint", allow_provisional)
    _optional_hex(store_authority.get("receipt_hash"), 64, "store_probe_authority.receipt_hash", allow_provisional)
    if store_authority.get("primary_class") != DEFAULT_PRIMARY_CLASS or store_authority.get("replica_class") != DEFAULT_REPLICA_CLASS:
        raise PreviewError("STORE_AUTHORITY_CLASS_MISMATCH", "primary/replica")

    provisional_reasons: list[str] = []
    if manifest["provisional"] is not False:
        provisional_reasons.append("NO_RENDER_MANIFEST_PROVISIONAL")
    visual_ids = ("runner_head", "private_sha", "no_render_manifest_sha256", "visual_input_fingerprint", "private_render_request_sha256")
    if visual_gate.get("result") != "PASS" or any(visual_gate.get(field) is None or _is_zero(visual_gate.get(field), 40 if field in {"runner_head", "private_sha"} else 64) for field in visual_ids):
        provisional_reasons.append("VISUAL_EXACT_GATE_NOT_PASS")
    if timing["provisional"] is not False or timing["timing_authority_accepted"] is not True:
        provisional_reasons.append("ACCEPTED_TIMING_MISSING")
    if timing["unresolved_rows"] != 0:
        provisional_reasons.append("TIMING_UNRESOLVED_ROWS")
    if captions["provisional"] is not False or captions["final"] is not True:
        provisional_reasons.append("FINAL_RU_CAPTIONS_MISSING")
    if host_authority.get("status") != "READY" or host_authority.get("receipt_hash") is None or host_authority.get("lock_fingerprint") is None:
        provisional_reasons.append("HOST_LOCK_RECEIPT_MISSING")
    if store_authority.get("status") != "PASS" or store_authority.get("receipt_hash") is None:
        provisional_reasons.append("STORE_PROBE_RECEIPT_MISSING")
    if request["execution_authorized"] is not True:
        provisional_reasons.append("EXECUTION_NOT_AUTHORIZED")
    if provisional_reasons and not allow_provisional:
        raise PreviewError("FINAL_RENDER_INPUTS_NOT_ACCEPTED", ",".join(sorted(set(provisional_reasons))))

    for value, field in ((timing["accepted_contract_path"], "timing.accepted_contract_path"), (captions["path"], "captions.path")):
        if value is None and allow_provisional:
            continue
        safe_relative(value, field)
    for value, field in ((timing["accepted_contract_sha256"], "timing.accepted_contract_sha256"), (captions["sha256"], "captions.sha256")):
        if value is None and allow_provisional:
            continue
        require_hex(value, 64, field)
    if allow_provisional and request["execution_authorized"] is True and provisional_reasons:
        raise PreviewError("PROVISIONAL_REQUEST_MUST_NOT_AUTHORIZE", ",".join(provisional_reasons))

    if request["output_profile"] != profile["expected_outputs"]:
        raise PreviewError("OUTPUT_PROFILE_MISMATCH", "fixed output profile")
    store = request["store_policy"]
    require_fields(store, {"primary_class", "replica_class", "minimum_free_bytes", "content_addressed", "overwrite_allowed"}, "store_policy")
    if store["primary_class"] != DEFAULT_PRIMARY_CLASS or store["replica_class"] != DEFAULT_REPLICA_CLASS or store["minimum_free_bytes"] != profile["minimum_free_bytes"] or store["content_addressed"] is not True or store["overwrite_allowed"] is not False:
        raise PreviewError("STORE_POLICY_INVALID", "primary/replica")
    if request["owner_delivery_class"] != DEFAULT_OWNER_CLASS:
        raise PreviewError("OWNER_DELIVERY_CLASS_INVALID", str(request["owner_delivery_class"]))

    result = copy.deepcopy(dict(request))
    result["validation_status"] = "PROVISIONAL_BLOCKED" if provisional_reasons else "ACCEPTED_INPUTS_READY"
    result["blockers"] = sorted(set(provisional_reasons))
    result["input_fingerprint"] = compute_input_fingerprint(result)
    return result


def compute_visual_input_fingerprint(request: Mapping[str, Any]) -> str:
    visual = request["visual"]
    payload = {
        "production_sha": request["production"]["sha"],
        "visual_runtime_head": visual["visual_runtime_head"],
        "production_adapter_git_blob_sha": visual["production_adapter_git_blob_sha"],
        "no_render_manifest_git_blob_sha": visual["no_render_manifest"]["git_blob_sha"],
        "no_render_manifest_sha256": visual["no_render_manifest"]["sha256"],
        "shot_ir_count": visual["shot_ir_count"],
        "scene_ir_count": visual["scene_ir_count"],
        "source_visual_input_fingerprint": visual["visual_input_fingerprint"],
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def require_private_execution_host() -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise PreviewError("PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN", "GitHub Actions")


def materialize_and_verify_inputs(request: Mapping[str, Any], profile: Mapping[str, Any], runner_dir: Path, control_dir: Path, production_dir: Path, audio_authority_dir: Path, *, control_head_sha: str, request_blob_sha: str) -> dict[str, str]:
    require_private_execution_host()
    validate_git_checkout(runner_dir, request["runner"]["sha"])
    validate_git_checkout(control_dir, control_head_sha)
    validate_ancestor(control_dir, request["control"]["sha"], control_head_sha)
    validate_git_checkout(production_dir, request["production"]["sha"])
    request_file = control_dir / request["control"]["request_path"]
    if not request_file.is_file():
        raise PreviewError("BOUND_FILE_MISSING", request["control"]["request_path"])
    require_hex(request_blob_sha, 40, "external.request_blob_sha")
    if git_output(control_dir, "hash-object", str(request_file)) != request_blob_sha:
        raise PreviewError("REQUEST_BLOB_BINDING_MISMATCH", request["control"]["request_path"])
    adapter = validate_blob(production_dir, profile["fixed_production_adapter_path"], request["visual"]["production_adapter_git_blob_sha"])
    manifest = validate_blob(production_dir, request["visual"]["no_render_manifest"]["path"], request["visual"]["no_render_manifest"]["git_blob_sha"], request["visual"]["no_render_manifest"]["sha256"])
    timing_path = audio_authority_dir / request["timing"]["accepted_contract_path"]
    captions_path = audio_authority_dir / request["captions"]["path"]
    for path, expected, field in ((timing_path, request["timing"]["accepted_contract_sha256"], "timing"), (captions_path, request["captions"]["sha256"], "captions")):
        if not path.is_file() or sha256_file(path) != expected:
            raise PreviewError("AUDIO_AUTHORITY_HASH_MISMATCH", field)
    lock = profile["runtime_lock"]
    package_lock = validate_blob(production_dir, lock["package_lock_path"], lock["package_lock_git_blob_sha"], lock["package_lock_sha256"])
    if package_lock.stat().st_size != lock["package_lock_size_bytes"]:
        raise PreviewError("PACKAGE_LOCK_SIZE_MISMATCH", lock["package_lock_path"])
    return {
        "adapter_sha256": sha256_file(adapter),
        "manifest_sha256": sha256_file(manifest),
        "timing_sha256": sha256_file(timing_path),
        "captions_sha256": sha256_file(captions_path),
        "package_lock_sha256": sha256_file(package_lock),
        "visual_input_fingerprint": request["visual"]["visual_input_fingerprint"],
        "runner_visual_binding_fingerprint": compute_visual_input_fingerprint(request),
        "request_blob_sha": request_blob_sha,
        "control_head_sha": control_head_sha,
    }


def compute_input_fingerprint(request: Mapping[str, Any]) -> str:
    payload = {key: request[key] for key in ("profile_id", "scope", "runner", "control", "production", "visual", "visual_gate", "timing", "captions", "audio", "host_authority", "store_probe_authority", "output_profile", "store_policy")}
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
