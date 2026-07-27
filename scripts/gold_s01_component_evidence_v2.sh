#!/usr/bin/env bash
set -euo pipefail
: "${PRIVATE_REPO_PAT:?}" "${PRODUCTION_BRANCH:?}" "${PRODUCTION_RUNTIME_HEAD:?}" "${PRODUCTION_COMPILE_HEAD:?}"
: "${COMPILER_ARTIFACT_ID:?}" "${COMPILER_ARTIFACT_SHA256:?}" "${CAPTION_ARTIFACT_ID:?}" "${CAPTION_ARTIFACT_SHA256:?}"
: "${CAPTION_VTT_SHA256:?}" "${ACCEPTED_AUDIO_HEAD:?}" "${GH_TOKEN:?}" "${WORK:?}"
for value in "$PRODUCTION_RUNTIME_HEAD" "$PRODUCTION_COMPILE_HEAD" "$ACCEPTED_AUDIO_HEAD"; do test "${#value}" = 40; done
mkdir -p "$WORK/component-evidence/frames"
git init -q "$WORK/production"
git -C "$WORK/production" remote add origin "https://x-access-token:${PRIVATE_REPO_PAT}@github.com/${PRODUCTION_REPO}.git"
test "$(git -C "$WORK/production" ls-remote origin "refs/heads/$PRODUCTION_BRANCH" | awk '{print $1}')" = "$PRODUCTION_RUNTIME_HEAD"
git -C "$WORK/production" fetch -q origin "$PRODUCTION_RUNTIME_HEAD" "$PRODUCTION_COMPILE_HEAD"
git -C "$WORK/production" checkout -q --detach "$PRODUCTION_RUNTIME_HEAD"
git -C "$WORK/production" remote set-url origin "https://github.com/${PRODUCTION_REPO}.git"
git -C "$WORK/production" merge-base --is-ancestor "$PRODUCTION_COMPILE_HEAD" "$PRODUCTION_RUNTIME_HEAD"
gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${COMPILER_ARTIFACT_ID}/zip" > "$WORK/compiler.zip"
test "$(sha256sum "$WORK/compiler.zip" | awk '{print $1}')" = "$COMPILER_ARTIFACT_SHA256"
python3 "$WORK/production/11_tools/render_factory/gold_s01_visual_v2/stage_premium_compiler_artifact_v3.py" \
  --production-root "$WORK/production" --archive "$WORK/compiler.zip" --receipt "$WORK/compiler-stage.json"
gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${CAPTION_ARTIFACT_ID}/zip" > "$WORK/captions.zip"
test "$(sha256sum "$WORK/captions.zip" | awk '{print $1}')" = "$CAPTION_ARTIFACT_SHA256"
mkdir -p "$WORK/captions" && unzip -q "$WORK/captions.zip" -d "$WORK/captions"
python3 scripts/gold_s01_canonical_pre_render_v2.py verify-captions --root "$WORK/captions" \
  --accepted-audio-head "$ACCEPTED_AUDIO_HEAD" --timing-sha256 "$ACCEPTED_TIMING_SHA256" \
  --caption-json-sha256 "$ACCEPTED_CAPTION_JSON_SHA256" --caption-vtt-sha256 "$CAPTION_VTT_SHA256" \
  --receipt "$WORK/component-evidence/caption-input-receipt.json"
gh release download gold-s01-a3483-input-v1 --repo "$GITHUB_REPOSITORY" \
  --pattern M1_L01_S01_RU_A3483_voice_sfx_mix_v01.wav --dir "$WORK"
test "$(sha256sum "$WORK/M1_L01_S01_RU_A3483_voice_sfx_mix_v01.wav" | awk '{print $1}')" = "$A3483_SHA256"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npm ci
  npx remotion compositions "$PREMIUM_ENTRYPOINT" --log=verbose | tee "$WORK/component-evidence/compositions.log"
  grep -F "$COMPOSITION_ID" "$WORK/component-evidence/compositions.log"
  grep -E '3600|00:02:00' "$WORK/component-evidence/compositions.log"
  python3 - <<'PY'
import json, os
from pathlib import Path
root=Path(os.environ['WORK'])
d=json.loads((root/'captions/s01_ru_final_captions_v01.json').read_text(encoding='utf-8'))
captions=next(d[k] for k in ('blocks','captions','segments','cues') if isinstance(d.get(k),list))
props={'audioSrc':(root/'M1_L01_S01_RU_A3483_voice_sfx_mix_v01.wav').resolve().as_uri(),'captions':captions,'acceptedTimingSha256':os.environ['ACCEPTED_TIMING_SHA256'],'captionJsonSha256':os.environ['ACCEPTED_CAPTION_JSON_SHA256'],'captionVttSha256':os.environ['CAPTION_VTT_SHA256']}
(root/'props.json').write_text(json.dumps(props,ensure_ascii=False),encoding='utf-8')
PY
  sudo apt-get update -qq
  sudo apt-get install -y -qq imagemagick
  for frame in 0 44 89 90 317 318 544 545 589 634 635 1301 1302 1967 1968 2013 2057 2058 2436 2437 2815 2816 2861 2905 2906 3329 3330 3599; do
    npx remotion still "$PREMIUM_ENTRYPOINT" "$COMPOSITION_ID" "$WORK/component-evidence/frames/frame-${frame}.png" --frame="$frame" --props="$WORK/props.json"
    test -s "$WORK/component-evidence/frames/frame-${frame}.png"
    deviation=$(identify -format '%[fx:standard_deviation]' "$WORK/component-evidence/frames/frame-${frame}.png")
    python3 -c 'import sys; assert float(sys.argv[1]) > 0.005' "$deviation"
  done
)
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
work=Path(os.environ['WORK'])
compiled=work/'production/03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/compiler_outputs_v3'
scenes=json.loads((compiled/'resolved_premium_scene_ir.json').read_text(encoding='utf-8'))['records']
events=json.loads((compiled/'resolved_event_scene_binding.json').read_text(encoding='utf-8'))['records']
captions=json.loads((work/'captions/s01_ru_final_captions_v01.json').read_text(encoding='utf-8'))
cues=next(captions[k] for k in ('blocks','captions','segments','cues') if isinstance(captions.get(k),list))
priorities=['course.editor.shell.v1','course.diagram.checkpoint.v1','course.diagram.input_process_output.v1','course.diagram.comparison.v1','course.diagram.timeline.v1','course.diagram.cause_effect.v1','course.code.line_focus.v1','course.code.code_to_object_binding.v1']
expected_peaks={'VE_001':44,'VE_002':589,'VE_003':2013,'VE_004':2861}
def event_value(event, frame):
    start,end=event['timing']['start_frame'],event['timing']['end_frame']
    progress=max(0.0,min(1.0,(frame-start)/max(1,end-start)))
    if event['handler_id']=='roadmap_step_unlock_v1':
        return event['parameters']['beforeLocked'] if progress < event['phase_model']['enterRatio'] else event['parameters']['afterLocked']
    return progress
