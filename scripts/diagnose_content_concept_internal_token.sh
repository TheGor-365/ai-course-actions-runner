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

python3 - "$OUT/M1-L01-S01_content_semantics_v1.json" "$ROOT/validate_content_semantics.py" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path

package_path = Path(sys.argv[1])
validator_path = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("content_validator", validator_path)
if spec is None or spec.loader is None:
    raise SystemExit("validator_import_failed")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
package = json.loads(package_path.read_text(encoding="utf-8"))

matches = []
for unit in package["semantic_units"]:
    match = module.INTERNAL_ID_RE.search(unit["concept"])
    if match:
        matches.append((unit["order"], match.group(0)))

if len(matches) != 1:
    print("result=FAIL")
    print("error_class=validator")
    print(f"error_code=concept_internal_token_match_count_{len(matches)}")
    print("private_content_printed=false")
    print("artifact_policy=none")
    raise SystemExit(1)

order, token = matches[0]
print("result=FAIL")
print("error_class=content_or_regex")
print(f"error_code=semantic_unit_{order}_concept_matches_{token}")
print("private_content_printed=false")
print("artifact_policy=none")
raise SystemExit(1)
PY
