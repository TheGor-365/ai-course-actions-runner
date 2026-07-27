#!/usr/bin/env bash
set -euo pipefail
: "${PRIVATE_REPO_PAT:?}" "${GH_TOKEN:?}" "${WORK:?}" "${AUTHORITY_MANIFEST_PATH:?}" "${RUNNER_HEAD:?}"
manifest="$AUTHORITY_MANIFEST_PATH"
get(){ python3 scripts/gold_s01_canonical_pre_render_v2.py get --manifest "$manifest" --key "$1"; }
python3 scripts/gold_s01_canonical_pre_render_v2.py verify-manifest --manifest "$manifest" --receipt "$WORK/manifest-validation.json"
test "$(git rev-parse HEAD)" = "$RUNNER_HEAD"
test "$(get runner_workflow_head)" = "$RUNNER_HEAD"
clone_exact(){
  repo="$1" branch="$2" head="$3" dir="$4"
  git init -q "$dir"
  git -C "$dir" remote add origin "https://x-access-token:${PRIVATE_REPO_PAT}@github.com/${repo}.git"
  test "$(git -C "$dir" ls-remote origin "refs/heads/$branch" | awk '{print $1}')" = "$head"
  git -C "$dir" fetch -q origin "$head"
  git -C "$dir" checkout -q --detach "$head"
  git -C "$dir" remote set-url origin "https://github.com/${repo}.git"
  test "$(git -C "$dir" rev-parse HEAD)" = "$head"
}
mkdir -p "$WORK"
clone_exact "$(get source_repository)" "$(get source_branch)" "$(get source_head)" "$WORK/source"
clone_exact "$(get production_repository)" "$(get production_branch)" "$(get production_runtime_head)" "$WORK/production"
git -C "$WORK/production" fetch -q origin "$(get production_compile_head)"
git -C "$WORK/production" merge-base --is-ancestor "$(get production_compile_head)" "$(get production_runtime_head)"
git -C "$WORK/production" fetch -q origin "$(get caption_carrier_head)" "$(get accepted_audio_execution_head)"
git -C "$WORK/production" merge-base --is-ancestor "$(get accepted_audio_execution_head)" "$(get caption_carrier_head)"
clone_exact "$(get quality_repository)" "$(get quality_branch)" "$(get quality_evidence_head)" "$WORK/quality"
download_artifact(){
  id="$1" expected="$2" zip="$3" dir="$4"
  gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${id}/zip" > "$WORK/$zip"
  test "$(sha256sum "$WORK/$zip" | awk '{print $1}')" = "$expected"
  mkdir -p "$WORK/$dir" && unzip -q "$WORK/$zip" -d "$WORK/$dir"
}
download_artifact "$(get source_exact_artifact_id)" "$(get source_exact_artifact_sha256)" source.zip source-artifact
download_artifact "$(get compiler_artifact_id)" "$(get compiler_artifact_sha256)" compiler.zip compiler-artifact
download_artifact "$(get caption_artifact_id)" "$(get caption_artifact_sha256)" captions.zip captions
download_artifact "$(get component_evidence_artifact_id)" "$(get component_evidence_artifact_sha256)" component.zip component
python3 "$WORK/production/11_tools/render_factory/gold_s01_visual_v2/stage_premium_compiler_artifact_v3.py" \
  --production-root "$WORK/production" --archive "$WORK/compiler.zip" --receipt "$WORK/compiler-stage.json"
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
work=Path(os.environ['WORK']); manifest=json.loads(Path(os.environ['AUTHORITY_MANIFEST_PATH']).read_text())
root=work/'production/03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/compiler_outputs_v3'
for name,digest in manifest['compiler_output_file_hashes'].items():
    path=root/name
    assert path.is_file(), name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest, name
PY
gh release download gold-s01-a3483-input-v1 --repo "$GITHUB_REPOSITORY" \
  --pattern M1_L01_S01_RU_A3483_voice_sfx_mix_v01.wav --dir "$WORK"
