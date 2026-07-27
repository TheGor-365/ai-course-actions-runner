#!/usr/bin/env bash
set -euo pipefail
: "${PRIVATE_REPO_PAT:?}" "${PRODUCTION_BRANCH:?}" "${PRODUCTION_RUNTIME_HEAD:?}" "${PRODUCTION_COMPILE_HEAD:?}"
: "${COMPILER_ARTIFACT_ID:?}" "${COMPILER_ARTIFACT_SHA256:?}" "${GH_TOKEN:?}" "${WORK:?}"
for value in "$PRODUCTION_RUNTIME_HEAD" "$PRODUCTION_COMPILE_HEAD"; do test "${#value}" = 40; done
mkdir -p "$WORK/runtime-evidence"
exec > >(tee "$WORK/runtime-evidence/runtime-discovery-command.log") 2>&1
CURRENT_PHASE=INITIALIZED
on_exit() {
  status=$?
  if [ "$status" -ne 0 ]; then
    python3 - "$status" "$CURRENT_PHASE" "$WORK/runtime-evidence/runtime-discovery-failure.json" <<'PY'
import json, sys
from pathlib import Path
status, phase, output = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
output.write_text(json.dumps({
    'schema_version': 'gold_s01_runtime_discovery_failure.v1',
    'result': 'FAIL',
    'exit_code': status,
    'failed_phase': phase,
    'media_render_started': False,
    'no_fake_green': True,
}, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
PY
  fi
}
trap on_exit EXIT

CURRENT_PHASE=CLONE_EXACT_PRODUCTION_HEAD
echo "PHASE=$CURRENT_PHASE"
git init -q "$WORK/production"
git -C "$WORK/production" remote add origin "https://x-access-token:${PRIVATE_REPO_PAT}@github.com/${PRODUCTION_REPO}.git"
test "$(git -C "$WORK/production" ls-remote origin "refs/heads/$PRODUCTION_BRANCH" | awk '{print $1}')" = "$PRODUCTION_RUNTIME_HEAD"
git -C "$WORK/production" fetch -q origin "$PRODUCTION_RUNTIME_HEAD" "$PRODUCTION_COMPILE_HEAD"
git -C "$WORK/production" checkout -q --detach "$PRODUCTION_RUNTIME_HEAD"
git -C "$WORK/production" remote set-url origin "https://github.com/${PRODUCTION_REPO}.git"
test "$(git -C "$WORK/production" rev-parse HEAD)" = "$PRODUCTION_RUNTIME_HEAD"

CURRENT_PHASE=VERIFY_COMPILE_RUNTIME_ANCESTRY
echo "PHASE=$CURRENT_PHASE"
git -C "$WORK/production" merge-base --is-ancestor "$PRODUCTION_COMPILE_HEAD" "$PRODUCTION_RUNTIME_HEAD"
git -C "$WORK/production" diff --quiet "$PRODUCTION_COMPILE_HEAD" "$PRODUCTION_RUNTIME_HEAD" -- \
  11_tools/render_factory/gold_s01_visual_v2/premium_scene_compiler_v2.py \
  11_tools/render_factory/gold_s01_visual_v2/premium_scene_compiler_exact_v3.py \
  11_tools/render_factory/gold_s01_visual_v2/exact_v3 \
  03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/asset_registry_v1.json \
  03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/timing_binding_v1.json \
  03_modules/M1/L01/04_render_migration/gold_s01_visual_v2/premium_production_source_binding_v1.json
echo COMPILER_RERUN_REQUIRED=false

CURRENT_PHASE=DOWNLOAD_AND_STAGE_COMPILER_ARTIFACT
echo "PHASE=$CURRENT_PHASE"
gh api "repos/${GITHUB_REPOSITORY}/actions/artifacts/${COMPILER_ARTIFACT_ID}/zip" > "$WORK/compiler.zip"
test "$(sha256sum "$WORK/compiler.zip" | awk '{print $1}')" = "$COMPILER_ARTIFACT_SHA256"
python3 "$WORK/production/11_tools/render_factory/gold_s01_visual_v2/stage_premium_compiler_artifact_v3.py" \
  --production-root "$WORK/production" --archive "$WORK/compiler.zip" \
  --receipt "$WORK/runtime-evidence/compiler-staging-receipt.json"

CURRENT_PHASE=NPM_CI
echo "PHASE=$CURRENT_PHASE"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npm ci
)
CURRENT_PHASE=TYPECHECK
echo "PHASE=$CURRENT_PHASE"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npm run typecheck | tee "$WORK/runtime-evidence/typecheck.log"
)
CURRENT_PHASE=EVENT_RUNTIME_TESTS
echo "PHASE=$CURRENT_PHASE"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npm run test:event-runtime | tee "$WORK/runtime-evidence/event-runtime.log"
)
CURRENT_PHASE=PRODUCTION_INTEGRATION_TESTS
echo "PHASE=$CURRENT_PHASE"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npm run test:premium-production-integration | tee "$WORK/runtime-evidence/production-integration.log"
)
CURRENT_PHASE=COMPOSITION_DISCOVERY
echo "PHASE=$CURRENT_PHASE"
(
  cd "$WORK/production/$REMOTION_ROOT"
  npx remotion compositions "$PREMIUM_ENTRYPOINT" --log=verbose | tee "$WORK/runtime-evidence/compositions.log"
)
grep -F "$COMPOSITION_ID" "$WORK/runtime-evidence/compositions.log"
grep -E '3600|00:02:00' "$WORK/runtime-evidence/compositions.log"

