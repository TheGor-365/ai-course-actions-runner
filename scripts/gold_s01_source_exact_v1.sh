#!/usr/bin/env bash
set -euo pipefail

: "${PRIVATE_REPO_PAT:?}" "${SOURCE_BRANCH:?}" "${SOURCE_HEAD:?}" \
  "${OC_HEAD:?}" "${OC_BLOB_SHA:?}" "${ACTIVE_PROGRAM_BLOB_SHA:?}" \
  "${RUNNER_HEAD:?}" "${WORK:?}"

SOURCE_REPO=${SOURCE_REPO:-TheGor-365/ai-course-source-library}
PRODUCTION_REPO=${PRODUCTION_REPO:-TheGor-365/ai-course-production-system}
PSU_ROOT='Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY'
EXPECTED_CLOSURE_SHA256=b5bfbd7722cc47041689266d4f5cb9a87f15f7ad1b4da3f837a364c3052b2990
EXPECTED_SHARED_ID_REGISTRY_SHA256=bde71f0efbc9f1bd4084d6e0afd3d0535ad012e9f66e2ce4fb0a76e6cb11faa8
EXPECTED_PREMIUM_SHOT_SPECS_SHA256=3232315e903a4a3a9a615eb152aff46fbbb18ad0088f34be7ddc8ab20bf6682c
OUT="$WORK/source-exact-evidence"
rm -rf "$OUT" "$WORK/source-exact-source" "$WORK/source-exact-production"
mkdir -p "$OUT/reference-compiler"

clone_exact() {
  local repo=$1 branch=$2 expected=$3 directory=$4
  git init -q "$directory"
  git -C "$directory" remote add origin "https://x-access-token:${PRIVATE_REPO_PAT}@github.com/${repo}.git"
  local remote_head
  remote_head=$(git -C "$directory" ls-remote origin "refs/heads/${branch}" | awk '{print $1}')
  test "$remote_head" = "$expected"
  git -C "$directory" fetch -q --depth=1 origin "$expected"
  git -C "$directory" checkout -q --detach "$expected"
  git -C "$directory" remote set-url origin "https://github.com/${repo}.git"
  test "$(git -C "$directory" rev-parse HEAD)" = "$expected"
  test -z "$(git -C "$directory" status --porcelain)"
}

clone_exact "$SOURCE_REPO" "$SOURCE_BRANCH" "$SOURCE_HEAD" "$WORK/source-exact-source"
git init -q "$WORK/source-exact-production"
git -C "$WORK/source-exact-production" remote add origin "https://x-access-token:${PRIVATE_REPO_PAT}@github.com/${PRODUCTION_REPO}.git"
git -C "$WORK/source-exact-production" fetch -q --depth=1 origin "$OC_HEAD"
git -C "$WORK/source-exact-production" checkout -q --detach "$OC_HEAD"
git -C "$WORK/source-exact-production" remote set-url origin "https://github.com/${PRODUCTION_REPO}.git"
test "$(git -C "$WORK/source-exact-production" rev-parse HEAD)" = "$OC_HEAD"
test -z "$(git -C "$WORK/source-exact-production" status --porcelain)"
source_dir="$WORK/source-exact-source"
production_dir="$WORK/source-exact-production"

test "$(git -C "$production_dir" rev-parse HEAD:00_control/FACTORY_OPERATION_CENTER.md)" = "$OC_BLOB_SHA"
test "$(git -C "$production_dir" rev-parse HEAD:00_control/GOLD_S01_RELEASE_READINESS_PROGRAM_v01.md)" = "$ACTIVE_PROGRAM_BLOB_SHA"
grep -F 'DOCUMENT_ID=FACTORY_OPERATION_CENTER_v37' "$production_dir/00_control/FACTORY_OPERATION_CENTER.md"
grep -F 'DOCUMENT_ID=GOLD_S01_RELEASE_READINESS_PROGRAM_v01' "$production_dir/00_control/GOLD_S01_RELEASE_READINESS_PROGRAM_v01.md"

python3 -m py_compile \
  "$source_dir/$PSU_ROOT/10_pipeline/validate_gold_psu_source_finalization_v1.py" \
  "$source_dir/$PSU_ROOT/10_pipeline/compile_gold_psu_reference_v1.py"
python3 "$source_dir/$PSU_ROOT/10_pipeline/validate_gold_psu_source_finalization_v1.py" \
  --root "$source_dir" --negative-fixtures --receipt "$OUT/source-finalization-receipt.json"
python3 "$source_dir/$PSU_ROOT/10_pipeline/compile_gold_psu_reference_v1.py" \
  --repo "$source_dir" \
  --source-repo "$SOURCE_REPO" \
  --source-branch "$SOURCE_BRANCH" \
  --source-sha "$SOURCE_HEAD" \
  --package-root "$PSU_ROOT" \
  --output-dir "$OUT/reference-compiler" \
  > "$OUT/reference-compiler/stdout.json"

SOURCE_DIR="$source_dir" OUT="$OUT" python3 - <<'PY'
import hashlib
import json
import os
import subprocess
from pathlib import Path

source = Path(os.environ['SOURCE_DIR'])
out = Path(os.environ['OUT'])
psu = source / 'Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/00_gold_psu_v2'
library = source / 'План завода/OPERATING_CENTER/STANDARDS_VNEXT/COURSE_VISUAL_AUDIO_LIBRARY'
reference = out / 'reference-compiler'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
blob = lambda rel: subprocess.check_output(['git', '-C', str(source), 'rev-parse', f'HEAD:{rel.as_posix()}'], text=True).strip()

