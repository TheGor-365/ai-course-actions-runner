#!/usr/bin/env bash
set -euo pipefail

PRODUCTION_DIR="${1:-}"
SOURCE_DIR="${2:-}"
SOURCE_REQUEST_PATH="${3:-}"
EXPECTED_EXTERNAL_HASH="${4:-}"
EXPECTED_INTERNAL_REQUEST_ID="${5:-}"
EXPECTED_INTERNAL_HASH="${6:-}"
EXPECTED_RECEIPT_HASH="${7:-}"

fail() {
  echo "gate_id=S02_FACTORY_ADAPTER_EXECUTION_GATE"
  echo "result=FAIL"
  echo "error_class=$1"
  echo "error_code=$2"
  echo "private_content_printed=false"
  echo "artifact_policy=none"
  echo "real_media_execution=false"
  exit "${3:-1}"
}

[[ -d "$PRODUCTION_DIR/.git" ]] || fail policy production_checkout_missing 2
[[ -d "$SOURCE_DIR/.git" ]] || fail policy source_checkout_missing 2
[[ -n "$SOURCE_REQUEST_PATH" ]] || fail policy source_request_path_missing 2
[[ "$SOURCE_REQUEST_PATH" != /* ]] || fail policy source_request_path_must_be_repository_relative 2

REQUEST_FILE="$SOURCE_DIR/$SOURCE_REQUEST_PATH"
[[ -f "$REQUEST_FILE" ]] || fail policy source_request_missing 2

OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
RUNTIME_A="$OUT/runtime-a"
RUNTIME_B="$OUT/runtime-b"

python3 -m py_compile \
  "$PRODUCTION_DIR/11_tools/factory_core/core.py" \
  "$PRODUCTION_DIR/11_tools/factory_core/factory_interface.py" \
  "$PRODUCTION_DIR/11_tools/run_factory_core.py" \
  >/dev/null 2>&1 || fail validator python_compile_failed

run_once() {
  local runtime_dir="$1"
  local stdout_file="$2"
  python3 "$PRODUCTION_DIR/11_tools/run_factory_core.py" \
    --repo-root "$PRODUCTION_DIR" \
    --request "$REQUEST_FILE" \
    --runtime-dir "$runtime_dir" \
    >"$stdout_file" 2>"$runtime_dir.stderr" \
    || fail execution one_command_execution_failed
}

run_once "$RUNTIME_A" "$OUT/run-a.json"
run_once "$RUNTIME_B" "$OUT/run-b.json"

python3 - \
  "$RUNTIME_A/factory_run_summary.json" \
  "$RUNTIME_A/factory_interface_adapter_receipt.json" \
  "$RUNTIME_B/factory_run_summary.json" \
  "$RUNTIME_B/factory_interface_adapter_receipt.json" \
  "$EXPECTED_EXTERNAL_HASH" \
  "$EXPECTED_INTERNAL_REQUEST_ID" \
  "$EXPECTED_INTERNAL_HASH" \
  "$EXPECTED_RECEIPT_HASH" <<'PY' \
  >/dev/null 2>&1 || fail validator adapter_execution_evidence_mismatch
import json
import sys
from pathlib import Path

summary_a = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
receipt_a = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
summary_b = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
receipt_b = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
external_hash, request_id, internal_hash, receipt_hash = sys.argv[5:9]

for summary in (summary_a, summary_b):
    assert summary["result"] == "PASS"
    assert summary["current_state"] == "READY_FOR_RENDER"
    assert summary["external_contract_version"] == "factory-interface-v1"
    assert summary["package_request_sha256"] == external_hash
    assert summary["factory_interface_adapter"]["internal_request_id"] == request_id
    assert summary["factory_interface_adapter"]["internal_content_hash"] == internal_hash
    assert summary["factory_interface_adapter"]["adapter_receipt_sha256"] == receipt_hash
    assert summary["factory_interface_adapter"]["mapping_status"] == "PASS"
    assert summary["factory_interface_adapter"]["no_silent_inference"] is True
    assert summary["factory_interface_adapter"]["no_fake_green"] is True
    assert summary.get("private_media_executed", False) is False
    assert summary.get("production_ready", False) is False

for receipt in (receipt_a, receipt_b):
    assert receipt["contract_version"] == "factory-interface-v1"
    assert receipt["adapter_version"] == "factory-interface-adapter-v1"
    assert receipt["package_request_sha256"] == external_hash
    assert receipt["internal_request_id"] == request_id
    assert receipt["internal_content_hash"] == internal_hash
    assert receipt["adapter_receipt_sha256"] == receipt_hash
    assert receipt["mapping_status"] == "PASS"
    assert receipt["no_silent_inference"] is True
    assert receipt["no_fake_green"] is True

assert receipt_a == receipt_b
stable_fields = (
    "result",
    "current_state",
    "external_contract_version",
    "external_request_id",
    "package_request_sha256",
    "completed_station_ids",
    "last_green_station",
    "artifact_count",
)
assert {key: summary_a.get(key) for key in stable_fields} == {
    key: summary_b.get(key) for key in stable_fields
}
PY

PRODUCTION_SHA="$(git -C "$PRODUCTION_DIR" rev-parse HEAD)"
SOURCE_SHA="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
CLI_HASH="$(sha256sum "$PRODUCTION_DIR/11_tools/run_factory_core.py" | awk '{print $1}')"
ADAPTER_HASH="$(sha256sum "$PRODUCTION_DIR/11_tools/factory_core/factory_interface.py" | awk '{print $1}')"
REQUEST_FILE_HASH="$(sha256sum "$REQUEST_FILE" | awk '{print $1}')"

cat <<EOF
gate_id=S02_FACTORY_ADAPTER_EXECUTION_GATE
production_sha=$PRODUCTION_SHA
source_sha=$SOURCE_SHA
one_command_execution=PASS
repeat_execution=PASS
deterministic_adapter_receipt=PASS
external_request_sha256=$EXPECTED_EXTERNAL_HASH
internal_request_id=$EXPECTED_INTERNAL_REQUEST_ID
internal_content_hash=$EXPECTED_INTERNAL_HASH
adapter_receipt_sha256=$EXPECTED_RECEIPT_HASH
terminal_state=READY_FOR_RENDER
real_station_outputs_used=false
real_media_execution=false
production_ready=false
production_green_claimed=false
sha256_factory_cli=$CLI_HASH
sha256_factory_adapter=$ADAPTER_HASH
sha256_source_request_file=$REQUEST_FILE_HASH
private_content_printed=false
artifact_policy=none
result=PASS
no_fake_green=true
EOF
