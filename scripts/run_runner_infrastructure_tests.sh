#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
bash -n scripts/run_manifest_gate.sh
python3 -m py_compile \
  scripts/runner_infrastructure_v1.py \
  scripts/content_semantics_gate_v1.py \
  scripts/alignment_model_provisioning_v1.py \
  scripts/validate_cross_repo_sync_v1.py \
  tests/test_runner_infrastructure.py \
  tests/test_content_semantics_gate.py \
  tests/test_alignment_model_provisioning.py \
  tests/test_cross_repo_sync.py
python3 scripts/runner_infrastructure_v1.py validate-contract
python3 scripts/runner_infrastructure_v1.py validate-private-contract
python3 scripts/validate_cross_repo_sync_v1.py \
  --expected config/factory_sync_epoch_v1.json \
  --observed config/factory_sync_epoch_v1.json
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
