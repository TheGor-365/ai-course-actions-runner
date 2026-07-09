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

expected = {
    'beats': 13,
    'visual_anchor_targets': 24,
    'hard_anchors': 15,
    'soft_anchors': 9,
    'sfx_targets': 15,
    'policy_rows': 13,
}

errors = []

def add_error(code):
    errors.append(code)

for key, path in paths.items():
    if not path.is_file():
        add_error(f'missing_{key}')

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

with paths['visual_anchor_contract'].open(encoding='utf-8', newline='') as f:
    visual_rows = list(csv.DictReader(f))

with paths['beat_fit_policy'].open(encoding='utf-8', newline='') as f:
    policy_rows = list(csv.DictReader(f))

observed = {
    'beats': len(beats),
    'visual_anchor_targets': len(visual_rows),
    'hard_anchors': sum(1 for row in visual_rows if row.get('anchor_type') == 'hard'),
    'soft_anchors': sum(1 for row in visual_rows if row.get('anchor_type') == 'soft'),
    'sfx_targets': sum(1 for row in visual_rows if row.get('sfx_id')),
    'policy_rows': len(policy_rows),
}

for key, value in expected.items():
    if observed.get(key) != value:
        add_error(f'{key}_expected_{value}_observed_{observed.get(key)}')

number_checks = {
    'beats_created': 13,
    'visual_anchor_targets_created': 24,
    'hard_anchor_targets_created': 15,
    'soft_anchor_targets_created': 9,
    'sfx_anchor_targets_created': 15,
}
for key, value in number_checks.items():
    if contract_numbers.get(key) != value:
        add_error(f'contract_numbers_{key}_expected_{value}_observed_{contract_numbers.get(key)}')

false_claims = [
    'audio_production_green',
    'video_allowed',
    'sync_green',
    'video_generated',
    'final_video_green',
]
for key in false_claims:
    if non_claims.get(key) is not False:
        add_error(f'non_claim_{key}_not_false')

report_text = paths['report'].read_text(encoding='utf-8')
required_report_tokens = [
    'TARGET_TIMING_CONTRACT_CREATED=true',
    'BEAT_TARGET_WINDOWS_CREATED=13',
    'VISUAL_ANCHOR_TARGETS_CREATED=24',
    'HARD_VISUAL_ANCHORS_CREATED=15',
    'SOFT_VISUAL_ANCHORS_CREATED=9',
    'SFX_TARGET_LINKS_CREATED=15',
    'AUDIO_PRODUCTION_GREEN=false',
    'VIDEO_ALLOWED=false',
    'SYNC_GREEN=false',
]
for token in required_report_tokens:
    if token not in report_text:
        add_error('report_token_missing_' + hashlib.sha256(token.encode()).hexdigest()[:12])

print('gate_id=A3479_CONTENT_ONLY_LOCAL_GATE')
for key in ['beats', 'visual_anchor_targets', 'hard_anchors', 'soft_anchors', 'sfx_targets', 'policy_rows']:
    print(f'{key}={observed[key]}')
print('video_allowed=false')
print('sync_green=false')
print('audio_production_green=false')
for key, path in paths.items():
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f'sha256_{key}={digest}')
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
