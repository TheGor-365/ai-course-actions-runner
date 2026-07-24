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
  "$ROOT/validate_factory_request_bridge.py" \
  >/dev/null 2>&1 || fail validator python_compile_failed

python3 "$ROOT/build_content_semantics.py" \
  --repo-root . \
  --out-dir "$OUT" \
  >/dev/null 2>&1 || fail validator deterministic_build_failed

cmp \
  "$ROOT/M1-L01-S02_immutable_blind_request_v1.json" \
  "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  >/dev/null 2>&1 || fail validator legacy_request_reproducibility_failed

python3 "$ROOT/validate_content_semantics.py" \
  --package "$OUT/M1-L01-S01_content_semantics_v1.json" \
  --request "$OUT/M1-L01-S02_immutable_blind_request_v1.json" \
  --attestation "$ROOT/connector_preflight_attestation_v1.json" \
  >/dev/null 2>&1 || fail validator content_semantics_validation_failed

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
BRIDGE_HASH="$(sha256sum "$ROOT/validate_factory_request_bridge.py" | awk '{print $1}')"
FACTORY_REQUEST_HASH="$(sha256sum "$ROOT/M1-L01-S02_factory_request_v1.json" | awk '{print $1}')"

cat <<EOF
gate_id=CONTENT_SEMANTICS_LAUNCH_GATE
private_sha=$PRIVATE_SHA
python_compile=PASS
deterministic_build=PASS
legacy_request_reproducibility=PASS
content_semantics_validator=PASS
factory_request_bridge=PASS
factory_request_negative_self_tests=4_PASS
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
sha256_factory_request_bridge=$BRIDGE_HASH
sha256_factory_request_file=$FACTORY_REQUEST_HASH
private_content_printed=false
artifact_policy=none
production_green_claimed=false
result=PASS
EOF
