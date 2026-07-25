from __future__ import annotations

from .common import *


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    require_fields(profile, {"schema_version", "profile_id", "scope", "stations", "runtime_lock", "expected_outputs"}, "profile")
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
    return copy.deepcopy(dict(profile))


def validate_request(request: Mapping[str, Any], profile: Mapping[str, Any], *, allow_provisional: bool = False) -> dict[str, Any]:
    profile = validate_profile(profile)
    required = {"schema_version", "request_id", "profile_id", "scope", "runner", "control", "production", "visual", "timing", "captions", "audio", "execution_authorized", "output_profile", "store_policy", "owner_delivery_class", "public_workflow_execution_allowed", "public_artifact_upload_allowed", "media_in_git_allowed", "network_provider_calls_allowed", "arbitrary_commands_allowed", "dynamic_script_path_allowed", "restore_verification_required", "no_fake_green"}
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

    runner = request["runner"]
    control = request["control"]
    production = request["production"]
    for block, name in ((runner, "runner"), (control, "control"), (production, "production")):
        if not isinstance(block, Mapping):
            raise PreviewError("REQUEST_BLOCK_INVALID", name)
        require_fields(block, {"repository", "branch", "sha"}, name)
        require_hex(block["sha"], 40, f"{name}.sha")
    if runner["repository"] != "TheGor-365/ai-course-actions-runner" or production["repository"] != "TheGor-365/ai-course-production-system" or control["repository"] != production["repository"]:
        raise PreviewError("REPOSITORY_AUTHORITY_INVALID", "runner/control/production")
    require_fields(control, {"request_path"}, "control")
    safe_relative(control["request_path"], "control.request_path")

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

    timing = request["timing"]
    require_fields(timing, {"accepted_contract_path", "accepted_contract_sha256", "timing_authority_accepted", "unresolved_rows", "provisional"}, "timing")
    captions = request["captions"]
    require_fields(captions, {"path", "sha256", "final", "provisional"}, "captions")
    audio = request["audio"]
    require_fields(audio, {"artifact_id", "sha256"}, "audio")
    if audio["artifact_id"] != "A3483" or audio["sha256"] != A3483_SHA256:
        raise PreviewError("A3483_IDENTITY_MISMATCH", "audio")

    provisional_reasons: list[str] = []
    if manifest["provisional"] is not False:
        provisional_reasons.append("NO_RENDER_MANIFEST_PROVISIONAL")
    if timing["provisional"] is not False or timing["timing_authority_accepted"] is not True:
        provisional_reasons.append("ACCEPTED_TIMING_MISSING")
    if timing["unresolved_rows"] != 0:
        provisional_reasons.append("TIMING_UNRESOLVED_ROWS")
    if captions["provisional"] is not False or captions["final"] is not True:
        provisional_reasons.append("FINAL_RU_CAPTIONS_MISSING")
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

    expected_outputs = profile["expected_outputs"]
    if request["output_profile"] != expected_outputs:
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
        "accepted_timing_sha256": request["timing"].get("accepted_contract_sha256"),
        "final_ru_captions_sha256": request["captions"].get("sha256"),
        "audio_sha256": request["audio"]["sha256"],
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def require_private_execution_host() -> None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise PreviewError("PUBLIC_WORKFLOW_PRIVATE_EXECUTION_FORBIDDEN", "GitHub Actions")


def materialize_and_verify_inputs(
    request: Mapping[str, Any],
    profile: Mapping[str, Any],
    runner_dir: Path,
    control_dir: Path,
    production_dir: Path,
) -> dict[str, str]:
    require_private_execution_host()
    validate_git_checkout(runner_dir, request["runner"]["sha"])
    validate_git_checkout(control_dir, request["control"]["sha"])
    validate_git_checkout(production_dir, request["production"]["sha"])
    request_file = control_dir / request["control"]["request_path"]
    if not request_file.is_file():
        raise PreviewError("BOUND_FILE_MISSING", request["control"]["request_path"])
    adapter = validate_blob(
        production_dir,
        profile["fixed_production_adapter_path"],
        request["visual"]["production_adapter_git_blob_sha"],
    )
    manifest = validate_blob(
        production_dir,
        request["visual"]["no_render_manifest"]["path"],
        request["visual"]["no_render_manifest"]["git_blob_sha"],
        request["visual"]["no_render_manifest"]["sha256"],
    )
    timing = validate_blob(
        production_dir,
        request["timing"]["accepted_contract_path"],
        git_output(production_dir, "hash-object", str(production_dir / request["timing"]["accepted_contract_path"])),
        request["timing"]["accepted_contract_sha256"],
    )
    captions = validate_blob(
        production_dir,
        request["captions"]["path"],
        git_output(production_dir, "hash-object", str(production_dir / request["captions"]["path"])),
        request["captions"]["sha256"],
    )
    lock = profile["runtime_lock"]
    package_lock = validate_blob(
        production_dir,
        lock["package_lock_path"],
        lock["package_lock_git_blob_sha"],
        lock["package_lock_sha256"],
    )
    if package_lock.stat().st_size != lock["package_lock_size_bytes"]:
        raise PreviewError("PACKAGE_LOCK_SIZE_MISMATCH", lock["package_lock_path"])
    observed_fingerprint = compute_visual_input_fingerprint(request)
    if observed_fingerprint != request["visual"]["visual_input_fingerprint"]:
        raise PreviewError("ASSET_FINGERPRINT_MISMATCH", "request fingerprint")
    return {
        "adapter_sha256": sha256_file(adapter),
        "manifest_sha256": sha256_file(manifest),
        "timing_sha256": sha256_file(timing),
        "captions_sha256": sha256_file(captions),
        "package_lock_sha256": sha256_file(package_lock),
        "visual_input_fingerprint": observed_fingerprint,
    }


def compute_input_fingerprint(request: Mapping[str, Any]) -> str:
    payload = {
        "profile_id": request["profile_id"],
        "scope": request["scope"],
        "runner": request["runner"],
        "control": request["control"],
        "production": request["production"],
        "visual": request["visual"],
        "timing": request["timing"],
        "captions": request["captions"],
        "audio": request["audio"],
        "output_profile": request["output_profile"],
        "store_policy": request["store_policy"],
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