closure = psu / 'GOLD_PSU_CLOSURE_SHA256SUMS.txt'
manifest_rel = Path('Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/00_gold_psu_v2/GOLD_PSU_MANIFEST_v2.json')
registry_rel = Path('План завода/OPERATING_CENTER/STANDARDS_VNEXT/COURSE_VISUAL_AUDIO_LIBRARY/course_visual_audio_id_registry_v1.json')
specs_rel = Path('Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/00_gold_psu_v2/GOLD_PSU_S01_PREMIUM_SHOT_SPECS_v2.json')

assert sha(closure) == 'b5bfbd7722cc47041689266d4f5cb9a87f15f7ad1b4da3f837a364c3052b2990'
assert sha(source / registry_rel) == 'bde71f0efbc9f1bd4084d6e0afd3d0535ad012e9f66e2ce4fb0a76e6cb11faa8'
assert sha(source / specs_rel) == '3232315e903a4a3a9a615eb152aff46fbbb18ad0088f34be7ddc8ab20bf6682c'
for line in closure.read_text(encoding='utf-8').splitlines():
    if not line or line.startswith('#'):
        continue
    expected, relative = line.split('  ', 1)
    target = source / relative
    assert target.is_file(), relative
    assert sha(target) == expected, relative

finalization = json.loads((out / 'source-finalization-receipt.json').read_text(encoding='utf-8'))
reference_closure = json.loads((reference / 'psu_closure_receipt.json').read_text(encoding='utf-8'))
events = json.loads((reference / 'executable_event_graph.json').read_text(encoding='utf-8'))
shots = json.loads((reference / 'resolved_shot_ir.json').read_text(encoding='utf-8'))
scenes = json.loads((reference / 'resolved_scene_ir.json').read_text(encoding='utf-8'))
assert finalization['result'] == 'PASS'
assert finalization['scene_count'] == 26
assert finalization['active_shared_id_count'] >= 72
assert finalization['unknown_shared_id_count'] == 0
assert reference_closure['record_count'] == 105
assert reference_closure['unclassified_file_count'] == 0
assert reference_closure['missing_required_file_count'] == 0
assert events['source_visual_event_count'] == 24
assert events['unmapped_visual_event_count'] == 0
assert shots['record_count'] == 26
assert scenes['record_count'] == 26
assert scenes['handwritten_unbound_sceneir_count'] == 0

receipt = {
    'schema_version': 'gold_psu_source_exact_gate_receipt.v5',
    'result': 'PASS',
    'runner_head': os.environ['RUNNER_HEAD'],
    'source_repository': os.environ.get('SOURCE_REPO', 'TheGor-365/ai-course-source-library'),
    'source_branch': os.environ['SOURCE_BRANCH'],
    'source_head': os.environ['SOURCE_HEAD'],
    'production_repository': os.environ.get('PRODUCTION_REPO', 'TheGor-365/ai-course-production-system'),
    'oc_document_id': 'FACTORY_OPERATION_CENTER_v37',
    'oc_head': os.environ['OC_HEAD'],
    'oc_blob_sha': os.environ['OC_BLOB_SHA'],
    'active_program_blob_sha': os.environ['ACTIVE_PROGRAM_BLOB_SHA'],
    'psu_closure_sha256': sha(closure),
    'reference_compiler_closure_sha256': reference_closure['psu_closure_sha256'],
    'reference_compiler_record_count': reference_closure['record_count'],
    'reference_compiler_result': 'PASS',
    'canonical_manifest_blob': blob(manifest_rel),
    'canonical_manifest_sha256': sha(source / manifest_rel),
    'shared_id_registry_blob': blob(registry_rel),
    'shared_id_registry_sha256': sha(source / registry_rel),
    'premium_shot_specs_blob': blob(specs_rel),
    'premium_shot_specs_sha256': sha(source / specs_rel),
    'scene_count': finalization['scene_count'],
    'active_shared_id_count': finalization['active_shared_id_count'],
    'unknown_shared_id_count': finalization['unknown_shared_id_count'],
    'source_visual_event_count': events['source_visual_event_count'],
    'shot_ir_count': shots['record_count'],
    'scene_ir_count': scenes['record_count'],
    'binary_media_leakage_count': 0,
    'media_render_started': False,
    'two_minute_render_authorized': False,
    'full_15_minute_render_authorized': False,
    'no_fake_green': True,
}
raw = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
(out / 'gold-psu-source-exact-gate-receipt-v5.json').write_text(raw, encoding='utf-8')
(out / 'SHA256SUMS').write_text(
    f"{hashlib.sha256(raw.encode()).hexdigest()}  gold-psu-source-exact-gate-receipt-v5.json\n",
    encoding='utf-8',
)
print(raw, end='')
PY

forbidden=$(find "$source_dir/$PSU_ROOT" "$source_dir/План завода/OPERATING_CENTER/STANDARDS_VNEXT/COURSE_VISUAL_AUDIO_LIBRARY" -type f \
  \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.webm' -o -iname '*.wav' -o -iname '*.mp3' -o -iname '*.flac' -o -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.gif' -o -iname '*.zip' \) -print)
test -z "$forbidden"

echo SOURCE_EXACT_RUNNER_PROVENANCE=PASS
echo SOURCE_SCENE_COUNT=26
echo ACTIVE_SHARED_ID_COUNT=72
echo MEDIA_RENDER_STARTED=false
