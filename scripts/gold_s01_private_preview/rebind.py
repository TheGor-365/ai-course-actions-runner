from __future__ import annotations

from .common import *
from .contracts import validate_profile, validate_request
from .host import validate_host_locks, validate_store_probe_receipt

AUDIO_HANDOFF_SCHEMA = "GoldS01AcceptedTimingHandoff_v1"
VISUAL_HANDOFF_SCHEMA = "GoldS01VisualExactGateHandoff_v1"


def _validate_audio_handoff(value: Mapping[str, Any]) -> dict[str, Any]:
    require_fields(value, {"schema_version", "audio_head", "accepted_timing_path", "accepted_timing_sha256", "final_ru_captions_path", "final_ru_captions_sha256", "unresolved_rows", "timing_authority_accepted", "a3483_sha256", "receipt_hash", "no_fake_green"}, "audio_handoff")
    if value["schema_version"] != AUDIO_HANDOFF_SCHEMA or value["no_fake_green"] is not True:
        raise PreviewError("AUDIO_HANDOFF_SCHEMA_INVALID", "schema/no_fake_green")
    validate_embedded_hash(value)
    require_hex(value["audio_head"], 40, "audio_handoff.audio_head")
    safe_relative(value["accepted_timing_path"], "audio_handoff.accepted_timing_path")
    safe_relative(value["final_ru_captions_path"], "audio_handoff.final_ru_captions_path")
    require_hex(value["accepted_timing_sha256"], 64, "audio_handoff.accepted_timing_sha256")
    require_hex(value["final_ru_captions_sha256"], 64, "audio_handoff.final_ru_captions_sha256")
    if value["unresolved_rows"] != 0 or value["timing_authority_accepted"] is not True:
        raise PreviewError("AUDIO_HANDOFF_NOT_ACCEPTED", str(value["unresolved_rows"]))
    if value["a3483_sha256"] != A3483_SHA256:
        raise PreviewError("A3483_IDENTITY_MISMATCH", "audio_handoff")
    return copy.deepcopy(dict(value))


