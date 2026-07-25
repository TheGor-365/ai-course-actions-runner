#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=CONTENT_SEMANTIC_EQUIVALENCE_GATE"
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit "${3:-1}"
}

[[ -d "$PRIVATE_DIR/.git" ]] || fail policy private_checkout_missing 2

ROOT="$PRIVATE_DIR/Module 1/Lesson 1/launch_5d/content_semantics"
VOICEOVER="$PRIVATE_DIR/Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/02_voiceover/voiceover_segments_ru.json"
SOURCE="$ROOT/S01_semantic_equivalence_source_v1.json"
GLOSSARY="$ROOT/locale_neutral_glossary_v1.json"

python3 -m py_compile "$ROOT/validate_semantic_equivalence_source.py" \
  >/dev/null 2>&1 || fail validator python_compile_failed

RESULT_FILE="$(mktemp)"
trap 'rm -f "$RESULT_FILE"' EXIT
python3 "$ROOT/validate_semantic_equivalence_source.py" \
  --source "$SOURCE" \
  --voiceover "$VOICEOVER" \
  --glossary "$GLOSSARY" \
  --self-test \
  >"$RESULT_FILE" 2>&1 || fail validator semantic_equivalence_validation_failed

python3 - "$RESULT_FILE" <<'PY' \
  >/dev/null 2>&1 || fail validator semantic_equivalence_result_mismatch
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert result["SEMANTIC_EQUIVALENCE_SOURCE"] == "PASS"
assert result["SLOT_COVERAGE"] == "13/13"
assert result["TARGET_LOCALES"] == "RU_DE_JA"
assert result["SOURCE_PHRASE_BINDINGS"] == "13/13"
assert result["GLOSSARY_CONCEPT_BINDINGS"] == "PASS"
assert result["IMMUTABLE_TOKEN_BINDINGS"] == "PASS"
assert result["CONTENT_HASH"] == "PASS"
assert result["NEGATIVE_SELF_TESTS"] == "4/4_PASS"
assert result["FINAL_LOCALE_FIT_CLAIMED"] is False
assert result["PRODUCTION_GREEN_CLAIMED"] is False
assert result["NO_FAKE_GREEN"] is True
PY

PRIVATE_SHA="$(git -C "$PRIVATE_DIR" rev-parse HEAD)"
SOURCE_HASH="$(sha256sum "$SOURCE" | awk '{print $1}')"
VALIDATOR_HASH="$(sha256sum "$ROOT/validate_semantic_equivalence_source.py" | awk '{print $1}')"
WORKFLOW_HASH="$(sha256sum "$PRIVATE_DIR/.github/workflows/content-semantics-launch.yml" | awk '{print $1}')"

cat <<EOF
gate_id=CONTENT_SEMANTIC_EQUIVALENCE_GATE
private_sha=$PRIVATE_SHA
semantic_equivalence_source=PASS
slot_coverage=13/13
target_locales=RU_DE_JA
source_phrase_bindings=13/13
glossary_concept_bindings=PASS
immutable_token_bindings=PASS
content_hash=PASS
negative_self_tests=4/4_PASS
final_locale_fit_claimed=false
production_green_claimed=false
sha256_equivalence_source_file=$SOURCE_HASH
sha256_equivalence_validator=$VALIDATOR_HASH
sha256_source_workflow=$WORKFLOW_HASH
private_content_printed=false
artifact_policy=none
result=PASS
no_fake_green=true
EOF
