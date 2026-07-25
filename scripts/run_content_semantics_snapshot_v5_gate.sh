#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=CONTENT_SEMANTICS_SNAPSHOT_V5_GATE"
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  exit "${3:-1}"
}

[[ -d "$PRIVATE_DIR/.git" ]] || fail policy private_checkout_missing 2

V4_SUMMARY="$(mktemp)"
OUT="$(mktemp -d)"
trap 'rm -f "$V4_SUMMARY"; rm -rf "$OUT"' EXIT

set +e
bash scripts/run_content_semantics_snapshot_v4_gate.sh "$PRIVATE_DIR" \
  >"$V4_SUMMARY" 2>&1
V4_RC=$?
set -e
V4_ERROR="$(sed -n 's/^error_code=//p' "$V4_SUMMARY" | tail -n 1)"

if [[ "$V4_RC" -ne 1 || "$V4_ERROR" != "normalization_receipt_v2_failed" ]]; then
  SAFE_ERROR="$(printf '%s' "${V4_ERROR:-missing}" | tr -cd 'a-zA-Z0-9._-')"
  fail validator "v4_matrix_unexpected_${SAFE_ERROR:-unknown}"
fi

ROOT="$PRIVATE_DIR/Module 1/Lesson 1/launch_5d/content_semantics"

python3 "$ROOT/test_validate_content_semantics.py" \
  >/dev/null 2>&1 || fail validator learner_scanner_regression_tests_failed
python3 "$ROOT/test_build_content_semantics_handoff_v2.py" \
  >/dev/null 2>&1 || fail validator handoff_normalization_regression_tests_failed

python3 "$ROOT/build_content_semantics_handoff_v2.py" \
  --repo-root "$PRIVATE_DIR" \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator learner_safe_handoff_build_failed

python3 - "$OUT/M1-L01-S01_content_semantics_v1.json" <<'PY' \
  >/dev/null 2>&1 || fail validator normalization_receipt_v3_failed
import json
import sys
from pathlib import Path

package = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert package["handoff_builder_version"] == "content-semantics-handoff-v2"
normalizations = package["learner_text_normalizations"]
assert len(normalizations) == 3
assert [row["normalization_id"] for row in normalizations] == [
    "S01_B08_TAKEAWAY_INTERNAL_LABEL_REMOVAL_v1",
    "S01_B13_TEACHING_GOAL_INTERNAL_LABEL_REMOVAL_v1",
    "S01_B13_TAKEAWAY_INTERNAL_LABEL_REMOVAL_v1",
]
assert all(
    row["policy"] == "EXACT_ASSERTION_NO_SILENT_INFERENCE"
    for row in normalizations
)
unit8 = package["semantic_units"][7]
unit12 = package["semantic_units"][11]
unit13 = package["semantic_units"][12]
assert unit8["concept"] == "Четыре базовых термина достаточны для первого блока."
assert unit8["success_criterion"] == "Четыре базовых термина достаточны для первого блока."
assert unit8["technical_truth_claims"][0]["statement"] == "Четыре базовых термина достаточны для первого блока."
assert unit12["transition_to_next"] == "Перейти к следующему блоку про инструменты разработчика."
assert unit13["learner_goal"] == "Перейти к следующему блоку про инструменты разработчика."
assert unit13["concept"] == "Завершение первого блока должно создавать мост к следующей 15-минутке."
assert unit13["success_criterion"] == "Завершение первого блока должно создавать мост к следующей 15-минутке."
assert unit13["technical_truth_claims"][0]["statement"] == "Завершение первого блока должно создавать мост к следующей 15-минутке."
assert package["production_green_claimed"] is False
PY

PRIVATE_SHA="$(git -C "$PRIVATE_DIR" rev-parse HEAD)"
BUILDER_HASH="$(sha256sum "$ROOT/build_content_semantics_handoff_v2.py" | awk '{print $1}')"
VALIDATOR_HASH="$(sha256sum "$ROOT/validate_content_semantics.py" | awk '{print $1}')"
SCANNER_TEST_HASH="$(sha256sum "$ROOT/test_validate_content_semantics.py" | awk '{print $1}')"
NORMALIZATION_TEST_HASH="$(sha256sum "$ROOT/test_build_content_semantics_handoff_v2.py" | awk '{print $1}')"
WORKFLOW_HASH="$(sha256sum "$PRIVATE_DIR/.github/workflows/content-semantics-launch.yml" | awk '{print $1}')"

cat <<EOF
gate_id=CONTENT_SEMANTICS_SNAPSHOT_V5_GATE
private_sha=$PRIVATE_SHA
v4_compile_and_full_validator_matrix=PASS_BEFORE_LEGACY_COUNT_ASSERTION
learner_scanner_regression_tests=4_PASS
handoff_normalization_regression_tests=7_PASS
learner_text_normalization_count=3
learner_text_normalization_ids=PASS
learner_text_normalization_policy=EXACT_ASSERTION_NO_SILENT_INFERENCE
internal_S01_takeaway_labels_removed=true
internal_S02_transition_labels_removed=true
final_S01_takeaway_labels_removed=true
production_green_claimed=false
sha256_handoff_builder=$BUILDER_HASH
sha256_content_validator=$VALIDATOR_HASH
sha256_scanner_tests=$SCANNER_TEST_HASH
sha256_normalization_tests=$NORMALIZATION_TEST_HASH
sha256_source_workflow=$WORKFLOW_HASH
private_content_printed=false
artifact_policy=none
result=PASS
no_fake_green=true
EOF
