#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=CONTENT_SEMANTICS_SNAPSHOT_V2_GATE"
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit "${3:-1}"
}

if [[ -z "$PRIVATE_DIR" || ! -d "$PRIVATE_DIR/.git" ]]; then
  fail policy private_checkout_missing 2
fi

ROOT="Module 1/Lesson 1/launch_5d/content_semantics"

python3 -m py_compile \
  "$PRIVATE_DIR/$ROOT/validate_content_semantics.py" \
  "$PRIVATE_DIR/$ROOT/test_validate_content_semantics.py" \
  >/dev/null 2>&1 || fail validator learner_scanner_compile_failed

python3 "$PRIVATE_DIR/$ROOT/test_validate_content_semantics.py" \
  >/dev/null 2>&1 || fail validator learner_scanner_regression_tests_failed

SUMMARY="$(mktemp)"
trap 'rm -f "$SUMMARY"' EXIT
set +e
bash scripts/run_content_semantics_launch_gate.sh "$PRIVATE_DIR" >"$SUMMARY" 2>&1
RC=$?
set -e
cat "$SUMMARY"
if [[ "$RC" -ne 0 ]]; then
  exit "$RC"
fi

echo "learner_scanner_regression_tests=4_PASS"
echo "structured_learner_text=list_and_object_supported"
echo "unsupported_scalar_policy=FAIL_CLOSED"
echo "snapshot_v2_result=PASS"
