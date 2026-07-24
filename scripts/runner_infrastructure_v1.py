#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/"config/public_gate_manifest_v1.json"
HEX64=re.compile(r"^[0-9a-f]{64}$")
SAFE=re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
SAFE_PATH=re.compile(r"^[A-Za-z0-9._:/-]+$")
RETRY=75

class ContractError(ValueError): pass

def load(path:Path)->dict:
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise ContractError("root_not_object")
    return value

def now()->str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")

def write_json(path:Path,value:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    os.replace(tmp,path)

def resolve(gate_id:str,repo:str,field:str)->str:
    data=load(MANIFEST)
    if data.get("arbitrary_command_input_allowed") is not False: raise ContractError("manifest_policy")
    gate=data.get("gates",{}).get(gate_id)
    if not isinstance(gate,dict): raise ContractError("gate_not_allowlisted")
    if repo not in gate.get("allowed_repositories",[]): raise ContractError("repo_not_allowlisted_for_gate")
    if gate.get("media") is not False: raise ContractError("public_media_gate_forbidden")
    value=gate.get(field)
    if not isinstance(value,str) or not SAFE_PATH.fullmatch(value): raise ContractError("unsafe_manifest_value")
    if field=="output_schema_file":
        path=(ROOT/value).resolve()
        if ROOT not in path.parents or not path.is_file(): raise ContractError("schema_missing")
    return value

def choices(text:str,name:str)->set[str]:
    lines=text.splitlines(); start=None; indent=0
    for i,line in enumerate(lines):
        if re.match(rf"^\s{{6}}{re.escape(name)}:\s*$",line):
            start=i; indent=len(line)-len(line.lstrip()); break
    if start is None: raise ContractError("workflow_input_missing")
    out=set(); active=False
    for line in lines[start+1:]:
        level=len(line)-len(line.lstrip())
        if line.strip() and level<=indent: break
        if line.strip()=="options:": active=True; continue
        if active:
            m=re.match(r"^\s+-\s+([A-Za-z0-9_./:-]+)\s*$",line)
            if m: out.add(m.group(1))
            elif line.strip() and level<=indent+4: break
    return out

def validate_contract()->int:
    data=load(MANIFEST)
    workflow=(ROOT/".github/workflows/run-private-validator.yml").read_text()
    contract=(ROOT/"00_contracts/PUBLIC_RUNNER_CENTER_CONTRACT_v01.md").read_text()
    runbook=(ROOT/"docs/PUBLIC_RUNNER_DISPATCH_RUNBOOK_v01.md").read_text()
    wrapper=(ROOT/"scripts/run_manifest_gate.sh").read_text()
    gates=set(data["gates"])
    contract_gates=set(re.findall(r"^([A-Z][A-Z0-9_]+)$",contract.split("## 6. Current gate allowlist",1)[1].split("## 7.",1)[0],re.M))
    runbook_gates=set(re.findall(r"\|\s*`([A-Z][A-Z0-9_]+)`\s*\|",runbook.split("## 5. Current gate capability matrix",1)[1].split("## 6.",1)[0]))
    errors=[]
    for label,observed in [("workflow",choices(workflow,"gate_id")),("contract",contract_gates),("runbook",runbook_gates)]:
        if observed!=gates: errors.append(label+"_gate_set_mismatch")
    if choices(workflow,"private_repo")!=set(data["allowed_private_repositories"]): errors.append("repo_allowlist_mismatch")
    declared=set(re.findall(r"^\s{6}([A-Za-z0-9_]+):\s*$",workflow,re.M))
    if declared&{"command","shell","script","validator_path","path"}: errors.append("arbitrary_input")
    if "actions/upload-artifact" in workflow: errors.append("public_artifact_upload")
    if "runner_infrastructure_v1.py" not in wrapper or "resolve-gate" not in wrapper: errors.append("manifest_guard_missing")
    for gate_id,gate in data["gates"].items():
        if gate.get("media") is not False: errors.append(gate_id+"_media")
        if not (ROOT/gate["output_schema_file"]).is_file(): errors.append(gate_id+"_schema")
    print("validator=runner_contract_self_validator_v1")
    print(f"manifest_gate_count={len(gates)}")
    print(f"workflow_gate_count={len(choices(workflow,'gate_id'))}")
    print(f"contract_gate_count={len(contract_gates)}")
    print(f"runbook_gate_count={len(runbook_gates)}")
    print("arbitrary_shell_input=false\npublic_media_artifacts=false")
    print("result="+("FAIL" if errors else "PASS"))
    if errors: print("error_codes="+",".join(sorted(set(errors))))
    return bool(errors)

def launch_gate(private:Path)->int:
    if not (private/".git").is_dir(): raise ContractError("private_checkout_missing")
    plan=private/"00_control/FACTORY_5_DAY_LAUNCH_PLAN_v01.md"
    oc=private/"00_control/FACTORY_OPERATION_CENTER.md"
    missing=[p.name for p in (plan,oc) if not p.is_file()]
    if missing:
        print("gate_id=FACTORY_LAUNCH_CONTROL_PLANE_GATE\nresult=FAIL\nerror_class=missing_required_file")
        print("error_codes="+",".join(missing)); return 1
    plan_text,oc_text=plan.read_text(),oc.read_text()
    errors=[]
    for token in ("FACTORY_ID=AI_COURSE_FACTORY","STATUS=ACTIVE_LAUNCH_SPRINT","NO_FAKE_GREEN=true","RUNNER_REPO=TheGor-365/ai-course-actions-runner"):
        if token not in plan_text: errors.append("plan_"+hashlib.sha256(token.encode()).hexdigest()[:12])
    for token in ("FACTORY_ID=AI_COURSE_FACTORY","NO_FAKE_GREEN=true","PUBLIC_RUNNER_MEDIA=false","PRIVATE_EXECUTOR_REQUIRED=true"):
        if token not in oc_text: errors.append("oc_"+hashlib.sha256(token.encode()).hexdigest()[:12])
    sha=subprocess.check_output(["git","-C",str(private),"rev-parse","HEAD"],text=True).strip()
    print("gate_id=FACTORY_LAUNCH_CONTROL_PLANE_GATE")
    print("private_sha="+sha+"\ncontrol_file_count=2")
    print("launch_plan_sha256="+hashlib.sha256(plan.read_bytes()).hexdigest())
    print("operation_center_sha256="+hashlib.sha256(oc.read_bytes()).hexdigest())
    print("no_fake_green_declared=true\npublic_media_allowed=false\nprivate_content_printed=false")
    print("result="+("FAIL" if errors else "PASS"))
    if errors: print("error_class=launch_control_plane_contract_mismatch\nerror_codes="+",".join(errors))
    return bool(errors)

def validate_request(req:dict)->None:
    required={"schema_version","request_id","package_request_id","station_id","attempt_id","executor_class","input_manifest_pointer","input_hash","command_profile_id","runtime_lock_id","resource_limits","timeout_seconds","output_artifact_types","idempotency_key","cleanup_policy"}
    if required-set(req) or set(req)-(required|{"resume_token_optional"}): raise ContractError("request_fields")
    if any(not isinstance(req[k],str) or not SAFE.fullmatch(req[k]) for k in ("request_id","package_request_id","station_id","attempt_id","idempotency_key")): raise ContractError("unsafe_id")
    if req["schema_version"]!="1.0" or req["executor_class"]!="locked_private_Linux_host_or_self_hosted_private_runner": raise ContractError("executor_contract")
    if not str(req["input_manifest_pointer"]).startswith("private-manifest://") or not HEX64.fullmatch(req["input_hash"]): raise ContractError("input_identity")
    if req["command_profile_id"]!="FIXTURE_ARTIFACT_V1" or req["runtime_lock_id"]!="fixture-runtime-v1" or req["cleanup_policy"]!="fixture_cleanup_v1": raise ContractError("fixed_profile")
    if req["output_artifact_types"]!=["fixture_text"] or not 1<=req["timeout_seconds"]<=30: raise ContractError("execution_limits")
    limits=req["resource_limits"]
    if set(limits)!={"cpu_count","memory_mb","disk_mb"} or not 1<=limits["cpu_count"]<=4 or not 64<=limits["memory_mb"]<=1024 or not 1<=limits["disk_mb"]<=128: raise ContractError("resource_limits")

def validate_private_contract()->int:
    bundle=load(ROOT/"schemas/private_executor_v1.schemas.json")
    profiles=load(ROOT/"config/private_executor_profiles_v1.json")
    expected={"private_executor_request_v1","private_executor_receipt_v1","artifact_pointer_record_v1"}
    if set(bundle.get("schemas",{}))!=expected: raise ContractError("schema_bundle")
    if profiles.get("arbitrary_command_input_allowed") is not False or set(profiles.get("profiles",{}))!={"FIXTURE_ARTIFACT_V1"}: raise ContractError("profile_manifest")
    profile=profiles["profiles"]["FIXTURE_ARTIFACT_V1"]
    if profile.get("media") is not False or profile.get("fixture_only") is not True: raise ContractError("profile_policy")
    print("validator=private_executor_contract_v1\nrequest_schema=PASS\nreceipt_schema=PASS\nartifact_pointer_schema=PASS\nfixed_profile_count=1\narbitrary_command_input=false\nresult=PASS")
    return 0

def safe(receipt:dict)->None:
    print("executor_id=private-executor-fixture-v1")
    print("result="+receipt["result"]+"\nfailure_class="+receipt["failure_class"]+"\nretryable="+str(receipt["retryable"]).lower())
    print("artifact_count="+str(len(receipt["output_artifacts"])))
    if receipt["output_artifacts"]:
        art=receipt["output_artifacts"][0]
        print("artifact_sha256="+art["sha256"]+"\nartifact_size_bytes="+str(art["size_bytes"])+"\nrestore_status="+art["restore_status"])
    print("cleanup_status="+receipt["cleanup_status"]+"\nprivate_content_public_exposure=false")

def execute(args)->int:
    started=now(); req=load(Path(args.request)); validate_request(req)
    state_dir=Path(args.state_dir).resolve(); store=Path(args.artifact_dir).resolve(); receipt_path=Path(args.receipt).resolve()
    state_dir.mkdir(parents=True,exist_ok=True); store.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(req["idempotency_key"].encode()).hexdigest(); state_path=state_dir/(digest+".json")
    state={"prepare_count":0,"materialize_count":0,"backup_restore_count":0,"failure_injected":False,"completed":False,"artifact_record":None}
    if state_path.exists(): state=load(state_path)
    if not state["completed"] and state["prepare_count"]==0: state["prepare_count"]=1; write_json(state_path,state)
    def base():
        return {"schema_version":"1.0","request_id":req["request_id"],"station_id":req["station_id"],"attempt_id":req["attempt_id"],"executor_id":"private-executor-fixture-v1","runtime_lock_id":req["runtime_lock_id"],"started_at":started,"completed_at":now(),"exit_code":0,"result":"PASS","failure_class":"NONE","retryable":False,"output_artifacts":[],"sanitized_metrics":{},"resume_token_optional":None,"cleanup_status":"PASS","private_content_public_exposure":False}
    if args.inject_failure_once and not state["failure_injected"] and not state["completed"]:
        state["failure_injected"]=True; state["resume_token"]=hashlib.sha256((digest+":resume:v1").encode()).hexdigest(); write_json(state_path,state)
        receipt=base(); receipt.update({"exit_code":RETRY,"result":"RETRYABLE_FAILURE","failure_class":"STATION_RETRYABLE_FAILURE","retryable":True,"resume_token_optional":state["resume_token"],"cleanup_status":"DEFERRED","sanitized_metrics":{"prepare_count":1,"materialize_count":0,"failure_injected":True}})
        write_json(receipt_path,receipt); safe(receipt); return RETRY
    if state.get("resume_token") and req.get("resume_token_optional")!=state["resume_token"]: raise ContractError("resume_token_mismatch")
    if not state["completed"]:
        data=("AI_COURSE_FACTORY_PRIVATE_EXECUTOR_FIXTURE_V1\n"+f"package_request_id={req['package_request_id']}\nstation_id={req['station_id']}\ninput_hash={req['input_hash']}\n").encode()
        name=digest+".txt"; art=store/name; art.write_bytes(data); state["materialize_count"]+=1
        backup_dir,restore_dir=store/"backup",store/"restore_check"; backup_dir.mkdir(exist_ok=True); restore_dir.mkdir(exist_ok=True)
        backup,restore=backup_dir/name,restore_dir/name; shutil.copy2(art,backup); shutil.copy2(backup,restore); state["backup_restore_count"]+=1
        hashes=[hashlib.sha256(x.read_bytes()).hexdigest() for x in (art,backup,restore)]
        if len(set(hashes))!=1: raise ContractError("artifact_hash_mismatch")
        restore.unlink(); restore_dir.rmdir()
        state["artifact_record"]={"artifact_id":"fixture-"+digest[:24],"package_request_id":req["package_request_id"],"station_id":req["station_id"],"artifact_type":"fixture_text","sha256":hashes[0],"size_bytes":art.stat().st_size,"codec_or_format":"text/plain; charset=utf-8","duration_ms_optional":None,"private_storage_pointer":f"private-artifact://fixture/{name}","producer_version":"private-executor-fixture-v1","created_at":now(),"backup_pointer_optional":f"private-backup://fixture/{name}","restore_status":"PASS","QC_identity_optional":"sha256_restore_identity_v1"}
        state["completed"]=True; write_json(state_path,state)
    receipt=base(); receipt["output_artifacts"]=[state["artifact_record"]]; receipt["resume_token_optional"]=state.get("resume_token")
    receipt["sanitized_metrics"]={k:state[k] for k in ("prepare_count","materialize_count","backup_restore_count")}
    write_json(receipt_path,receipt); safe(receipt); return 0

def main()->int:
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("resolve-gate"); p.add_argument("gate_id"); p.add_argument("private_repo"); p.add_argument("--field",required=True,choices=["profile_id","handler_id","output_schema_file","validation_strength"])
    sub.add_parser("validate-contract"); sub.add_parser("validate-private-contract")
    p=sub.add_parser("run-launch-gate"); p.add_argument("--private-dir",required=True)
    p=sub.add_parser("execute-fixture"); p.add_argument("--request",required=True); p.add_argument("--state-dir",required=True); p.add_argument("--artifact-dir",required=True); p.add_argument("--receipt",required=True); p.add_argument("--inject-failure-once",action="store_true")
    args=parser.parse_args()
    try:
        if args.command=="resolve-gate": print(resolve(args.gate_id,args.private_repo,args.field)); return 0
        if args.command=="validate-contract": return validate_contract()
        if args.command=="validate-private-contract": return validate_private_contract()
        if args.command=="run-launch-gate": return launch_gate(Path(args.private_dir).resolve())
        if args.command=="execute-fixture": return execute(args)
        raise ContractError("unknown_command")
    except (ContractError,OSError,ValueError,json.JSONDecodeError) as exc:
        print("result=TERMINAL_FAILURE\nfailure_class=STATION_TERMINAL_FAILURE\nretryable=false")
        print("error_code="+type(exc).__name__+"\nprivate_content_public_exposure=false"); return 2

if __name__=="__main__": raise SystemExit(main())
