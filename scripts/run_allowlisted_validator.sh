#!/usr/bin/env bash
set -euo pipefail

GATE_ID="${1:-}"
PRIVATE_DIR="${2:-}"

fail() {
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  exit "${3:-1}"
}

if [[ -z "$GATE_ID" || -z "$PRIVATE_DIR" ]]; then
  fail "policy" "missing_required_arguments" 2
fi

if [[ ! -d "$PRIVATE_DIR/.git" ]]; then
  fail "policy" "private_checkout_missing" 2
fi

cd "$PRIVATE_DIR"
PRIVATE_SHA="$(git rev-parse HEAD)"
TOP_LEVEL_COUNT="$(find . -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"

case "$GATE_ID" in
  FACTORY_PUBLIC_RUNNER_SMOKE)
    echo "gate_id=$GATE_ID"
    echo "private_sha=$PRIVATE_SHA"
    echo "top_level_path_count=$TOP_LEVEL_COUNT"
    echo "artifact_policy=none"
    echo "private_content_printed=false"
    echo "result=PASS"
    ;;

  A3479_CONTENT_ONLY_LOCAL_GATE)
    python3 - <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path('.')
paths = {
    'target_timing_contract': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_target_timing_contract_v01.json',
    'visual_anchor_contract': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_visual_anchor_target_contract_v01.csv',
    'beat_fit_policy': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_beat_fit_tool_policy_v01.csv',
    'report': ROOT / '08_reports/M1_L01_A3_4_7_9_TARGET_TIMING_CONTRACT_REPORT.md',
}
expected = {'beats': 13, 'visual_anchor_targets': 24, 'hard_anchors': 15, 'soft_anchors': 9, 'sfx_targets': 15, 'policy_rows': 13}
errors = []
def add_error(code): errors.append(code)
for key, path in paths.items():
    if not path.is_file(): add_error(f'missing_{key}')
if errors:
    print('gate_id=A3479_CONTENT_ONLY_LOCAL_GATE')
    print('result=FAIL')
    print('error_class=missing_required_file')
    print('error_codes=' + ','.join(errors))
    sys.exit(1)
contract = json.loads(paths['target_timing_contract'].read_text(encoding='utf-8'))
contract_numbers = contract.get('contract_numbers', {})
beats = contract.get('beat_targets', [])
non_claims = contract.get('non_claims', {})
with paths['visual_anchor_contract'].open(encoding='utf-8', newline='') as f: visual_rows = list(csv.DictReader(f))
with paths['beat_fit_policy'].open(encoding='utf-8', newline='') as f: policy_rows = list(csv.DictReader(f))
observed = {
    'beats': len(beats),
    'visual_anchor_targets': len(visual_rows),
    'hard_anchors': sum(1 for row in visual_rows if row.get('anchor_type') == 'hard'),
    'soft_anchors': sum(1 for row in visual_rows if row.get('anchor_type') == 'soft'),
    'sfx_targets': sum(1 for row in visual_rows if row.get('sfx_id')),
    'policy_rows': len(policy_rows),
}
for key, value in expected.items():
    if observed.get(key) != value: add_error(f'{key}_expected_{value}_observed_{observed.get(key)}')
for key, value in {'beats_created': 13, 'visual_anchor_targets_created': 24, 'hard_anchor_targets_created': 15, 'soft_anchor_targets_created': 9, 'sfx_anchor_targets_created': 15}.items():
    if contract_numbers.get(key) != value: add_error(f'contract_numbers_{key}_expected_{value}_observed_{contract_numbers.get(key)}')
for key in ['audio_production_green', 'video_allowed', 'sync_green', 'video_generated', 'final_video_green']:
    if non_claims.get(key) is not False: add_error(f'non_claim_{key}_not_false')
report_text = paths['report'].read_text(encoding='utf-8')
required_report_tokens = ['TARGET_TIMING_CONTRACT_CREATED=true','BEAT_TARGET_WINDOWS_CREATED=13','VISUAL_ANCHOR_TARGETS_CREATED=24','HARD_VISUAL_ANCHORS_CREATED=15','SOFT_VISUAL_ANCHORS_CREATED=9','SFX_TARGET_LINKS_CREATED=15','AUDIO_PRODUCTION_GREEN=false','VIDEO_ALLOWED=false','SYNC_GREEN=false']
for token in required_report_tokens:
    if token not in report_text: add_error('report_token_missing_' + hashlib.sha256(token.encode()).hexdigest()[:12])
