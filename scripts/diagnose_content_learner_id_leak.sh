#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit "${3:-1}"
}

[[ -d "$PRIVATE_DIR/.git" ]] || fail policy private_checkout_missing 2

cd "$PRIVATE_DIR"
ROOT="Module 1/Lesson 1/launch_5d/content_semantics"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT

python3 "$ROOT/build_content_semantics.py" \
  --repo-root . \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator deterministic_build_failed

LOG="$OUT/validator.log"
set +e
python3 "$ROOT/validate_content_semantics.py" \
  --package "$OUT/M1-L01-S01_content_semantics_v1.json" \
  --request "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  --attestation "$ROOT/connector_preflight_attestation_v1.json" \
  >"$LOG" 2>&1
RC=$?
set -e

if [[ "$RC" -eq 0 ]]; then
  echo "result=PASS"
  echo "error_class=none"
  echo "error_code=none"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit 0
fi

FAILURE="$(sed -n 's/^FAILURE=//p' "$LOG" | tail -n 1)"
[[ -n "$FAILURE" ]] || fail validator validator_failed_without_failure_record

if [[ "$FAILURE" != learner-facing\ internal\ ID\ leak\ at\ * ]]; then
  DIGEST="$(printf '%s' "$FAILURE" | sha256sum | awk '{print substr($1,1,12)}')"
  fail validator "unexpected_failure_${DIGEST}"
fi

PATH_VALUE="${FAILURE#learner-facing internal ID leak at }"
PATH_VALUE="${PATH_VALUE%%: *}"
SAFE_PATH="$(python3 - "$PATH_VALUE" <<'PY'
import re
import sys

path = sys.argv[1]
path = re.sub(r"S01-SU-\d+", "semantic_unit", path)
path = re.sub(r"S01-SHOT-[A-Za-z0-9]+", "shot_intent", path)
path = re.sub(r"S01-PH-\d+", "phrase", path)
path = re.sub(r"\[\d+\]", "_item", path)
path = re.sub(r"[^A-Za-z0-9_.-]+", "_", path)
print(path.lower().strip("_.-")[:120])
PY
)"
[[ -n "$SAFE_PATH" ]] || SAFE_PATH=unknown_field

fail validator "learner_text_internal_id_leak_at_${SAFE_PATH}"
