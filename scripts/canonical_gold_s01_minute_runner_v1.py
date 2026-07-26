#!/usr/bin/env python3
"""Fail-closed coordinator for canonical Gold S01 minute proofs."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

HEX40=re.compile(r"^[0-9a-f]{40}$");HEX64=re.compile(r"^[0-9a-f]{64}$")
class RunnerError(RuntimeError): pass
def fail(code:str,detail:str)->None:raise RunnerError(f"{code}:{detail}")
def canonical(value:Any)->bytes:return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def load(path:Path)->dict[str,Any]:
    if not path.is_file():fail("MISSING_REQUIRED_FILE",path.as_posix())
    try:value=json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as exc:raise RunnerError(f"JSON_READ_FAILED:{path}") from exc
    if not isinstance(value,dict):fail("JSON_OBJECT_REQUIRED",path.as_posix())
    return value
def write(path:Path,value:Mapping[str,Any])->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(dict(value)))
def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()
def run(command:Sequence[str],cwd:Path|None=None)->str:
    p=subprocess.run(list(command),cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,shell=False)
    if p.returncode:fail("FIXED_COMMAND_FAILED",hashlib.sha256((p.stdout+p.stderr).encode()).hexdigest())
    return p.stdout.strip()
def git_head(path:Path)->str:return run(["git","rev-parse","HEAD"],path)
def safe_rel(value:str)->Path:
    path=Path(value)
    if not value or path.is_absolute() or ".." in path.parts:fail("UNSAFE_RELATIVE_PATH",value)
    return path
def validate_profile(profile:dict[str,Any])->None:
    if profile.get("schema_version")!="canonical_gold_s01_minute_runner_profile.v1":fail("PROFILE_SCHEMA_MISMATCH",str(profile.get("schema_version")))
    if profile.get("full_15_minute_render_authorized") is not False:fail("FULL_RENDER_NOT_AUTHORIZED","profile")
    if profile.get("human_final_preview_accepted") is not False:fail("HUMAN_ACCEPTANCE_FALSE_REQUIRED","profile")
    if profile.get("no_fake_green") is not True:fail("NO_FAKE_GREEN_MISSING","profile")
    for section in ("source","production"):
        record=profile[section]
        if not HEX40.fullmatch(record["sha"]):fail("INVALID_EXACT_SHA",section)
        safe_rel(record.get("canonical_psu_root",record.get("request_path","x")))
    pilots=profile["pilots"]
    if not all(pilots.get(key) is True for key in ("contiguous_required","audio_required","captions_required")):fail("PILOT_REQUIRED_POLICY_MISSING","pilots")
    if pilots.get("capability_montage_allowed") is not False:fail("MONTAGE_PILOT","profile")
    captions=profile["captions"]
    if captions.get("draft_srt_fallback_allowed") is not False or captions.get("regeneration_allowed") is not False:fail("CAPTION_FALLBACK_FORBIDDEN","profile")
def validate_checkout(path:Path,expected:str,code:str)->None:
    if not path.is_dir():fail(f"{code}_MISSING",path.as_posix())
    observed=git_head(path)
    if observed!=expected:fail(f"{code}_HEAD_MISMATCH",f"{observed}!={expected}")
    if run(["git","status","--porcelain"],path):fail(f"{code}_DIRTY","checkout")
def preflight(args:argparse.Namespace)->int:
    profile=load(Path(args.profile));validate_profile(profile);source=Path(args.source_dir);production=Path(args.production_dir);inputs=Path(args.inputs_dir);out=Path(args.output)
    blockers=[]
    try:validate_checkout(source,profile["source"]["sha"],"SOURCE")
    except RunnerError as exc:blockers.append(str(exc).split(":",1)[0])
    try:validate_checkout(production,profile["production"]["sha"],"PRODUCTION")
    except RunnerError as exc:blockers.append(str(exc).split(":",1)[0])
    request=production/safe_rel(profile["production"]["request_path"])
    if not request.is_file():blockers.append("CANONICAL_REQUEST_MISSING")
    else:
        data=load(request)
        if data.get("full_15_minute_render_authorized") is not False:blockers.append("FULL_RENDER_NOT_AUTHORIZED")
        if data.get("pilot_must_be_contiguous") is not True:blockers.append("NON_CONTIGUOUS_WINDOW")
        if data.get("pilot_audio_required") is not True:blockers.append("SILENT_PILOT")
        if data.get("pilot_captions_required") is not True:blockers.append("CAPTION_WINDOW_MISMATCH")
        if "FULL_VISUAL_MASTER_RENDER" in data.get("station_enum",[]):blockers.append("FULL_RENDER_STATION_PRESENT")
    audio=inputs/"audio"/profile["audio"]["asset_name"]
    if not audio.is_file():blockers.append("A3483_INPUT_MISSING")
    elif sha(audio)!=profile["audio"]["sha256"] or audio.stat().st_size!=profile["audio"]["size_bytes"]:blockers.append("WRONG_AUDIO_SHA")
    captions=profile["captions"];caption_json=inputs/"captions"/captions["accepted_json_name"];caption_vtt=inputs/"captions"/captions["accepted_vtt_name"]
    if not caption_json.is_file():blockers.append("ACCEPTED_CAPTION_JSON_MISSING")
    elif sha(caption_json)!=captions["accepted_json_sha256"]:blockers.append("FINAL_CAPTIONS_HASH_MISMATCH")
    if not caption_vtt.is_file():blockers.append("ACCEPTED_CAPTION_VTT_MISSING")
    elif not caption_vtt.read_text(encoding="utf-8",errors="strict").startswith("WEBVTT"):blockers.append("ACCEPTED_CAPTION_VTT_INVALID")
    receipt={"schema_version":"canonical_gold_s01_runner_preflight.v1","status":"PASS" if not blockers else "BLOCKED","source_sha":profile["source"]["sha"],"production_sha":profile["production"]["sha"],"blockers":sorted(set(blockers)),"pilot_audio_required":True,"pilot_captions_required":True,"pilot_must_be_contiguous":True,"full_15_minute_render_authorized":False,"full_15_minute_rendered":False,"human_final_preview_accepted":False,"no_fake_green":True}
    write(out,receipt);print(json.dumps(receipt,sort_keys=True));return 0 if not blockers else 2
def verify_artifact(args:argparse.Namespace)->int:
    root=Path(args.artifact_dir);expected=load(Path(args.expected_receipt));videos=list(root.rglob("*.mp4"))
    if len(videos)!=1:fail("DOWNLOADED_MP4_COUNT_INVALID",str(len(videos)))
    observed=sha(videos[0]);declared=expected.get("media_sha256")
    if observed!=declared:fail("PUBLIC_ARTIFACT_DOWNLOAD_HASH_MISMATCH",f"{observed}!={declared}")
    result={"schema_version":"canonical_gold_s01_artifact_identity.v1","artifact_name":args.artifact_name,"mp4_sha256":observed,"public_artifact_download_hash_verified":True,"full_15_minute_rendered":False,"human_final_preview_accepted":False,"no_fake_green":True};write(Path(args.output),result);print(json.dumps(result,sort_keys=True));return 0
def summarize(args:argparse.Namespace)->int:
    receipts=[load(Path(path)) for path in args.receipt]
    result={"schema_version":"canonical_gold_s01_runner_summary.v1","run_id":os.environ.get("GITHUB_RUN_ID","local"),"source_sha":args.source_sha,"production_sha":args.production_sha,"pilot_receipts":receipts,"pilot_count":len(receipts),"all_media_identity_verified":all(item.get("public_artifact_download_hash_verified") is True for item in receipts if "public_artifact_download_hash_verified" in item),"machine_qc_green":all(item.get("machine_qc",{}).get("machine_qc_green") is True for item in receipts if "machine_qc" in item),"full_15_minute_rendered":False,"human_final_preview_accepted":False,"no_fake_green":True};write(Path(args.output),result);print(json.dumps(result,sort_keys=True));return 0
def main()->int:
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("preflight");p.add_argument("--profile",required=True);p.add_argument("--source-dir",required=True);p.add_argument("--production-dir",required=True);p.add_argument("--inputs-dir",required=True);p.add_argument("--output",required=True);p.set_defaults(func=preflight)
    p=sub.add_parser("verify-artifact");p.add_argument("--artifact-dir",required=True);p.add_argument("--artifact-name",required=True);p.add_argument("--expected-receipt",required=True);p.add_argument("--output",required=True);p.set_defaults(func=verify_artifact)
    p=sub.add_parser("summarize");p.add_argument("--source-sha",required=True);p.add_argument("--production-sha",required=True);p.add_argument("--receipt",action="append",required=True);p.add_argument("--output",required=True);p.set_defaults(func=summarize)
    args=parser.parse_args();return args.func(args)
if __name__=="__main__":
    try:raise SystemExit(main())
    except RunnerError as error:print(str(error));raise SystemExit(1)
