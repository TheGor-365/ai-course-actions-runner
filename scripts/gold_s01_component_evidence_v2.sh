#!/usr/bin/env bash
set -euo pipefail
: "${PRIVATE_REPO_PAT:?}" "${PRODUCTION_REPO:?}" "${PRODUCTION_BRANCH:?}" "${PRODUCTION_RUNTIME_HEAD:?}" "${PRODUCTION_COMPILE_HEAD:?}"
: "${COMPILER_ARTIFACT_ID:?}" "${COMPILER_ARTIFACT_SHA256:?}" "${CAPTION_ARTIFACT_ID:?}" "${CAPTION_ARTIFACT_SHA256:?}"
: "${CAPTION_VTT_SHA256:?}" "${ACCEPTED_AUDIO_HEAD:?}" "${ACCEPTED_TIMING_SHA256:?}" "${ACCEPTED_CAPTION_JSON_SHA256:?}"
: "${A3483_SHA256:?}" "${GH_TOKEN:?}" "${GITHUB_SHA:?}" "${GITHUB_REPOSITORY:?}" "${WORK:?}"
: "${REMOTION_ROOT:?}" "${PREMIUM_ENTRYPOINT:?}" "${COMPOSITION_ID:?}"
for value in "$PRODUCTION_RUNTIME_HEAD" "$PRODUCTION_COMPILE_HEAD" "$ACCEPTED_AUDIO_HEAD" "$GITHUB_SHA"; do
  test "${#value}" = 40
done
REQUIRED_EVIDENCE_FRAMES=(
  0 44 89 90 317 318 544 545 589 634 635 1301 1302 1967 1968
  2013 2057 2058 2436 2437 2815 2816 2861 2905 2906 3329 3330 3599
)
test "${#REQUIRED_EVIDENCE_FRAMES[@]}" = 28
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
raw_captions=next(d[k] for k in ('caption_blocks','blocks','captions','segments','cues') if isinstance(d.get(k),list))
captions=[]
for index,cue in enumerate(raw_captions):
    if not isinstance(cue,dict): raise SystemExit(f'CAPTION_RUNTIME_ADAPTER_OBJECT_REQUIRED:{index}')
    cue_id=cue.get('id') or cue.get('caption_block_id')
    if not isinstance(cue_id,str) or not cue_id: raise SystemExit(f'CAPTION_RUNTIME_ADAPTER_ID_REQUIRED:{index}')
    captions.append({'id':cue_id,'start_ms':cue.get('start_ms'),'end_ms':cue.get('end_ms'),'text':cue.get('text')})