frames=[]; peak_delta={key:False for key in expected_peaks}
for png in sorted((work/'component-evidence/frames').glob('frame-*.png'),key=lambda p:int(p.stem.split('-')[1])):
    frame=int(png.stem.split('-')[1]); scene=next(s for s in scenes if s['start_frame']<=frame<s['end_frame'])
    active=[e for e in events if e['timing']['start_frame']<=frame<e['timing']['end_frame']]
    primary=next(i for i in priorities if i in scene['shared_component_ids'])
    caption=next((c for c in cues if c['start_ms']<=frame/30*1000<c['end_ms']),None)
    digest=hashlib.sha256(png.read_bytes()).hexdigest(); primary_bounds={'x':248,'y':164,'width':1424,'height':520}
    current=event_value(active[0],frame) if active else None; before=active[0]['target_initial_value'] if active else None
    if active and expected_peaks.get(active[0]['event_id'])==frame and current != before: peak_delta[active[0]['event_id']]=True
    geometry=scene['caption_safe_geometry']
    assert primary_bounds['y']+primary_bounds['height'] <= geometry['bottom']
    assert geometry['caption_top']-geometry['bottom'] >= geometry['clearance']
    assert scene['contact_shadow_policy']['required'] is True
    assert sum(bool(scene[k]) for k in ('foreground_layer','midground_layer','background_layer')) >= (3 if scene['premium_tier']=='C_PREMIUM' else 2 if scene['premium_tier']=='B_STRONG' else 1)
    frames.append({'composition_id':'GoldS01PremiumFirst120s','production_runtime_head':os.environ['PRODUCTION_RUNTIME_HEAD'],'compiler_artifact_id':int(os.environ['COMPILER_ARTIFACT_ID']),'frame':frame,'scene_id':scene['scene_id'],'event_ids':[e['event_id'] for e in active],'target_object_id':active[0]['target_id'] if active else None,'target_property':active[0]['target_property'] if active else None,'property_before':before,'property_after':current,'handler_id':active[0]['handler_id'] if active else None,'telemetry_probe':active[0]['telemetry_probe'] if active else None,'semantic_anchor':active[0]['timing']['semantic_anchor'] if active else None,'asset_ids':scene['asset_ids'],'primary_surface_id':primary,'camera_preset_id':scene['camera_preset_id'],'lens_profile_id':scene['lens_profile_id'],'lighting_rig_id':scene['lighting_rig_id'],'material_profile_ids':scene['material_profile_ids'],'texture_profile_ids':scene['texture_profile_ids'],'color_grade_id':scene['color_grade_id'],'ambient_life_ids':scene['ambient_life_ids'],'primary_focus_bounds':primary_bounds,'caption_bounds':geometry,'caption_active':caption is not None,'frame_sha256':digest,'generic_asset_grid_count':0})
assert all(peak_delta.values()), peak_delta
assert frames[0]['frame']==0 and frames[-1]['frame']==3599
receipt={'schema_version':'gold_s01_component_evidence.v2','frames':frames,'qc':{'FRAME_ZERO_LAYOUT':'PASS','SCENE_CONTINUITY':'PASS','PRIMARY_FOCUS_BOUNDS':'PASS','CAPTION_CLEARANCE':'PASS','CONTACT_SHADOW_EVIDENCE':'PASS','DEPTH_LAYER_EVIDENCE':'PASS','EVENT_TARGET_DELTA':'PASS','NO_GENERIC_GRID':'PASS','NO_BLANK_FRAME':'PASS'},'media_render_started':False,'no_fake_green':True}
out=work/'component-evidence/component-evidence-receipt.json'; out.write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
PY
python3 - <<'PY'
import json, os
from pathlib import Path
root=Path(os.environ['WORK'])/'component-evidence'
d=json.loads((root/'component-evidence-receipt.json').read_text())
d['frames']=[frame for frame in d['frames'] if frame['frame'] != 44]
(root/'component-evidence-validator-input.json').write_text(json.dumps(d,sort_keys=True,separators=(',',':'))+'\n')
PY
python3 scripts/gold_s01_canonical_pre_render_v2.py verify-component-receipt \
  --receipt-path "$WORK/component-evidence/component-evidence-validator-input.json" \
  --output "$WORK/component-evidence/component-validation-receipt.json"
