from __future__ import annotations

from .common import *
from .contracts import *
from .host import *
from .artifacts import *
from .state import *


def run_fixed_production_adapter(station: str, request_path: Path, profile: Mapping[str, Any], production_dir: Path, private_root: Path, workspace: Path) -> dict[str, Any]:
    adapter = production_dir / profile["fixed_production_adapter_path"]
    station_receipt = workspace / "station_adapter_receipts" / f"{station}.json"
    station_receipt.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(adapter), "--station", station, "--request", str(request_path), "--private-root", str(private_root), "--workspace", str(workspace), "--receipt", str(station_receipt)]
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise PreviewError("PRODUCTION_ADAPTER_STATION_FAILED", f"{station}:{proc.returncode}")
    receipt = load_json(station_receipt)
    if receipt.get("station") != station or receipt.get("status") != "GREEN":
        raise PreviewError("PRODUCTION_ADAPTER_RECEIPT_INVALID", station)
    serialized = json.dumps(receipt)
    if "/home/" in serialized or "file://" in serialized:
        raise PreviewError("RAW_PRIVATE_PATH_IN_ADAPTER_RECEIPT", station)
    return receipt


def execute_private_request(
    request: Mapping[str, Any],
    profile: Mapping[str, Any],
    runner_dir: Path,
    control_dir: Path,
    production_dir: Path,
    private_root: Path,
    receipt_dir: Path,
    *,
    resume_token: str | None = None,
    inject_failure_after_station: str | None = None,
) -> dict[str, Any]:
    require_private_execution_host()
    request = validate_request(request, profile)
    materialized = materialize_and_verify_inputs(request, profile, runner_dir, control_dir, production_dir)
    host = host_probe(profile, private_root, authorize_store_probe=True)
    validate_host_locks(host, profile)
    if host["blockers"]:
        raise PreviewError("HOST_LOCKS_NOT_READY", ",".join(host["blockers"]))
    receipt_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(receipt_dir, 0o700)
    atomic_json(receipt_dir / "sanitized_host_lock_receipt_v1.json", host)
    workspace = private_root / "gold_s01_execution_workspace_v1" / request["input_fingerprint"]
    workspace.mkdir(parents=True, exist_ok=True)
    request_path = control_dir / request["control"]["request_path"]
    state_path = private_root / "gold_s01_execution_state_v1" / f"{request['input_fingerprint']}.json"
    context: dict[str, Any] = {"materialized": materialized, "host": host}

    def load_receipts() -> None:
        if "primary" not in context:
            context["primary"] = load_json(receipt_dir / "primary_registration_receipt_v1.json")
            context["replica"] = load_json(receipt_dir / "replica_receipt_v1.json")
            context["restore"] = load_json(receipt_dir / "restore_receipt_v1.json")

    def station_runner(station: str) -> Mapping[str, Any]:
        if station == "01_PREFLIGHT":
            return {"status": "GREEN", "request_id": request["request_id"], "host_receipt_hash": host["receipt_hash"]}
        if station == "02_INPUT_MATERIALIZATION":
            return {"status": "GREEN", **materialized}
        if station in {"03_NO_RENDER_VALIDATE", "04_REPRESENTATIVE_STILLS", "05_STILL_MACHINE_QC", "06_SHORT_CROSS_SCENE_CLIP", "07_FULL_CLEAN_VISUAL_MASTER", "08_AUDIO_CAPTION_MUX", "09_FFPROBE_AND_SYNC_QC"}:
            return run_fixed_production_adapter(station, request_path, profile, production_dir, private_root, workspace)
        if station == "10_PRIMARY_REGISTRATION":
            outputs, probes, output_manifest = load_private_output_manifest(workspace / "final_outputs_manifest_v1.json", request, profile, private_root)
            primary, replica, restore = register_outputs(outputs, probes, profile, private_root, request)
            context.update(primary=primary, replica=replica, restore=restore, output_manifest=output_manifest)
            atomic_json(receipt_dir / "primary_registration_receipt_v1.json", primary)
            atomic_json(receipt_dir / "replica_receipt_v1.json", replica)
            atomic_json(receipt_dir / "restore_receipt_v1.json", restore)
            return {"status": "GREEN", "primary_receipt_hash": primary["receipt_hash"], "artifact_count": primary["artifact_count"]}
        load_receipts()
        if station == "11_REPLICA_COPY":
            if context["replica"].get("replica_status") != "PASS":
                raise PreviewError("REPLICA_NOT_GREEN", "replica")
            return {"status": "GREEN", "replica_receipt_hash": context["replica"]["receipt_hash"]}
        if station == "12_RESTORE_TO_CLEAN_LOCATION":
            if context["restore"].get("restore_status") != "PASS":
                raise PreviewError("RESTORE_NOT_GREEN", "restore")
            return {"status": "GREEN", "restore_receipt_hash": context["restore"]["receipt_hash"]}
        if station == "13_RESTORE_HASH_VERIFY":
            if context["restore"].get("cleanup_status") != "PASS" or len(context["restore"].get("verified_artifacts", [])) != 2:
                raise PreviewError("RESTORE_VERIFY_NOT_GREEN", "restore")
            return {"status": "GREEN", "verified_artifact_count": 2}
        if station == "14_OWNER_REVIEW_PACKAGE":
            primary = context["primary"]
            manifest = {
                "schema_version": OWNER_MANIFEST_SCHEMA,
                "request_id": request["request_id"],
                "input_fingerprint": request["input_fingerprint"],
                "artifacts": primary["artifacts"],
                "primary_receipt_hash": primary["receipt_hash"],
                "replica_receipt_hash": context["replica"]["receipt_hash"],
                "restore_receipt_hash": context["restore"]["receipt_hash"],
                "machine_qc_status": "GREEN",
                "owner_delivery_pointer_class": DEFAULT_OWNER_CLASS,
                "human_final_preview_accepted": False,
                "allowed_owner_decisions": ["ACCEPT", "REPAIR_REQUIRED", "REJECT"],
                "public_artifacts_created": False,
                "private_content_public_exposure": False,
                "raw_private_paths_in_manifest": False,
                "no_fake_green": True,
            }
            manifest["manifest_hash"] = canonical_hash(manifest)
            context["owner_manifest"] = manifest
            atomic_json(receipt_dir / "owner_delivery_manifest_v1.json", manifest)
            return {"status": "GREEN", "owner_manifest_hash": manifest["manifest_hash"]}
        if station == "15_SANITIZED_WRITEBACK":
            if "owner_manifest" not in context:
                context["owner_manifest"] = load_json(receipt_dir / "owner_delivery_manifest_v1.json")
            return {"status": "GREEN", "writeback_class": "SANITIZED_METADATA_ONLY", "owner_manifest_hash": context["owner_manifest"]["manifest_hash"]}
        raise PreviewError("STATION_UNCLASSIFIED", station)

    station_receipt = run_state_machine(request, profile, state_path, station_runner, resume_token=resume_token, inject_failure_after_station=inject_failure_after_station)
    load_receipts()
    owner_manifest = context.get("owner_manifest") or load_json(receipt_dir / "owner_delivery_manifest_v1.json")
    handoff = {
        "schema_version": "GoldS01PrivatePreviewHandoff_v1",
        "execution_request_sha256": sha256_file(request_path),
        "input_fingerprint": request["input_fingerprint"],
        "visual_master_receipt_sha256": next(item["sha256"] for item in context["primary"]["artifacts"] if item["artifact_type"] == "clean_visual_master"),
        "ru_preview_receipt_sha256": next(item["sha256"] for item in context["primary"]["artifacts"] if item["artifact_type"] == "ru_preview"),
        "primary_registration_receipt_sha256": context["primary"]["receipt_hash"],
        "replica_receipt_sha256": context["replica"]["receipt_hash"],
        "restore_receipt_sha256": context["restore"]["receipt_hash"],
        "station_run_receipt_sha256": station_receipt["receipt_hash"],
        "owner_manifest_hash": owner_manifest["manifest_hash"],
        "owner_delivery_pointer_class": DEFAULT_OWNER_CLASS,
        "human_final_preview_accepted": False,
        "public_artifacts_created": False,
        "private_content_public_exposure": False,
        "no_fake_green": True,
    }
    handoff["receipt_hash"] = canonical_hash(handoff)
    atomic_json(receipt_dir / "sanitized_factory_quality_handoff_v1.json", handoff)
    return handoff
