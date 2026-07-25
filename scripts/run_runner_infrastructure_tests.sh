#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
bash -n scripts/run_manifest_gate.sh
python3 -m py_compile \
  scripts/runner_infrastructure_v1.py \
  scripts/content_semantics_gate_v1.py \
  scripts/production_evidence_consumer_gate_v1.py \
  scripts/alignment_model_provisioning_v1.py \
  scripts/validate_cross_repo_sync_v1.py \
  scripts/private_owner_delivery_v1.py \
  scripts/run_private_owner_delivery_exact_v1.py \
  tests/test_runner_infrastructure.py \
  tests/test_content_semantics_gate.py \
  tests/test_alignment_model_provisioning.py \
  tests/test_cross_repo_sync.py \
  tests/test_private_owner_delivery.py \
  tests/test_private_owner_delivery_receipt_chain.py
python3 scripts/runner_infrastructure_v1.py validate-contract
python3 scripts/runner_infrastructure_v1.py validate-private-contract
python3 scripts/validate_cross_repo_sync_v1.py \
  --expected config/factory_sync_epoch_v1.json \
  --observed config/factory_sync_epoch_v1.json
python3 - <<'PY'
import json
from pathlib import Path
profiles = json.loads(Path("config/private_owner_delivery_profiles_v1.json").read_text())
schemas = json.loads(Path("schemas/private_owner_delivery_v1.schemas.json").read_text())
assert profiles["public_workflow_execution_allowed"] is False
assert profiles["public_artifact_upload_allowed"] is False
assert profiles["executor_entrypoint"] == "scripts/run_private_owner_delivery_exact_v1.py"
assert profiles["direct_internal_module_cli_authoritative"] is False
assert set(profiles["profiles"]) == {"OWNER_DELIVERY_EXISTING_STILLS_V1", "OWNER_DELIVERY_EXISTING_MEDIA_V1"}
assert set(schemas["schemas"]) == {
    "private_owner_delivery_request_v1",
    "private_artifact_registration_receipt_v1",
    "private_artifact_restore_receipt_v1",
    "owner_delivery_manifest_v1",
}
print("private_owner_delivery_contract=PASS")
PY
python3 -m unittest discover -s tests -p 'test_*.py' -v
if find . -type f \( -iname '*.mp3' -o -iname '*.wav' -o -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.webm' \) | grep -q .; then
  echo "binary_media_in_git=true"; exit 1
fi
if grep -RIE --exclude-dir=.git --exclude='*.pyc' \
  '(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|/home/[A-Za-z0-9._-]+/ai-course-private-artifacts)' .; then
  echo "secret_or_private_path_leak=true"; exit 1
fi
echo "binary_media_in_git=false"
echo "secret_or_private_path_leak=false"
echo "runner_infrastructure_tests=PASS"
