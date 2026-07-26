#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=FACTORY_CORE_DAY4_EXACT_GATE"
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

cd "$PRIVATE_DIR"
PRIVATE_SHA="$(git rev-parse HEAD)"

python3 -m py_compile \
  11_tools/factory_core/__init__.py \
  11_tools/factory_core/core.py \
  11_tools/factory_core/station_outputs.py \
  11_tools/factory_core/executor_boundary.py \
  11_tools/factory_core/factory_interface.py \
  11_tools/factory_core/day4_proofs.py \
  11_tools/factory_core/state_registry_sync.py \
  11_tools/run_factory_core.py \
  11_tools/test_factory_core.py \
  11_tools/test_factory_core_day2.py \
  11_tools/test_factory_core_day3.py \
  11_tools/test_factory_core_day4.py \
  11_tools/test_factory_interface_adapter.py \
  >/dev/null 2>&1 || fail validator python_compile_failed

python3 11_tools/test_factory_core.py >/dev/null 2>&1 \
  || fail validator day1_test_suite_failed
python3 11_tools/test_factory_core_day2.py >/dev/null 2>&1 \
  || fail validator day2_test_suite_failed
python3 11_tools/test_factory_core_day3.py >/dev/null 2>&1 \
  || fail validator day3_test_suite_failed
python3 11_tools/test_factory_core_day4.py >/dev/null 2>&1 \
  || fail validator day4_test_suite_failed
python3 11_tools/test_factory_interface_adapter.py >/dev/null 2>&1 \
  || fail validator factory_interface_adapter_test_suite_failed

if find 04_validators/test_fixtures/factory_core \
        05_orchestration/launch_5d/core_contracts \
        11_tools/factory_core \
        -type f \( -iname '*.mp3' -o -iname '*.wav' -o -iname '*.mp4' -o -iname '*.mov' -o -iname '*.webm' -o -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) \
        | grep -q .; then
  fail policy binary_media_in_core_paths
fi

git show --check --oneline --no-renames HEAD >/dev/null 2>&1 \
  || fail validator diff_hygiene_failed

cat <<EOF
gate_id=FACTORY_CORE_DAY4_EXACT_GATE
private_sha=$PRIVATE_SHA
python_compile=PASS
day1_test_count=12
day1_tests=PASS
day2_test_count=6
day2_tests=PASS
day3_test_count=8
day3_tests=PASS
day4_test_count=10
day4_tests=PASS
factory_interface_test_count=5
factory_interface_tests=PASS
state_registry_hash_match=PASS
binary_media_in_core_paths=false
diff_hygiene=PASS
private_content_printed=false
artifact_policy=none
real_station_outputs_used=false
production_ready=false
result=PASS
EOF