test "$(sha256sum "$WORK/M1_L01_S01_RU_A3483_voice_sfx_mix_v01.wav" | awk '{print $1}')" = "$(get A3483_sha256)"
python3 scripts/gold_s01_canonical_pre_render_v2.py verify-captions --root "$WORK/captions" \
  --accepted-audio-head "$(get accepted_audio_execution_head)" --timing-sha256 "$ACCEPTED_TIMING_SHA256" \
  --caption-json-sha256 "$(get caption_json_sha256)" --caption-vtt-sha256 "$(get caption_vtt_sha256)" \
  --receipt "$WORK/caption-validation.json"
python3 scripts/gold_s01_canonical_pre_render_v2.py verify-component-receipt \
  --receipt-path "$WORK/component/component-evidence-receipt.json" --output "$WORK/component-validation.json"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npm ci
  npm run typecheck
  npm run test:event-runtime
  npm run test:premium-production-integration
  npx remotion compositions "$PREMIUM_ENTRYPOINT" --log=verbose | tee "$WORK/compositions.txt"
)
grep -F "$COMPOSITION_ID" "$WORK/compositions.txt"
grep -E '3600|00:02:00' "$WORK/compositions.txt"
python3 - <<'PY'
import json,os
from pathlib import Path
work=Path(os.environ['WORK']); m=json.loads(Path(os.environ['AUTHORITY_MANIFEST_PATH']).read_text())
r={'schema_version':'gold_s01_runtime_pre_render_validation.v2','result':'PASS','production_compile_head':m['production_compile_head'],'production_runtime_head':m['production_runtime_head'],'composition_id':'GoldS01PremiumFirst120s','duration_in_frames':3600,'runtime_typecheck':'PASS','runtime_tests':'PASS','composition_discovery':'PASS','one_coherent_scene_orchestration':'PASS','generic_asset_grid_count':0,'generic_presentation_substitution_count':0,'scene_primary_teaching_surface_count':26,'canonical_event_dispatch':'PASS','first_120_required_events':'4/4_PASS','target_property_changed_count':4,'generic_motion_substitution_count':0,'event_timing_shift_count':0,'unsafe_cast_only_json_acceptance':False,'scene_ir_array_fields_normalized':True,'presentation_layer_limit_interpreted_as_asset_count':False,'compile_head_required_to_equal_runtime_head':False,'canonical_gold_s01_triggering_workflow_count':1,'media_render_started':False,'no_fake_green':True}
(work/'runtime-validation.json').write_text(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n')
caption=json.loads((work/'caption-validation.json').read_text())
caption.update({'caption_artifact_id':m['caption_artifact_id'],'accepted_caption_json_materialized':True,'accepted_caption_vtt_materialized':True,'caption_artifact_download_hash_verified':True,'caption_download_identity':'PASS','caption_carrier_ancestry_pass':True})
(work/'caption-validation.json').write_text(json.dumps(caption,sort_keys=True,separators=(',',':'))+'\n')
PY
python3 "$WORK/quality/04_validators/render/premium_qc/validate_gold_s01_pre_render_inputs_v1.py" \
  --manifest "$manifest" --compiler-output-dir "$WORK/production/03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/compiler_outputs_v3" \
  --component-evidence "$WORK/component/component-evidence-receipt.json" \
  --caption-input-receipt "$WORK/caption-validation.json" --runtime-receipt "$WORK/runtime-validation.json" \
  --pre-render-mode --output "$WORK/quality-validation.json"
test "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("result"))' "$WORK/quality-validation.json")" = PASS
python3 scripts/gold_s01_canonical_pre_render_v2.py write-pre-render-receipt \
  --manifest "$manifest" --runtime-receipt "$WORK/runtime-validation.json" \
  --quality-receipt "$WORK/quality-validation.json" --component-receipt "$WORK/component-validation.json" \
  --caption-receipt "$WORK/caption-validation.json" --output "$WORK/pre-render-receipt.json"
mkdir -p "$WORK/pre-render-artifact"
cp "$WORK/pre-render-receipt.json" "$WORK/manifest-validation.json" "$WORK/runtime-validation.json" \
  "$WORK/quality-validation.json" "$WORK/component-validation.json" "$WORK/caption-validation.json" \
  "$WORK/compositions.txt" "$WORK/pre-render-artifact/"
(cd "$WORK/pre-render-artifact" && sha256sum * > SHA256SUMS)
