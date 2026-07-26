from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
HEX40 = re.compile('^[0-9a-f]{40}$')
HEX64 = re.compile('^[0-9a-f]{64}$')
REQUIRED_LANES = ('A', 'B', 'C', 'D', 'E')
REQUIRED_HASH_KEYS = ('PSU_CLOSURE_SHA256', 'PREMIUM_SHOT_SPEC_SHA256', 'SHARED_ID_REGISTRY_SHA256', 'COMPILER_SHA256', 'ShotIR_SHA256', 'SceneIR_SHA256', 'ASSET_MANIFEST_SHA256', 'RUNTIME_BINDING_SHA256', 'QC_MANIFEST_SHA256', 'CAPTION_JSON_SHA256', 'CAPTION_VTT_SHA256')
REQUIRED_EFFECTS = ('code_typewriter', 'operator_pulse', 'token_glow', 'line_focus', 'execution_path', 'value_to_object_binding')
EXPECTED_OC_HEAD = 'd2aa0ee07bc9323bcc4a2bd134806d09c217eeeb'
EXPECTED_CAPTION_JSON = '5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18'
EXPECTED_AUDIO_SHA = '74d9a9008b594bd8bd18f001d05542e249bd9af371c32e87181a0df42064f352'
EXPECTED_AUDIO_SIZE = 43603182

class ProofError(RuntimeError):
    pass

def fail(code: str, detail: str='') -> 'NoReturn':
    raise ProofError(f'{code}:{detail}' if detail else code)

def load_json(path: Path) -> Any:
    if not path.is_file():
        fail('MISSING_REQUIRED_FILE', path.as_posix())
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProofError(f'INVALID_JSON:{path.as_posix()}') from exc

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')

def sha256(path: Path) -> str:
    if not path.is_file():
        fail('MISSING_REQUIRED_FILE', path.as_posix())
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def safe_rel(value: Any, key: str) -> Path:
    if not isinstance(value, str) or not value:
        fail('SAFE_RELATIVE_PATH_REQUIRED', key)
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or '\x00' in value:
        fail('UNSAFE_RELATIVE_PATH', key)
    return path

def require_sha(value: Any, key: str, length: int) -> str:
    pattern = HEX40 if length == 40 else HEX64
    if not isinstance(value, str) or not pattern.fullmatch(value):
        fail(f'INVALID_SHA{length}', key)
    return value

def run(argv: Sequence[str], cwd: Path | None=None, capture: bool=False) -> str:
    proc = subprocess.run(list(argv), cwd=cwd, check=False, shell=False, text=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)
    if proc.returncode:
        material = ((proc.stdout or '') + (proc.stderr or '')).encode('utf-8', errors='replace')
        fail('FIXED_COMMAND_FAILED', hashlib.sha256(material).hexdigest())
    return (proc.stdout or '').strip()

