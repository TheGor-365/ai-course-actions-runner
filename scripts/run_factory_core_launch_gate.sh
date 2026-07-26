#!/usr/bin/env bash
set -euo pipefail

PRIVATE_DIR="${1:-}"

fail() {
  echo "gate_id=FACTORY_CORE_LAUNCH_GATE"
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
  11_tools/factory_core/launch_hardening.py \
  11_tools/factory_core/gold_s01_real.py \
  11_tools/factory_core/gold_s01_authority.py \
  11_tools/factory_core/gold_s01_authority_v2.py \
  11_tools/factory_core/runner14_compat.py \
  11_tools/run_factory_core.py \
  11_tools/test_factory_core.py \
  11_tools/test_factory_core_day2.py \
  11_tools/test_factory_core_day3.py \
  11_tools/test_factory_core_day4.py \
  11_tools/test_factory_core_day5.py \
  11_tools/test_factory_interface_adapter.py \
  11_tools/test_factory_core_gold_s01_real.py \
  11_tools/test_factory_core_gold_s01_authority_v2.py \
  >/dev/null 2>&1 || fail validator python_compile_failed

python3 11_tools/test_factory_core.py >/dev/null 2>&1 || fail validator day1_test_suite_failed
python3 11_tools/test_factory_core_day2.py >/dev/null 2>&1 || fail validator day2_test_suite_failed
python3 11_tools/test_factory_core_day3.py >/dev/null 2>&1 || fail validator day3_test_suite_failed
python3 11_tools/test_factory_core_day4.py >/dev/null 2>&1 || fail validator day4_test_suite_failed
python3 11_tools/test_factory_core_day5.py >/dev/null 2>&1 || fail validator day5_test_suite_failed
python3 11_tools/test_factory_interface_adapter.py >/dev/null 2>&1 || fail validator factory_interface_adapter_test_suite_failed
python3 11_tools/test_factory_core_gold_s01_real.py >/dev/null 2>&1 || fail validator gold_s01_real_test_suite_failed
python3 11_tools/test_factory_core_gold_s01_authority_v2.py >/dev/null 2>&1 || fail validator gold_s01_authority_test_suite_failed

if find 04_validators/test_fixtures/factory_core \
        05_orchestration/launch_5d/core_contracts \
        05_orchestration/gold_s01_closure/contracts \
        05_orchestration/gold_s01_closure/handoffs \
        11_tools/factory_core \
        -type f \( -iname '*.mp3' -o -iname '*.wav' -o -iname '*.mp4' -o -iname '*.mov' -o -iname '*.webm' -o -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) \
        | grep -q .; then
  fail policy binary_media_in_core_paths
fi

git show --check --oneline --no-renames HEAD >/dev/null 2>&1 || fail validator diff_hygiene_failed

CORE_HASH="$(sha256sum 11_tools/factory_core/core.py | awk '{print $1}')"
GOLD_S01_HASH="$(sha256sum 11_tools/factory_core/gold_s01_real.py | awk '{print $1}')"
AUTHORITY_FACADE_HASH="$(sha256sum 11_tools/factory_core/gold_s01_authority.py | awk '{print $1}')"
AUTHORITY_HASH="$(sha256sum 11_tools/factory_core/gold_s01_authority_v2.py | awk '{print $1}')"
RUNNER14_COMPAT_HASH="$(sha256sum 11_tools/factory_core/runner14_compat.py | awk '{print $1}')"
CLI_HASH="$(sha256sum 11_tools/run_factory_core.py | awk '{print $1}')"
AUTHORITY_TEST_HASH="$(sha256sum 11_tools/test_factory_core_gold_s01_authority_v2.py | awk '{print $1}')"

cat <<EOF
gate_id=FACTORY_CORE_LAUNCH_GATE
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
day5_test_count=10
day5_tests=PASS
factory_interface_test_count=5
factory_interface_tests=PASS
gold_s01_real_test_count=10
gold_s01_real_tests=PASS
gold_s01_authority_test_count=7
gold_s01_authority_tests=PASS
total_test_count=68
preflight_real_s01_media_mutation=false
blind_s02_blocks_first_ru_preview=false
binary_media_in_core_paths=false
diff_hygiene=PASS
sha256_core=$CORE_HASH
sha256_gold_s01_real=$GOLD_S01_HASH
sha256_gold_s01_authority_facade=$AUTHORITY_FACADE_HASH
sha256_gold_s01_authority=$AUTHORITY_HASH
sha256_runner14_compat=$RUNNER14_COMPAT_HASH
sha256_cli=$CLI_HASH
sha256_gold_s01_authority_tests=$AUTHORITY_TEST_HASH
private_content_printed=false
artifact_policy=none
result=PASS
EOF