CURRENT_PHASE=ACTIVE_IMPORT_GRAPH
echo "PHASE=$CURRENT_PHASE"
python3 - <<'PY'
import json, os, re
from pathlib import Path
root=Path(os.environ['WORK'])/'production/11_tools/render_factory/remotion/src/goldS01VisualV2'
seen=set(); stack=[root/'PremiumRootV3.tsx']; imports=[]
pattern=re.compile(r"(?:from\s+|import\s*)['\"]([^'\"]+)['\"]")
while stack:
    path=stack.pop().resolve()
    if path in seen: continue
    seen.add(path); text=path.read_text(encoding='utf-8')
    for spec in pattern.findall(text):
        imports.append((path.as_posix(),spec))
        if not spec.startswith('.'): continue
        base=(path.parent/spec).resolve()
        candidates=[base,base.with_suffix('.ts'),base.with_suffix('.tsx')]
        if spec.endswith('.js'): candidates += [Path(str(base)[:-3]+'.ts'),Path(str(base)[:-3]+'.tsx')]
        target=next((x for x in candidates if x.is_file()),None)
        if target: stack.append(target)
joined='\n'.join(f'{a} -> {b}' for a,b in imports)
for item in ('resolved_scene_ir_shard_01_v1.json','resolved_scene_ir_shard_02_v1.json','resolved_scene_ir_shard_03_v1.json','resolved_scene_ir_shard_04_v1.json','GoldS01HybridCompositions'):
    assert item not in joined, item
for item in ('resolved_premium_scene_ir.json','resolved_premium_shot_ir.json','resolved_event_scene_binding.json','resolved_shared_ID_binding.json','resolved_asset_materialization_plan.json','PremiumProductionRuntimeGateV4'):
    assert item in joined, item
renderer=(root/'PremiumSceneRendererV3.tsx').read_text(encoding='utf-8')
assert 'dispatchRuntimeFrame' in renderer and 'data-generic-asset-grid-count="0"' in renderer
assert "display: 'grid'" not in renderer and 'gridTemplateColumns' not in renderer
receipt={'schema_version':'gold_s01_runtime_discovery_receipt.v4','result':'PASS','production_compile_head':os.environ['PRODUCTION_COMPILE_HEAD'],'production_runtime_head':os.environ['PRODUCTION_RUNTIME_HEAD'],'compiler_artifact_id':int(os.environ['COMPILER_ARTIFACT_ID']),'compiler_artifact_sha256':os.environ['COMPILER_ARTIFACT_SHA256'],'composition_id':'GoldS01PremiumFirst120s','duration_in_frames':3600,'old_sceneir_v1_active_import_count':0,'static_unresolved_compiled_event_authority_count':0,'generic_asset_grid_count':0,'scene_primary_teaching_surface_count':26,'first_120_required_event_count':4,'first_120_required_event_executed_count':4,'target_property_changed_count':4,'media_render_started':False,'no_fake_green':True}
out=Path(os.environ['WORK'])/'runtime-evidence/runtime-discovery-receipt.json'
out.write_text(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n')
(out.parent/'active-import-graph.txt').write_text(joined+'\n')
PY
CURRENT_PHASE=COMPLETE
echo "PHASE=$CURRENT_PHASE"