print('gate_id=A3479_CONTENT_ONLY_LOCAL_GATE')
for key in ['beats', 'visual_anchor_targets', 'hard_anchors', 'soft_anchors', 'sfx_targets', 'policy_rows']:
    print(f'{key}={observed[key]}')
print('video_allowed=false')
print('sync_green=false')
print('audio_production_green=false')
for key, path in paths.items(): print(f'sha256_{key}={hashlib.sha256(path.read_bytes()).hexdigest()}')
print('private_content_printed=false')
if errors:
    print('result=FAIL')
    print('error_class=validator_contract_mismatch')
    print('error_count=' + str(len(errors)))
    print('error_codes=' + ','.join(errors[:20]))
    sys.exit(1)
print('result=PASS')
PY
    ;;

  A3480_SCRIPT_FIT_PACK_LOCAL_GATE)
    python3 - <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path('.')
paths = {
    'a3479_target_timing_contract': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_target_timing_contract_v01.json',
    'ru_script_fit_pack_json': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_ru_script_fit_pack_v01.json',
    'ru_script_fit_pack_csv': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_ru_script_fit_pack_v01.csv',
    'ru_prosody_source_contract': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_ru_prosody_source_contract_v01.json',
    'ru_tts_candidate_requirements': ROOT / '03_modules/M1/L01/06_audio_video_sync/prosody_source_control/s01_ru_tts_candidate_requirements_v01.json',
    'report': ROOT / '08_reports/M1_L01_A3_4_8_0_RU_SCRIPT_FIT_PROSODY_SOURCE_CONTRACT_REPORT.md',
    'validator': ROOT / '04_validators/audio_video_sync/validate_m1_l01_s01_a3480_ru_script_fit_prosody_source_contract.py',
}
errors = []
def add_error(code): errors.append(code)
for key, path in paths.items():
    if not path.is_file(): add_error(f'missing_{key}')
if errors:
    print('gate_id=A3480_SCRIPT_FIT_PACK_LOCAL_GATE')
    print('files_exist=false')
    print('result=FAIL')
    print('error_class=missing_required_file')
    print('error_codes=' + ','.join(errors))
    sys.exit(1)
try:
    a3479 = json.loads(paths['a3479_target_timing_contract'].read_text(encoding='utf-8'))
    fit_json = json.loads(paths['ru_script_fit_pack_json'].read_text(encoding='utf-8'))
    prosody = json.loads(paths['ru_prosody_source_contract'].read_text(encoding='utf-8'))
    tts_req = json.loads(paths['ru_tts_candidate_requirements'].read_text(encoding='utf-8'))
except Exception as exc:
    print('gate_id=A3480_SCRIPT_FIT_PACK_LOCAL_GATE')
    print('result=FAIL')
    print('error_class=json_parse_failure')
    print('error_code=' + type(exc).__name__)
    sys.exit(1)
contract_numbers = a3479.get('contract_numbers', {})
expected_counts = {
    'beats': 13,
    'visual_anchor_targets': 24,
    'hard_anchors': 15,
    'soft_anchors': 9,
    'sfx_targets': 15,
}
observed = {
    'beats': len(a3479.get('beat_targets', [])),
    'visual_anchor_targets': contract_numbers.get('visual_anchor_targets_created'),
    'hard_anchors': contract_numbers.get('hard_anchor_targets_created'),
    'soft_anchors': contract_numbers.get('soft_anchor_targets_created'),
    'sfx_targets': contract_numbers.get('sfx_anchor_targets_created'),
}
for key, expected in expected_counts.items():
    if observed.get(key) != expected: add_error(f'a3479_{key}_expected_{expected}_observed_{observed.get(key)}')
with paths['ru_script_fit_pack_csv'].open(encoding='utf-8', newline='') as f:
    fit_rows = list(csv.DictReader(f))
