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

python3 "$ROOT/build_content_semantics_handoff_v2.py" \
  --repo-root . \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator learner_safe_handoff_build_failed

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

python3 - "$FAILURE" <<'PY'
import hashlib
import re
import sys

message = sys.argv[1]
code = None

if message.startswith("learner-facing internal ID leak at "):
    rest = message.removeprefix("learner-facing internal ID leak at ")
    path, _, value = rest.partition(": ")
    token_match = re.search(
        r"(?:\bS0[12]\b|\bM1-L01\b|\bVO_\d+\b|\bB\d{2}_[A-Z0-9_]+\b|"
        r"\bVE_\d+\b|\bS01-(?:SU|SHOT|SLOT)-\w+\b)",
        value,
    )
    path = re.sub(r"S01-SU-\d+", "semantic_unit", path)
    path = re.sub(r"S01-SHOT-[A-Za-z0-9]+", "shot_intent", path)
    path = re.sub(r"S01-PH-\d+", "phrase", path)
    path = re.sub(r"\[\d+\]", "_item", path)
    path = re.sub(r"[^A-Za-z0-9_.-]+", "_", path).lower().strip("_.-")
    token = token_match.group(0) if token_match else "unknown_token"
    code = f"learner_id_leak_at_{path}_token_{token}"
elif message.startswith("unresolved placeholder token at "):
    path = message.removeprefix("unresolved placeholder token at ").split(": ", 1)[0]
    path = re.sub(r"\[\d+\]", "_item", path)
    path = re.sub(r"[^A-Za-z0-9_.-]+", "_", path).lower().strip("_.-")
    code = f"placeholder_at_{path}"
else:
    mappings = [
        ("source pointer not connector-attested", "source_pointer_not_attested"),
        ("source hash drift", "source_blob_hash_drift"),
        ("immutable request hash drift", "immutable_request_hash_drift"),
        ("semantic unit count mismatch", "semantic_unit_count_mismatch"),
        ("shot intent count mismatch", "shot_intent_count_mismatch"),
        ("semantic slot count mismatch", "semantic_slot_count_mismatch"),
        ("ShotIR source input count mismatch", "shotir_input_count_mismatch"),
        ("existing 24 visual events are not fully preserved", "visual_event_coverage_mismatch"),
        ("existing visual event mapped more than once", "duplicate_visual_event_mapping"),
        ("technical truth", "technical_truth_contract_failure"),
        ("fabricated measured", "fabricated_measured_timing"),
        ("invalid duration bounds", "invalid_duration_bounds"),
        ("missing fields", "required_field_missing"),
        ("empty required field", "required_field_empty"),
    ]
    for needle, mapped in mappings:
        if needle in message:
            code = mapped
            break

if code is None:
    shape = re.sub(r"(['\"]).*?\1", " quoted ", message)
    shape = re.sub(r"\b[0-9a-fA-F]{32,64}\b", " hash ", shape)
    shape = re.sub(r"\b\d+\b", " n ", shape)
    shape = re.sub(r"[^A-Za-z]+", "_", shape).lower().strip("_")[:96]
    digest = hashlib.sha256(message.encode()).hexdigest()[:8]
    code = f"unclassified_{shape or 'empty'}_{digest}"

safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", code)[:180]
print("result=FAIL")
print("error_class=validator")
print(f"error_code={safe}")
print("private_content_printed=false")
print("artifact_policy=none")
raise SystemExit(1)
PY