def _validate_visual_handoff(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema_version", "runner_pr", "runner_head", "private_pr", "private_branch", "private_sha", "result", "production_adapter_git_blob_sha", "no_render_manifest_path", "no_render_manifest_git_blob_sha", "no_render_manifest_sha256", "visual_input_fingerprint", "private_render_request_sha256", "shot_ir_count", "scene_ir_count", "receipt_hash", "no_fake_green"}
    require_fields(value, required, "visual_handoff")
    if value["schema_version"] != VISUAL_HANDOFF_SCHEMA or value["no_fake_green"] is not True:
        raise PreviewError("VISUAL_HANDOFF_SCHEMA_INVALID", "schema/no_fake_green")
    validate_embedded_hash(value)
    if value["result"] != "PASS":
        raise PreviewError("VISUAL_EXACT_GATE_NOT_PASS", str(value["result"]))
    if value["runner_pr"] != 15 or value["private_pr"] != 349:
        raise PreviewError("VISUAL_GATE_PR_MISMATCH", "15/349")
    require_hex(value["runner_head"], 40, "visual_handoff.runner_head")
    require_hex(value["private_sha"], 40, "visual_handoff.private_sha")
    require_hex(value["production_adapter_git_blob_sha"], 40, "visual_handoff.production_adapter_git_blob_sha")
    safe_relative(value["no_render_manifest_path"], "visual_handoff.no_render_manifest_path")
    require_hex(value["no_render_manifest_git_blob_sha"], 40, "visual_handoff.no_render_manifest_git_blob_sha")
    for field in ("no_render_manifest_sha256", "visual_input_fingerprint", "private_render_request_sha256"):
        require_hex(value[field], 64, f"visual_handoff.{field}")
    if value["shot_ir_count"] != 26 or value["scene_ir_count"] != 26:
        raise PreviewError("VISUAL_SCENE_COUNT_MISMATCH", "visual_handoff")
    return copy.deepcopy(dict(value))


def rebind_request(provisional: Mapping[str, Any], audio_handoff: Mapping[str, Any], visual_handoff: Mapping[str, Any], host_receipt: Mapping[str, Any], store_receipt: Mapping[str, Any], profile: Mapping[str, Any], *, runner_sha: str, control_base_sha: str, authorize: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    profile = validate_profile(profile)
    current = validate_request(provisional, profile, allow_provisional=True)
    if current["execution_authorized"] is True or current["validation_status"] != "PROVISIONAL_BLOCKED":
        raise PreviewError("REBIND_SOURCE_NOT_PROVISIONAL", current["validation_status"])
    audio = _validate_audio_handoff(audio_handoff)
    visual = _validate_visual_handoff(visual_handoff)
    validate_host_locks(host_receipt, profile)
    validate_store_probe_receipt(store_receipt, profile)
    require_hex(runner_sha, 40, "rebind.runner_sha")
    require_hex(control_base_sha, 40, "rebind.control_base_sha")

    request = copy.deepcopy(dict(provisional))
    request["request_id"] = "gold-s01-private-preview-exact-v1"
    request["runner"].update(branch="repair/gold-s01-private-preview-runner-v1", sha=runner_sha)
    request["control"].update(sha=control_base_sha, binding_mode=CONTROL_BINDING_MODE)
    request["production"].update(branch=visual["private_branch"], sha=visual["private_sha"])
    request["visual"] = {
        "visual_runtime_head": visual["private_sha"],
        "production_adapter_git_blob_sha": visual["production_adapter_git_blob_sha"],
        "no_render_manifest": {
            "path": visual["no_render_manifest_path"],
            "git_blob_sha": visual["no_render_manifest_git_blob_sha"],
            "sha256": visual["no_render_manifest_sha256"],
            "visual_input_fingerprint": visual["visual_input_fingerprint"],
            "provisional": False,
        },
        "shot_ir_count": visual["shot_ir_count"],
        "scene_ir_count": visual["scene_ir_count"],
        "visual_input_fingerprint": visual["visual_input_fingerprint"],
    }
    request["visual_gate"] = {
        "runner_pr": visual["runner_pr"],
        "runner_head": visual["runner_head"],
        "private_pr": visual["private_pr"],
        "private_sha": visual["private_sha"],
        "result": "PASS",
        "no_render_manifest_sha256": visual["no_render_manifest_sha256"],
        "visual_input_fingerprint": visual["visual_input_fingerprint"],
        "private_render_request_sha256": visual["private_render_request_sha256"],
    }
    request["timing"] = {
        "accepted_contract_path": audio["accepted_timing_path"],
        "accepted_contract_sha256": audio["accepted_timing_sha256"],
        "timing_authority_accepted": True,
        "unresolved_rows": 0,
        "provisional": False,
        "authority_head": audio["audio_head"],
    }
    request["captions"] = {
        "path": audio["final_ru_captions_path"],
        "sha256": audio["final_ru_captions_sha256"],
        "final": True,
        "provisional": False,
        "authority_head": audio["audio_head"],
    }
    request["audio"] = {"artifact_id": "A3483", "sha256": audio["a3483_sha256"]}
    request["host_authority"] = {"status": "READY", "receipt_hash": host_receipt["receipt_hash"], "lock_fingerprint": host_receipt["lock_fingerprint"]}
    request["store_probe_authority"] = {"status": "PASS", "receipt_hash": store_receipt["receipt_hash"], "primary_class": DEFAULT_PRIMARY_CLASS, "replica_class": DEFAULT_REPLICA_CLASS}
    request["execution_authorized"] = bool(authorize)
    if not authorize:
        raise PreviewError("REBIND_AUTHORIZATION_REQUIRED", "--authorize")
    validated = validate_request(request, profile)
    request = {key: value for key, value in validated.items() if key not in {"validation_status", "blockers", "input_fingerprint"}}
    receipt: dict[str, Any] = {
        "schema_version": REBIND_RECEIPT_SCHEMA,
        "request_id": request["request_id"],
        "input_fingerprint": validated["input_fingerprint"],
        "audio_handoff_receipt_hash": audio["receipt_hash"],
        "visual_handoff_receipt_hash": visual["receipt_hash"],
        "host_lock_receipt_hash": host_receipt["receipt_hash"],
        "store_probe_receipt_hash": store_receipt["receipt_hash"],
        "request_sha256": hashlib.sha256(canonical_bytes(request)).hexdigest(),
        "execution_authorized": True,
        "provisional_fields": 0,
        "status": "EXACT_AUTHORIZED",
        "public_artifacts_created": False,
        "private_content_public_exposure": False,
        "no_fake_green": True,
        "created_at": utc_now(),
    }
    receipt["receipt_hash"] = canonical_hash(receipt)
    return request, receipt


def atomic_rebind(output: Path, request: Mapping[str, Any], receipt: Mapping[str, Any], receipt_path: Path) -> str:
    if output.exists():
        existing = load_json(output)
        if canonical_bytes(existing) == canonical_bytes(request):
            if not receipt_path.exists():
                atomic_json(receipt_path, receipt)
            return "UNCHANGED"
        if existing.get("execution_authorized") is True:
            raise PreviewError("EXACT_REQUEST_REBIND_CONFLICT", output.name)
    atomic_json(output, request)
    atomic_json(receipt_path, receipt)
    return "REPLACED_PROVISIONAL"
