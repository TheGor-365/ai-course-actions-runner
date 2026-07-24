#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=CONTENT_SEMANTICS_LAUNCH_GATE"
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit "${3:-1}"
}

classify_content_failure() {
  local message="$1"
  case "$message" in
    *"immutable request hash drift"*) echo immutable_request_hash_drift ;;
    *"source pointer not connector-attested"*) echo source_pointer_not_attested ;;
    *"source hash drift"*) echo source_blob_hash_drift ;;
    *"learner-facing internal ID leak"*) echo learner_text_internal_id_leak ;;
    *"unresolved placeholder token"*) echo unresolved_placeholder ;;
    *"semantic unit count mismatch"*) echo semantic_unit_count_mismatch ;;
    *"shot intent count mismatch"*) echo shot_intent_count_mismatch ;;
    *"semantic slot count mismatch"*) echo semantic_slot_count_mismatch ;;
    *"ShotIR source input count mismatch"*) echo shotir_input_count_mismatch ;;
    *"expected exactly two normalized shot intents per unit"*) echo shots_per_unit_mismatch ;;
    *"existing 24 visual events are not fully preserved"*) echo visual_event_coverage_mismatch ;;
    *"existing visual event mapped more than once"*) echo duplicate_visual_event_mapping ;;
    *"source-to-production semantic mapping incomplete"*) echo semantic_mapping_incomplete ;;
    *"source-to-production shot mapping incomplete"*) echo shot_mapping_incomplete ;;
    *"fabricated measured start"*|*"fabricated measured end"*) echo fabricated_measured_timing ;;
    *"invalid duration bounds"*) echo invalid_duration_bounds ;;
    *"missing fields"*) echo required_field_missing ;;
    *"empty required field"*) echo required_field_empty ;;
    *"incomplete claim field"*) echo technical_truth_claim_incomplete ;;
    *)
      local digest
      digest="$(printf '%s' "$message" | sha256sum | awk '{print $1}')"
      echo "unclassified_${digest:0:12}"
      ;;
  esac
}

if [[ -z "$PRIVATE_DIR" || ! -d "$PRIVATE_DIR/.git" ]]; then
  fail policy private_checkout_missing 2
fi

cd "$PRIVATE_DIR"
PRIVATE_SHA="$(git rev-parse HEAD)"
ROOT="Module 1/Lesson 1/launch_5d/content_semantics"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

python3 -m py_compile \
  "$ROOT/build_content_semantics.py" \
  "$ROOT/validate_content_semantics.py" \
  "$ROOT/validate_policy_bindings.py" \
  "$ROOT/validate_factory_request_bridge.py" \
  "$ROOT/validate_audio_authority_mapping.py" \
  >/dev/null 2>&1 || fail validator python_compile_failed

python3 "$ROOT/build_content_semantics.py" \
  --repo-root . \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator deterministic_build_failed

cmp \
  "$ROOT/M1-L01-S02_immutable_blind_request_v1.json" \
  "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  >/dev/null 2>&1 || fail validator legacy_request_reproducibility_failed

python3 "$ROOT/validate_policy_bindings.py" \
  --repo-root . \
  --request "$ROOT/M1-L01-S02_immutable_blind_request_v1.json" \
  >/dev/null 2>&1 || fail validator policy_bindings_failed

python3 "$ROOT/validate_audio_authority_mapping.py" \
  --mapping "$ROOT/S01_audio_authority_mapping_v1.json" \
  --attestation "$ROOT/audio_authority_connector_attestation_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator audio_authority_mapping_failed

VALIDATOR_LOG="$OUT/content_semantics_validator.log"
if ! python3 "$ROOT/validate_content_semantics.py" \
  --package "$OUT/M1-L01-S01_content_semantics_v1.json" \
  --request "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  --attestation "$ROOT/connector_preflight_attestation_v1.json" \
  >"$VALIDATOR_LOG" 2>&1; then
  FAILURE="$(sed -n 's/^FAILURE=//p' "$VALIDATOR_LOG" | tail -n 1)"
  [[ -n "$FAILURE" ]] || FAILURE=validator_failed_without_failure_record
  fail validator "$(classify_content_failure "$FAILURE")"
fi

python3 "$ROOT/validate_factory_request_bridge.py" \
  --request "$ROOT/M1-L01-S02_factory_request_v1.json" \
  --manifest "$ROOT/M1-L01-S02_factory_source_manifest_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator factory_request_bridge_failed

python3 - "$OUT/M1-L01-S01_content_semantics_v1.json" <<'PY' \
  >/dev/null 2>&1 || fail validator generated_contract_counts_failed
import json
import sys
from pathlib import Path

package = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "semantic_units": 13,
    "shot_intents": 26,
    "semantic_slots": 13,
    "shotir_source_inputs": 26,
}
for key, count in expected.items():
    if len(package[key]) != count:
        raise SystemExit(1)
if package["production_green_claimed"] is not False:
    raise SystemExit(1)
PY

if find "$ROOT" \
  -type f \( -iname '*.mp3' -o -iname '*.wav' -o -iname '*.mp4' -o -iname '*.mov' -o -iname '*.webm' -o -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) \
  | grep -q .; then
  fail policy binary_media_in_content_semantics_paths
fi

git show --check --oneline --no-renames HEAD >/dev/null 2>&1 \
  || fail validator diff_hygiene_failed

BUILDER_HASH="$(sha256sum "$ROOT/build_content_semantics.py" | awk '{print $1}')"
VALIDATOR_HASH="$(sha256sum "$ROOT/validate_content_semantics.py" | awk '{print $1}')"
POLICY_HASH="$(sha256sum "$ROOT/validate_policy_bindings.py" | awk '{print $1}')"
BRIDGE_HASH="$(sha256sum "$ROOT/validate_factory_request_bridge.py" | awk '{print $1}')"
AUDIO_MAPPING_HASH="$(sha256sum "$ROOT/validate_audio_authority_mapping.py" | awk '{print $1}')"
FACTORY_REQUEST_HASH="$(sha256sum "$ROOT/M1-L01-S02_factory_request_v1.json" | awk '{print $1}')"

cat <<EOF
gate_id=CONTENT_SEMANTICS_LAUNCH_GATE
private_sha=$PRIVATE_SHA
python_compile=PASS
deterministic_build=PASS
legacy_request_reproducibility=PASS
policy_bindings=PASS
audio_authority_mapping=PASS
content_semantics_validator=PASS
factory_request_bridge=PASS
factory_request_negative_self_tests=PASS
s01_semantic_units=13
s01_shot_intents=26
s01_semantic_slots=13
s01_shotir_inputs=26
s02_factory_semantic_units=12
s02_factory_shot_intents=12
binary_media_in_content_semantics_paths=false
diff_hygiene=PASS
sha256_builder=$BUILDER_HASH
sha256_content_validator=$VALIDATOR_HASH
sha256_policy_validator=$POLICY_HASH
sha256_factory_request_bridge=$BRIDGE_HASH
sha256_audio_authority_validator=$AUDIO_MAPPING_HASH
sha256_factory_request_file=$FACTORY_REQUEST_HASH
private_content_printed=false
artifact_policy=none
production_green_claimed=false
result=PASS
EOF