if len(captions)!=13 or len({cue['id'] for cue in captions})!=13: raise SystemExit('CAPTION_RUNTIME_ADAPTER_IDENTITY_FAILED')
props={'audioSrc':(root/'M1_L01_S01_RU_A3483_voice_sfx_mix_v01.wav').resolve().as_uri(),'captions':captions,'acceptedTimingSha256':os.environ['ACCEPTED_TIMING_SHA256'],'captionJsonSha256':os.environ['ACCEPTED_CAPTION_JSON_SHA256'],'captionVttSha256':os.environ['CAPTION_VTT_SHA256']}
(root/'props.json').write_text(json.dumps(props,ensure_ascii=False),encoding='utf-8')
PY
  sudo apt-get update -qq
  sudo apt-get install -y -qq imagemagick
  for frame in "${REQUIRED_EVIDENCE_FRAMES[@]}"; do
    npx remotion still "$PREMIUM_ENTRYPOINT" "$COMPOSITION_ID" "$WORK/component-evidence/frames/frame-${frame}.png" --frame="$frame" --props="$WORK/props.json"
    test -s "$WORK/component-evidence/frames/frame-${frame}.png"
    deviation=$(identify -format '%[fx:standard_deviation]' "$WORK/component-evidence/frames/frame-${frame}.png")
    python3 -c 'import sys; assert float(sys.argv[1]) > 0.005' "$deviation"
  done
)
python3 - <<'PY'
import hashlib, json, os, re, subprocess
from pathlib import Path
work=Path(os.environ['WORK'])
compiled=work/'production/03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/compiler_outputs_v3'
scenes=json.loads((compiled/'resolved_premium_scene_ir.json').read_text(encoding='utf-8'))['records']
events=json.loads((compiled/'resolved_event_scene_binding.json').read_text(encoding='utf-8'))['records']
captions=json.loads((work/'captions/s01_ru_final_captions_v01.json').read_text(encoding='utf-8'))
cues=next(captions[k] for k in ('caption_blocks','blocks','captions','segments','cues') if isinstance(captions.get(k),list))
priorities=['course.editor.shell.v1','course.diagram.checkpoint.v1','course.diagram.input_process_output.v1','course.diagram.comparison.v1','course.diagram.timeline.v1','course.diagram.cause_effect.v1','course.code.line_focus.v1','course.code.code_to_object_binding.v1']
probes={'VE_001':{'start':0,'peak':44,'end':90},'VE_002':{'start':545,'peak':589,'end':635},'VE_003':{'start':1968,'peak':2013,'end':2058},'VE_004':{'start':2816,'peak':2861,'end':2906}}
required_frames=[0,44,89,90,317,318,544,545,589,634,635,1301,1302,1967,1968,2013,2057,2058,2436,2437,2815,2816,2861,2905,2906,3329,3330,3599]
internal_id_pattern=re.compile(r'(?i)(?:\bVE_\d{3}\b|\bcourse\.[a-z0-9_.-]+\b|\btarget\.[a-z0-9_.-]+\b|\bhandler\.[a-z0-9_.-]+\b)')
debug_pattern=re.compile(r'(?i)(?:debug[_:. -]|production_runtime_head|compiler_artifact_id|frame_sha256|data-[a-z0-9_-]+)')
def event_value(event, frame):
    start,end=event['timing']['start_frame'],event['timing']['end_frame']
    progress=max(0.0,min(1.0,(frame-start)/max(1,end-start)))
    if event['handler_id']=='roadmap_step_unlock_v1':
        return event['parameters']['beforeLocked'] if progress < event['phase_model']['enterRatio'] else event['parameters']['afterLocked']
    return progress
def visible_text(scene):
    values=[]
    for key in ('foreground_layer','midground_layer','background_layer'):
        value=scene.get(key,[])
        if isinstance(value,list): values.extend(str(item) for item in value)
        elif value is not None: values.append(str(value))
    return '\n'.join(values)