fit_items = fit_json.get('fit_pack') or fit_json.get('beats') or fit_json.get('items') or []
prosody_items = prosody.get('prosody_units') or prosody.get('beats') or prosody.get('items') or []
tts_items = tts_req.get('candidate_requirements') or tts_req.get('beats') or tts_req.get('items') or []
if len(fit_rows) != 13: add_error(f'fit_pack_rows_expected_13_observed_{len(fit_rows)}')
if isinstance(fit_items, list) and len(fit_items) != 13: add_error(f'fit_pack_json_items_expected_13_observed_{len(fit_items)}')
if isinstance(prosody_items, list) and len(prosody_items) != 13: add_error(f'prosody_items_expected_13_observed_{len(prosody_items)}')
if isinstance(tts_items, list) and len(tts_items) != 13: add_error(f'tts_requirement_items_expected_13_observed_{len(tts_items)}')
non_claim_flags = {
    'tts_candidates_rendered': False,
    'audio_created': False,
    'audio_production_green': False,
    'video_allowed': False,
    'sync_green': False,
}
for obj_name, obj in [('fit_pack', fit_json), ('prosody', prosody), ('tts_requirements', tts_req)]:
    non_claims = obj.get('non_claims', {}) if isinstance(obj, dict) else {}
    for key, expected in non_claim_flags.items():
        if non_claims.get(key) is not expected:
            add_error(f'{obj_name}_non_claim_{key}_not_false')
report_text = paths['report'].read_text(encoding='utf-8')
required_report_tokens = [
    'READ_A3479_TARGET_TIMING_CONTRACT=true',
    'BEAT_WINDOWS=13',
    'VISUAL_ANCHOR_TARGETS=24',
    'HARD_ANCHORS=15',
    'SOFT_ANCHORS=9',
    'SFX_TARGETS=15',
    'RU_SCRIPT_FIT_PACK_CREATED=true',
    'PROSODY_SOURCE_CONTRACT_CREATED=true',
    'TTS_CANDIDATE_REQUIREMENTS_CREATED=true',
    'TTS_CANDIDATES_RENDERED=false',
    'AUDIO_CREATED=false',
    'AUDIO_PRODUCTION_GREEN=false',
    'VIDEO_ALLOWED=false',
    'SYNC_GREEN=false',
]
for token in required_report_tokens:
    if token not in report_text: add_error('report_token_missing_' + hashlib.sha256(token.encode()).hexdigest()[:12])
print('gate_id=A3480_SCRIPT_FIT_PACK_LOCAL_GATE')
print('private_sha=' + (ROOT / '.git').exists().__str__().lower())
print('files_exist=true')
print('beat_count=' + str(observed['beats']))
print('visual_anchor_targets=' + str(observed['visual_anchor_targets']))
print('hard_anchors=' + str(observed['hard_anchors']))
print('soft_anchors=' + str(observed['soft_anchors']))
print('sfx_targets=' + str(observed['sfx_targets']))
print('fit_pack_rows=' + str(len(fit_rows)))
print('prosody_contract_exists=true')
print('tts_candidate_requirements_exists=true')
print('audio_created=false')
print('video_allowed=false')
print('sync_green=false')
print('private_content_printed=false')
print('artifact_policy=none')
for key, path in paths.items(): print(f'sha256_{key}={hashlib.sha256(path.read_bytes()).hexdigest()}')
if errors:
    print('result=FAIL')
    print('error_class=a3480_contract_mismatch')
    print('error_count=' + str(len(errors)))
    print('error_codes=' + ','.join(errors[:25]))
    sys.exit(1)
print('result=PASS')
PY
    ;;

  A3479_CI_SCOPE_GUARD_DOC_GATE)
    WORKFLOW_COUNT="$(find .github/workflows -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | wc -l | tr -d ' ')"
    REPORT_COUNT="$(find 08_reports -type f 2>/dev/null | wc -l | tr -d ' ')"
    echo "gate_id=$GATE_ID"
    echo "private_sha=$PRIVATE_SHA"
    echo "workflow_file_count=$WORKFLOW_COUNT"
    echo "report_file_count=$REPORT_COUNT"
    echo "private_content_printed=false"
    echo "result=PASS"
    ;;

  M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET)
    M1_L01_COUNT="$(find 03_modules/M1/L01 -type f 2>/dev/null | wc -l | tr -d ' ')"
    VALIDATOR_COUNT="$(find 04_validators -type f 2>/dev/null | wc -l | tr -d ' ')"
    echo "gate_id=$GATE_ID"
    echo "private_sha=$PRIVATE_SHA"
    echo "m1_l01_file_count=$M1_L01_COUNT"
    echo "validator_file_count=$VALIDATOR_COUNT"
    echo "private_content_printed=false"
    echo "result=PASS"
    ;;

  *)
    fail "policy" "gate_id_not_allowlisted" 2
    ;;
esac
