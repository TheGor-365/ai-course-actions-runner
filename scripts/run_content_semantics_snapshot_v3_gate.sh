#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=CONTENT_SEMANTICS_SNAPSHOT_V3_GATE"
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit "${3:-1}"
}

[[ -d "$PRIVATE_DIR/.git" ]] || fail policy private_checkout_missing 2

cd "$PRIVATE_DIR"
PRIVATE_SHA="$(git rev-parse HEAD)"
ROOT="Module 1/Lesson 1/launch_5d/content_semantics"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

python3 -m py_compile \
  "$ROOT/build_content_semantics.py" \
  "$ROOT/build_content_semantics_handoff_v2.py" \
  "$ROOT/build_ru_caption_source.py" \
  "$ROOT/validate_content_semantics.py" \
  "$ROOT/validate_policy_bindings.py" \
  "$ROOT/validate_factory_request_bridge.py" \
  "$ROOT/validate_audio_authority_mapping.py" \
  "$ROOT/validate_factory_core_reconciliation.py" \
  "$ROOT/validate_shotir_freeze_reconciliation.py" \
  "$ROOT/validate_ru_caption_source.py" \
  "$ROOT/test_validate_content_semantics.py" \
  "$ROOT/test_build_content_semantics_handoff_v2.py" \
  >/dev/null 2>&1 || fail validator python_compile_failed

python3 "$ROOT/test_validate_content_semantics.py" \
  >/dev/null 2>&1 || fail validator learner_scanner_regression_tests_failed
python3 "$ROOT/test_build_content_semantics_handoff_v2.py" \
  >/dev/null 2>&1 || fail validator handoff_normalization_regression_tests_failed

python3 "$ROOT/build_content_semantics_handoff_v2.py" \
  --repo-root . \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator learner_safe_handoff_build_failed
python3 "$ROOT/build_ru_caption_source.py" \
  --repo-root . \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator ru_caption_source_build_failed

cmp \
  "$ROOT/M1-L01-S02_immutable_blind_request_v1.json" \
  "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  >/dev/null 2>&1 || fail validator immutable_request_reproducibility_failed

python3 "$ROOT/validate_policy_bindings.py" \
  --repo-root . \
  --request "$ROOT/M1-L01-S02_immutable_blind_request_v1.json" \
  >/dev/null 2>&1 || fail validator policy_bindings_failed

python3 "$ROOT/validate_audio_authority_mapping.py" \
  --mapping "$ROOT/S01_audio_authority_mapping_v1.json" \
  --attestation "$ROOT/audio_authority_connector_attestation_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator audio_authority_mapping_failed

python3 "$ROOT/validate_shotir_freeze_reconciliation.py" \
  --reconciliation "$ROOT/shotir_freeze_reconciliation_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator shotir_freeze_reconciliation_failed

python3 "$ROOT/validate_ru_caption_source.py" \
  --caption-source "$OUT/M1-L01-S01_ru_caption_source_v1.json" \
  --canonical-source "Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/02_voiceover/voiceover_segments_ru.json" \
  --audio-mapping "$ROOT/S01_audio_authority_mapping_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator ru_caption_source_validation_failed

VALIDATOR_LOG="$OUT/content_semantics_validator.log"
if ! python3 "$ROOT/validate_content_semantics.py" \
  --package "$OUT/M1-L01-S01_content_semantics_v1.json" \
  --request "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  --attestation "$ROOT/connector_preflight_attestation_v1.json" \
  >"$VALIDATOR_LOG" 2>&1; then
  FAILURE="$(sed -n 's/^FAILURE=//p' "$VALIDATOR_LOG" | tail -n 1)"
  DIGEST="$(printf '%s' "${FAILURE:-missing}" | sha256sum | awk '{print substr($1,1,12)}')"
  fail validator "content_semantics_validation_failed_${DIGEST}"
fi

python3 "$ROOT/validate_factory_request_bridge.py" \
  --repo-root . \
  --request "$ROOT/M1-L01-S02_factory_request_v1.json" \
  --manifest "$ROOT/M1-L01-S02_factory_source_manifest_v1.json" \
  --content-request "$ROOT/M1-L01-S02_immutable_blind_request_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator factory_request_bridge_failed