def manifest(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if not isinstance(value, dict):
        fail('MANIFEST_OBJECT_REQUIRED')
    if value.get('schema_version') != 'canonical_gold_s01_exact_inputs.v2':
        fail('MANIFEST_SCHEMA_MISMATCH')
    return value

def verify_policy(data: Mapping[str, Any]) -> None:
    policy = data.get('policy')
    if not isinstance(policy, dict):
        fail('POLICY_OBJECT_REQUIRED')
    forbidden_true = ('skip_event_QC', 'ignore_telemetry', 'replace_missing_asset', 'lower_premium_gate', 'switch_to_legacy_composition', 'use_silent_audio', 'use_draft_captions', 'full_15_minute_render_authorized', 'human_final_acceptance')
    for key in forbidden_true:
        if policy.get(key) is not False:
            fail('FORBIDDEN_POLICY_STATE', key)
    if policy.get('no_fake_green') is not True:
        fail('NO_FAKE_GREEN_REQUIRED')

def validate_exact_manifest(data: Mapping[str, Any]) -> None:
    if data.get('status') != 'EXACT_RECONCILED':
        fail('UPSTREAM_INPUTS_PROVISIONAL', str(data.get('status')))
    if data.get('OC_HEAD') != EXPECTED_OC_HEAD:
        fail('OC_HEAD_MISMATCH', str(data.get('OC_HEAD')))
    require_sha(data.get('SOURCE_HEAD_LANE_A'), 'SOURCE_HEAD_LANE_A', 40)
    require_sha(data.get('SOURCE_HEAD_LANE_B'), 'SOURCE_HEAD_LANE_B', 40)
    require_sha(data.get('SOURCE_HEAD_RECONCILED'), 'SOURCE_HEAD_RECONCILED', 40)
    require_sha(data.get('PRODUCTION_HEAD_LANE_C'), 'PRODUCTION_HEAD_LANE_C', 40)
    require_sha(data.get('PRODUCTION_HEAD_LANE_D'), 'PRODUCTION_HEAD_LANE_D', 40)
    require_sha(data.get('PRODUCTION_HEAD_LANE_E'), 'PRODUCTION_HEAD_LANE_E', 40)
    require_sha(data.get('PRODUCTION_HEAD_RECONCILED'), 'PRODUCTION_HEAD_RECONCILED', 40)
    for key in ('SOURCE_BRANCH_RECONCILED', 'PRODUCTION_BRANCH_RECONCILED'):
        if not isinstance(data.get(key), str) or not data[key]:
            fail('EXACT_BRANCH_REQUIRED', key)
    for key in REQUIRED_HASH_KEYS:
        require_sha(data.get(key), key, 64)
    if data.get('CAPTION_JSON_SHA256') != EXPECTED_CAPTION_JSON:
        fail('ACCEPTED_CAPTION_JSON_AUTHORITY_MISMATCH')
    for lane in REQUIRED_LANES:
        if data.get(f'LANE_{lane}_COMPLETE') is not True:
            fail('LANE_NOT_COMPLETE', lane)
    if data.get('EXACT_HEAD_RECONCILIATION') is not True:
        fail('EXACT_HEAD_RECONCILIATION_REQUIRED')
    receipts = data.get('LANE_RECEIPTS')
    if not isinstance(receipts, dict) or set(receipts) != set(REQUIRED_LANES):
        fail('LANE_RECEIPT_SET_INVALID')
    for lane, record in receipts.items():
        if not isinstance(record, dict):
            fail('LANE_RECEIPT_OBJECT_REQUIRED', lane)
        if record.get('repository') not in ('source', 'production'):
            fail('LANE_RECEIPT_REPOSITORY_INVALID', lane)
        safe_rel(record.get('path'), f'LANE_{lane}_RECEIPT_PATH')
        require_sha(record.get('sha256'), f'LANE_{lane}_RECEIPT_SHA256', 64)
        require_sha(record.get('head'), f'LANE_{lane}_RECEIPT_HEAD', 40)
    safe_rel(data.get('REMOTION_ROOT'), 'REMOTION_ROOT')
    safe_rel(data.get('PRODUCTION_BRIDGE_PATH'), 'PRODUCTION_BRIDGE_PATH')
    require_sha(data.get('PRODUCTION_BRIDGE_SHA256'), 'PRODUCTION_BRIDGE_SHA256', 64)
    bindings = data.get('IDENTITY_BINDINGS')
    expected_bindings = set(REQUIRED_HASH_KEYS) - {'CAPTION_JSON_SHA256', 'CAPTION_VTT_SHA256'}
    if not isinstance(bindings, dict) or set(bindings) != expected_bindings:
        fail('IDENTITY_BINDING_SET_INVALID')
    for key, record in bindings.items():
        if not isinstance(record, dict) or record.get('root') not in ('source', 'production', 'compiled'):
            fail('IDENTITY_BINDING_ROOT_INVALID', key)
        safe_rel(record.get('path'), f'{key}_PATH')
    if not isinstance(data.get('CAPTION_ARTIFACT_REPOSITORY'), str) or '/' not in data['CAPTION_ARTIFACT_REPOSITORY']:
        fail('CAPTION_ARTIFACT_REPOSITORY_REQUIRED')
    if not isinstance(data.get('CAPTION_ARTIFACT_ID'), int) or data['CAPTION_ARTIFACT_ID'] <= 0:
        fail('CAPTION_ARTIFACT_ID_REQUIRED')
    require_sha(data.get('CAPTION_ARTIFACT_ZIP_SHA256'), 'CAPTION_ARTIFACT_ZIP_SHA256', 64)
    if not isinstance(data.get('RUNNER_PR_NUMBER'), int) or data['RUNNER_PR_NUMBER'] <= 0:
        fail('RUNNER_PR_NUMBER_REQUIRED')
    targets = data.get('UPSTREAM_PR_TARGETS')
    if not isinstance(targets, list) or len(targets) < 5:
        fail('UPSTREAM_PR_TARGETS_REQUIRED')
    for target in targets:
        if not isinstance(target, dict) or not isinstance(target.get('repository'), str) or '/' not in target['repository']:
            fail('UPSTREAM_PR_TARGET_INVALID')
        if not isinstance(target.get('pr_number'), int) or target['pr_number'] <= 0:
            fail('UPSTREAM_PR_TARGET_INVALID')
    audio = data.get('A3483')
    if not isinstance(audio, dict):
        fail('A3483_OBJECT_REQUIRED')
    if audio.get('sha256') != EXPECTED_AUDIO_SHA or audio.get('size') != EXPECTED_AUDIO_SIZE:
        fail('A3483_AUTHORITY_MISMATCH')
    verify_policy(data)
    pilot_a = data.get('pilot_a', {})
    if pilot_a != {'start_ms': 0, 'end_ms': 60000, 'contiguous': True, 'audio_required': True, 'captions_required': True}:
        fail('PILOT_A_CONTRACT_MISMATCH')
    pilot_b = data.get('pilot_b')
    if not isinstance(pilot_b, dict):
        fail('PILOT_B_CONTRACT_REQUIRED')
    if pilot_b.get('duration_ms') != 60000 or pilot_b.get('contiguous') is not True:
        fail('PILOT_B_CONTIGUOUS_60000_REQUIRED')
    if pilot_b.get('audio_required') is not True or pilot_b.get('captions_required') is not True:
        fail('PILOT_B_MEDIA_REQUIRED')
    if tuple(pilot_b.get('required_effects', ())) != REQUIRED_EFFECTS:
        fail('PILOT_B_EFFECT_SET_MISMATCH')