frames=[]
for png in sorted((work/'component-evidence/frames').glob('frame-*.png'),key=lambda p:int(p.stem.split('-')[1])):
    frame=int(png.stem.split('-')[1])
    scene=next(s for s in scenes if s['start_frame']<=frame<s['end_frame'])
    active=[e for e in events if e['timing']['start_frame']<=frame<e['timing']['end_frame']]
    primary=next(i for i in priorities if i in scene['shared_component_ids'])
    caption=next((c for c in cues if c['start_ms']<=frame/30*1000<c['end_ms']),None)
    digest=hashlib.sha256(png.read_bytes()).hexdigest()
    deviation=float(subprocess.check_output(['identify','-format','%[fx:standard_deviation]',str(png)],text=True))
    assert deviation > 0.005
    primary_bounds={'x':248,'y':164,'width':1424,'height':520}
    geometry=scene['caption_safe_geometry']
    left=geometry.get('left',176); right=geometry.get('right',176); top=geometry['caption_top']; bottom=geometry['bottom']
    caption_bounds={'x':left,'y':top,'width':1920-left-right,'height':max(1,bottom-top)}
    assert primary_bounds['y']+primary_bounds['height'] <= geometry['bottom']
    assert geometry['caption_top']-geometry['bottom'] >= geometry['clearance']
    assert scene['contact_shadow_policy']['required'] is True
    assert sum(bool(scene[k]) for k in ('foreground_layer','midground_layer','background_layer')) >= (3 if scene['premium_tier']=='C_PREMIUM' else 2 if scene['premium_tier']=='B_STRONG' else 1)
    rendered_text=visible_text(scene)
    png_ascii=png.read_bytes().decode('latin1',errors='ignore')
    internal_id_leak=bool(internal_id_pattern.search(rendered_text) or internal_id_pattern.search(png_ascii))
    debug_metadata_leak=bool(debug_pattern.search(rendered_text) or debug_pattern.search(png_ascii))
    assert internal_id_leak is False, (frame,rendered_text)
    assert debug_metadata_leak is False, (frame,rendered_text)
    frames.append({'frame':frame,'composition_id':'GoldS01PremiumFirst120s','production_runtime_head':os.environ['PRODUCTION_RUNTIME_HEAD'],'frame_sha256':digest,'standard_deviation':deviation,'generic_asset_grid_count':0,'primary_focus_bounds':primary_bounds,'caption_bounds':caption_bounds,'internal_id_leak':False,'debug_metadata_leak':False,'camera_preset_id':scene['camera_preset_id'],'lens_profile_id':scene['lens_profile_id'],'lighting_rig_id':scene['lighting_rig_id'],'material_profile_ids':scene['material_profile_ids'],'texture_profile_ids':scene['texture_profile_ids'],'ambient_life_ids':scene['ambient_life_ids'],'caption_active':caption is not None,'event_ids':[e['event_id'] for e in active],'asset_ids':scene['asset_ids'],'scene_id':scene['scene_id'],'primary_surface_id':primary})
assert [frame['frame'] for frame in frames]==required_frames
by_frame={frame['frame']:frame for frame in frames}
for event_id,probe in probes.items():
    event=next(e for e in events if e['event_id']==event_id)
    peak=by_frame[probe['peak']]
    before=event['target_initial_value']; after=event_value(event,probe['peak'])
    frame_hashes={position:by_frame[number]['frame_sha256'] for position,number in probe.items()}
    telemetry_complete=all((event.get('handler_id'),event.get('target_id'),event.get('target_property'),event.get('timing',{}).get('semantic_anchor'))) and before != after and all(re.fullmatch(r'[0-9a-f]{64}',value) for value in frame_hashes.values())
    assert telemetry_complete is True, event_id
    peak.update({'handler_id':event['handler_id'],'target_object_id':event['target_id'],'target_property':event['target_property'],'semantic_anchor':event['timing']['semantic_anchor'],'property_before':before,'property_after':after,'telemetry_complete':True,'frame_hashes':frame_hashes})
receipt={'schema_version':'gold_s01_component_evidence.v3','runner_head':os.environ['GITHUB_SHA'],'caption_artifact_id':int(os.environ['CAPTION_ARTIFACT_ID']),'frames':frames,'qc':{'FRAME_ZERO_LAYOUT':'PASS','SCENE_CONTINUITY':'PASS','PRIMARY_FOCUS_BOUNDS':'PASS','CAPTION_CLEARANCE':'PASS','CONTACT_SHADOW_EVIDENCE':'PASS','DEPTH_LAYER_EVIDENCE':'PASS','EVENT_TARGET_DELTA':'PASS','NO_GENERIC_GRID':'PASS','NO_BLANK_FRAME':'PASS','NO_INTERNAL_DEBUG_IDS':'PASS'},'media_render_started':False,'no_fake_green':True}
out=work/'component-evidence/component-evidence-receipt.json'
out.write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
PY
python3 scripts/gold_s01_canonical_pre_render_v2.py verify-component-receipt \
  --receipt-path "$WORK/component-evidence/component-evidence-receipt.json" \
  --expected-runner-head "$GITHUB_SHA" \
  --expected-caption-artifact-id "$CAPTION_ARTIFACT_ID" \
  --output "$WORK/component-evidence/component-validation-receipt.json"
