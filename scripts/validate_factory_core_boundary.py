#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_STATUS = {"SUCCEEDED", "PARTIAL", "FAILED_RETRYABLE", "FAILED_TERMINAL"}
ALLOWED_TYPES = {"representative_still", "contact_sheet", "cross_scene_clip", "visual_master", "RU_preview"}
REQUIRED_SUCCESS_TYPES = {"visual_master", "RU_preview"}
REQUIRED_RECEIPT = {"schema_version","interface_version","render_request_id","request_id","idempotency_key","evidence_class","real_output_claim","media_executed","status","executor_id","executor_version","started_at","completed_at","artifacts","partial_output_count","quarantine_manifest","failure_class","retryable","receipt_hash"}
REQUIRED_ARTIFACT = {"schema_version","artifact_id","request_id","station_id","artifact_type","sha256","size_bytes","storage_class","private_pointer_or_repository_path","created_at","producer_version","restore_status"}

class ValidationError(ValueError): pass

def load(path: str | Path) -> dict:
    value=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ValidationError("root_not_object")
    return value

def canonical_hash(value: dict) -> str:
    data=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()

def validate_receipt(receipt: dict) -> None:
    missing=REQUIRED_RECEIPT-set(receipt)
    if missing: raise ValidationError("receipt_missing:"+",".join(sorted(missing)))
    if receipt["schema_version"]!="PrivateExecutorReceipt_v1" or receipt["interface_version"]!="launch-core-v1": raise ValidationError("receipt_contract_version")
    if receipt["status"] not in ALLOWED_STATUS: raise ValidationError("receipt_status")
    if not HEX64.fullmatch(str(receipt["idempotency_key"])): raise ValidationError("idempotency_key")
    if not HEX64.fullmatch(str(receipt["receipt_hash"])): raise ValidationError("receipt_hash_format")
    expected=canonical_hash({k:v for k,v in receipt.items() if k!="receipt_hash"})
    if receipt["receipt_hash"]!=expected: raise ValidationError("receipt_hash_mismatch")
    fixture=receipt["evidence_class"]=="COMPATIBLE_FIXTURE"
    real=receipt["evidence_class"]=="REAL_STATION_OUTPUT"
    if not (fixture or real): raise ValidationError("evidence_class")
    if fixture and (receipt["real_output_claim"] is not False or receipt["media_executed"] is not False): raise ValidationError("fixture_truth_boundary")
    if real and receipt["real_output_claim"] is not True: raise ValidationError("real_output_claim")
    if real and receipt["status"]=="SUCCEEDED" and receipt["media_executed"] is not True: raise ValidationError("real_media_proof")
    artifacts=receipt["artifacts"]
    if not isinstance(artifacts,list): raise ValidationError("artifacts_not_array")
    types=[]
    for artifact in artifacts:
        if not isinstance(artifact,dict): raise ValidationError("artifact_not_object")
        missing=REQUIRED_ARTIFACT-set(artifact)
        if missing: raise ValidationError("artifact_missing:"+",".join(sorted(missing)))
        if artifact["schema_version"]!="ArtifactRegistryRecord_v2_minimal" or artifact["station_id"]!="private_render": raise ValidationError("artifact_contract")
        if artifact["request_id"]!=receipt["request_id"]: raise ValidationError("artifact_request_id")
        if artifact["artifact_type"] not in ALLOWED_TYPES or artifact["artifact_type"] in types: raise ValidationError("artifact_type")
        if not HEX64.fullmatch(str(artifact["sha256"])) or not isinstance(artifact["size_bytes"],int) or artifact["size_bytes"]<1: raise ValidationError("artifact_identity")
        pointer=artifact["private_pointer_or_repository_path"]
        if not isinstance(pointer,str) or not pointer.startswith("artifact://") or pointer.startswith("/") or "/home/" in pointer: raise ValidationError("artifact_pointer")
        if fixture and artifact["storage_class"]!="fixture_metadata": raise ValidationError("fixture_storage_class")
        if real and artifact["storage_class"]!="private_external": raise ValidationError("real_storage_class")
        types.append(artifact["artifact_type"])
    status=receipt["status"]
    if status=="SUCCEEDED":
        if not REQUIRED_SUCCESS_TYPES.issubset(types): raise ValidationError("success_artifacts")
        if receipt["partial_output_count"]!=0 or receipt["quarantine_manifest"] is not None or receipt["failure_class"] is not None or receipt["retryable"] is not False: raise ValidationError("success_semantics")
    elif status=="PARTIAL":
        if receipt["partial_output_count"]!=len(artifacts) or not artifacts or not isinstance(receipt["quarantine_manifest"],dict) or not receipt["quarantine_manifest"].get("pointer") or receipt["failure_class"]!="PARTIAL_PRIVATE_OUTPUT" or receipt["retryable"] is not True: raise ValidationError("partial_semantics")
    else:
        if artifacts or receipt["partial_output_count"]!=0 or not receipt["failure_class"]: raise ValidationError("failure_semantics")
        if (status=="FAILED_RETRYABLE") != (receipt["retryable"] is True): raise ValidationError("retryable_semantics")

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--receipt",required=True); args=p.parse_args()
    try: validate_receipt(load(args.receipt))
    except (OSError,json.JSONDecodeError,ValidationError) as exc:
        print("FACTORY_CORE_EXECUTOR_RECEIPT_VALID=false\nFAILURE_CLASS=INVALID_EXECUTOR_RECEIPT\nERROR_CODE="+str(exc).split(":",1)[0]+"\nNO_FAKE_GREEN=true"); return 1
    print("FACTORY_CORE_EXECUTOR_RECEIPT_VALID=true\nINTERFACE_VERSION=launch-core-v1\nPUBLIC_MEDIA_ARTIFACTS_CREATED=false\nPRIVATE_CONTENT_PUBLIC_EXPOSURE=false\nNO_FAKE_GREEN=true"); return 0

if __name__=="__main__": raise SystemExit(main())