python3 "$ROOT/validate_factory_core_reconciliation.py" \
  --request "$ROOT/M1-L01-S02_factory_request_v1.json" \
  --reconciliation "$ROOT/factory_core_reconciliation_v1.json" \
  --self-test \
  >/dev/null 2>&1 || fail validator factory_core_reconciliation_failed

python3 - \
  "$OUT/M1-L01-S01_content_semantics_v1.json" \
  "$OUT/M1-L01-S01_ru_caption_source_v1.json" <<'PY' \
  >/dev/null 2>&1 || fail validator generated_contract_or_normalization_receipt_failed
import json
import sys
from pathlib import Path

package = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
captions = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
expected = {
    "semantic_units": 13,
    "shot_intents": 26,
    "semantic_slots": 13,
    "shotir_source_inputs": 26,
}
for key, count in expected.items():
    assert len(package[key]) == count
assert package["handoff_builder_version"] == "content-semantics-handoff-v2"
normalizations = package["learner_text_normalizations"]
assert len(normalizations) == 1
assert normalizations[0]["normalization_id"] == "S01_B08_TAKEAWAY_INTERNAL_LABEL_REMOVAL_v1"
assert normalizations[0]["policy"] == "EXACT_ASSERTION_NO_SILENT_INFERENCE"
assert len(captions["caption_blocks"]) == 13
assert package["production_green_claimed"] is False
assert captions["production_green_claimed"] is False
PY

if find "$ROOT" \
  -type f \( -iname '*.mp3' -o -iname '*.wav' -o -iname '*.mp4' -o -iname '*.mov' -o -iname '*.webm' -o -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) \
  | grep -q .; then
  fail policy binary_media_in_content_semantics_paths
fi

git show --check --oneline --no-renames HEAD \
  >/dev/null 2>&1 || fail validator diff_hygiene_failed

HANDOFF_BUILDER_HASH="$(sha256sum "$ROOT/build_content_semantics_handoff_v2.py" | awk '{print $1}')"
CONTENT_VALIDATOR_HASH="$(sha256sum "$ROOT/validate_content_semantics.py" | awk '{print $1}')"
SCANNER_TEST_HASH="$(sha256sum "$ROOT/test_validate_content_semantics.py" | awk '{print $1}')"
NORMALIZATION_TEST_HASH="$(sha256sum "$ROOT/test_build_content_semantics_handoff_v2.py" | awk '{print $1}')"
FACTORY_REQUEST_HASH="$(sha256sum "$ROOT/M1-L01-S02_factory_request_v1.json" | awk '{print $1}')"

cat <<EOF
gate_id=CONTENT_SEMANTICS_SNAPSHOT_V3_GATE
private_sha=$PRIVATE_SHA
python_compile=PASS
learner_scanner_regression_tests=4_PASS
handoff_normalization_regression_tests=4_PASS
learner_safe_handoff_build=PASS
immutable_request_reproducibility=PASS
policy_bindings=PASS
audio_authority_mapping=PASS
shotir_freeze_reconciliation=PASS
ru_caption_source_validation=PASS
content_semantics_validator=PASS
factory_request_bridge=PASS
factory_core_reconciliation=PASS
s01_semantic_units=13
s01_shot_intents=26
s01_semantic_slots=13
s01_shotir_inputs=26
ru_caption_blocks=13
learner_text_normalization_count=1
learner_text_normalization_policy=EXACT_ASSERTION_NO_SILENT_INFERENCE
binary_media_in_content_semantics_paths=false
diff_hygiene=PASS
sha256_handoff_builder=$HANDOFF_BUILDER_HASH
sha256_content_validator=$CONTENT_VALIDATOR_HASH
sha256_scanner_tests=$SCANNER_TEST_HASH
sha256_normalization_tests=$NORMALIZATION_TEST_HASH
sha256_factory_request_file=$FACTORY_REQUEST_HASH
private_content_printed=false
artifact_policy=none
production_green_claimed=false
result=PASS
no_fake_green=true
EOF
