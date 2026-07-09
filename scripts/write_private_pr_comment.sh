#!/usr/bin/env bash
set -euo pipefail

PRIVATE_REPO="${1:-}"
PRIVATE_PR="${2:-}"
COMMENT_FILE="${3:-}"

if [[ -z "$PRIVATE_REPO" || -z "$PRIVATE_PR" || -z "$COMMENT_FILE" ]]; then
  echo "pr_comment_write=skipped"
  echo "error_class=missing_required_arguments"
  exit 2
fi

if [[ ! -f "$COMMENT_FILE" ]]; then
  echo "pr_comment_write=failed"
  echo "error_class=comment_file_missing"
  exit 2
fi

PAYLOAD_FILE="$(mktemp)"
python3 - "$COMMENT_FILE" > "$PAYLOAD_FILE" <<'PY'
import json
import sys
from pathlib import Path
body = Path(sys.argv[1]).read_text(encoding='utf-8')
print(json.dumps({'body': body}, separators=(',', ':')))
PY

curl -fsS \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${PRIVATE_REPO_PAT}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/${PRIVATE_REPO}/issues/${PRIVATE_PR}/comments" \
  --data-binary "@$PAYLOAD_FILE" \
  -o /dev/null

rm -f "$PAYLOAD_FILE"
echo "pr_comment_write=ok"
echo "private_pr=$PRIVATE_PR"
