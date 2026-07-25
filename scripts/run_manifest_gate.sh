#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE_ID="${1:-}"
PRIVATE_DIR="${2:-}"
PRIVATE_REPO="${3:-}"

fail() {
  echo "result=FAIL"
  echo "error_class=policy"
  echo "error_code=$1"
  echo "private_content_public_exposure=false"
  echo "artifacts_created=false"
  exit "${2:-2}"
}

[[ -n "$GATE_ID" && -n "$PRIVATE_DIR" && -n "$PRIVATE_REPO" ]] || fail missing_required_arguments

PROFILE_ID="$(python3 "$ROOT/scripts/runner_infrastructure_v1.py" resolve-gate "$GATE_ID" "$PRIVATE_REPO" --field profile_id)" || fail gate_manifest_rejected
SCHEMA_FILE="$(python3 "$ROOT/scripts/runner_infrastructure_v1.py" resolve-gate "$GATE_ID" "$PRIVATE_REPO" --field output_schema_file)" || fail gate_schema_rejected
SCHEMA_HASH="$(sha256sum "$ROOT/$SCHEMA_FILE" | awk '{print $1}')"

set +e
case "$GATE_ID" in
  FACTORY_LAUNCH_CONTROL_PLANE_GATE)
    python3 "$ROOT/scripts/runner_infrastructure_v1.py" run-launch-gate --private-dir "$PRIVATE_DIR"
    RC=$?
    ;;
  CONTENT_SEMANTICS_LAUNCH_GATE)
    python3 "$ROOT/scripts/content_semantics_gate_v1.py" --private-dir "$PRIVATE_DIR"
    RC=$?
    ;;
  *)
    bash "$ROOT/scripts/run_allowlisted_validator.sh" "$GATE_ID" "$PRIVATE_DIR"
    RC=$?
    ;;
esac
set -e

echo "profile_id=$PROFILE_ID"
echo "output_schema_hash=$SCHEMA_HASH"
echo "private_content_public_exposure=false"
echo "artifacts_created=false"
exit "$RC"
