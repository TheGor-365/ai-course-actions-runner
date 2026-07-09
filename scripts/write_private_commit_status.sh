#!/usr/bin/env bash
set -euo pipefail

PRIVATE_REPO="${1:-}"
PRIVATE_SHA="${2:-}"
STATUS_CONTEXT="${3:-}"
STATE="${4:-}"
DESCRIPTION="${5:-}"
TARGET_URL="${6:-}"

if [[ -z "$PRIVATE_REPO" || -z "$PRIVATE_SHA" || -z "$STATUS_CONTEXT" || -z "$STATE" ]]; then
  echo "status_write=skipped"
  echo "error_class=missing_required_arguments"
  exit 2
fi

case "$STATE" in
  pending|success|failure|error) ;;
  *)
    echo "status_write=failed"
    echo "error_class=invalid_status_state"
    exit 2
    ;;
esac

DESCRIPTION="${DESCRIPTION:0:140}"

PAYLOAD_FILE="$(mktemp)"
python3 - "$STATE" "$TARGET_URL" "$DESCRIPTION" "$STATUS_CONTEXT" > "$PAYLOAD_FILE" <<'PY'
import json
import sys
state, target_url, description, context = sys.argv[1:5]
payload = {
    'state': state,
    'target_url': target_url,
    'description': description,
    'context': context,
}
print(json.dumps(payload, separators=(',', ':')))
PY

curl -fsS \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${PRIVATE_REPO_PAT}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${PRIVATE_REPO}/statuses/${PRIVATE_SHA}" \
  --data-binary "@$PAYLOAD_FILE" \
  -o /dev/null

rm -f "$PAYLOAD_FILE"
echo "status_write=ok"
echo "status_context=$STATUS_CONTEXT"
echo "status_state=$STATE"
