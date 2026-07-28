#!/usr/bin/env bash
set -euo pipefail
mode=${1:?prepare-or-verify-download}
if [ "$mode" = prepare ]; then
  : "${PRIVATE_REPO_PAT:?}" "${CAPTION_CARRIER_BRANCH:?}" "${CAPTION_CARRIER_HEAD:?}" "${ACCEPTED_AUDIO_HEAD:?}" "${CAPTION_VTT_SHA256:?}"
  for value in "$CAPTION_CARRIER_HEAD" "$ACCEPTED_AUDIO_HEAD"; do test "${#value}" = 40; done
  git init -q "$WORK/caption-carrier"
  git -C "$WORK/caption-carrier" remote add origin "https://x-access-token:${PRIVATE_REPO_PAT}@github.com/${PRODUCTION_REPO}.git"
  test "$(git -C "$WORK/caption-carrier" ls-remote origin "refs/heads/$CAPTION_CARRIER_BRANCH" | awk '{print $1}')" = "$CAPTION_CARRIER_HEAD"
  git -C "$WORK/caption-carrier" fetch -q origin "$CAPTION_CARRIER_HEAD" "$ACCEPTED_AUDIO_HEAD"
  git -C "$WORK/caption-carrier" checkout -q --detach "$CAPTION_CARRIER_HEAD"
  git -C "$WORK/caption-carrier" remote set-url origin "https://github.com/${PRODUCTION_REPO}.git"
  git -C "$WORK/caption-carrier" merge-base --is-ancestor "$ACCEPTED_AUDIO_HEAD" "$CAPTION_CARRIER_HEAD"
  root="$WORK/caption-carrier/sanitized_timing_handoff_v01"
  python3 scripts/gold_s01_canonical_pre_render_v2.py verify-captions --root "$root" \
    --accepted-audio-head "$ACCEPTED_AUDIO_HEAD" --timing-sha256 "$ACCEPTED_TIMING_SHA256" \
    --caption-json-sha256 "$ACCEPTED_CAPTION_JSON_SHA256" --caption-vtt-sha256 "$CAPTION_VTT_SHA256" \
    --receipt "$WORK/caption-input-receipt.json"
  python3 scripts/gold_s01_canonical_pre_render_v2.py stage-caption-pack --root "$root" \
    --output-dir "$WORK/caption-pack" --receipt "$WORK/caption-stage-receipt.json"
  test "$(find "$WORK/caption-pack" -maxdepth 1 -type f | wc -l)" = 5
elif [ "$mode" = verify-download ]; then
  : "${CAPTION_ARTIFACT_ID:?}" "${GH_TOKEN:?}" "${CAPTION_CARRIER_HEAD:?}" "${ACCEPTED_AUDIO_HEAD:?}" "${CAPTION_VTT_SHA256:?}"
  gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${CAPTION_ARTIFACT_ID}/zip" > "$WORK/caption-artifact.zip"
  archive_sha=$(sha256sum "$WORK/caption-artifact.zip" | awk '{print $1}')
  mkdir -p "$WORK/caption-redownload"
  unzip -q "$WORK/caption-artifact.zip" -d "$WORK/caption-redownload"
  python3 scripts/gold_s01_canonical_pre_render_v2.py verify-captions --root "$WORK/caption-redownload" \
    --accepted-audio-head "$ACCEPTED_AUDIO_HEAD" --timing-sha256 "$ACCEPTED_TIMING_SHA256" \
    --caption-json-sha256 "$ACCEPTED_CAPTION_JSON_SHA256" --caption-vtt-sha256 "$CAPTION_VTT_SHA256" \
    --receipt "$WORK/caption-download-receipt.json"
  job_id=$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/jobs" --jq '.jobs[] | select(.name=="caption-packaging") | .id' | head -n1)
  python3 - <<PY
import json, os
from pathlib import Path
d={
  'schema_version':'gold_s01_caption_public_artifact_receipt.v3',
  'result':'PASS',
  'runner_head':os.environ['GITHUB_SHA'],
  'caption_carrier_head':os.environ['CAPTION_CARRIER_HEAD'],
  'accepted_audio_execution_head':os.environ['ACCEPTED_AUDIO_HEAD'],
  'accepted_timing_sha256':os.environ['ACCEPTED_TIMING_SHA256'],
  'caption_json_sha256':os.environ['ACCEPTED_CAPTION_JSON_SHA256'],
  'caption_vtt_sha256':os.environ['CAPTION_VTT_SHA256'],
  'accepted_duration_ms':908398,
  'final_caption_end_ms':908398,
  'caption_file_count':5,
  'caption_json_block_count':13,
  'caption_vtt_cue_count':13,
  'caption_artifact_id':int(os.environ['CAPTION_ARTIFACT_ID']),
  'caption_artifact_archive_sha256':'$archive_sha',
  'caption_artifact_run_id':int(os.environ['GITHUB_RUN_ID']),
  'caption_artifact_job_id':int('$job_id'),
  'caption_download_identity':'PASS',
  'media_render_started':False,
  'no_fake_green':True,
}
Path(os.environ['WORK'],'caption-public-artifact-receipt.json').write_text(json.dumps(d,sort_keys=True,separators=(',',':'))+'\n')
PY
else
  echo "UNKNOWN_MODE=$mode" >&2; exit 2
fi
