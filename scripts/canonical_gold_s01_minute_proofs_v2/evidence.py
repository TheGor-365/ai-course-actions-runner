from .common import *

def event_records(path: Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    if isinstance(payload, dict):
        payload = payload.get('events')
    if not isinstance(payload, list):
        fail('EVENT_PLAN_LIST_REQUIRED')
    events = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        start = item.get('start_ms')
        end = item.get('end_ms', start)
        effect = item.get('effect_id', item.get('event_type', item.get('handler_id')))
        if isinstance(start, int) and isinstance(end, int) and isinstance(effect, str):
            events.append({'start_ms': start, 'end_ms': max(start + 1, end), 'effect': effect})
    if not events:
        fail('EVENT_PLAN_EMPTY')
    return events

def score_window(events: Sequence[Mapping[str, Any]], start: int) -> tuple[int, int, int]:
    end = start + 60000
    overlapping = [e for e in events if e['end_ms'] > start and e['start_ms'] < end]
    distinct = {effect for effect in REQUIRED_EFFECTS if any((effect in e['effect'] for e in overlapping))}
    return (len(distinct), len(overlapping), -start)

def verify_pilot_b_selection(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    events = event_records(Path(args.events))
    selection = load_json(Path(args.selection))
    if not isinstance(selection, dict):
        fail('PILOT_B_SELECTION_OBJECT_REQUIRED')
    declared = selection.get('start_ms')
    if not isinstance(declared, int) or selection.get('end_ms') != declared + 60000:
        fail('PILOT_B_SELECTION_DURATION_INVALID')
    max_end = max((e['end_ms'] for e in events))
    candidates = sorted({0, *(e['start_ms'] for e in events if e['start_ms'] + 60000 <= max_end)})
    if not candidates:
        fail('PILOT_B_CANDIDATE_MISSING')
    expected = max(candidates, key=lambda start: score_window(events, start))
    if declared != expected:
        fail('PILOT_B_SELECTION_ALGORITHM_MISMATCH', f'{declared}!={expected}')
    distinct, count, _ = score_window(events, declared)
    receipt = {'schema_version': 'canonical_gold_s01_pilot_b_selection.v2', 'start_ms': declared, 'end_ms': declared + 60000, 'duration_ms': 60000, 'distinct_required_effect_count': distinct, 'event_count': count, 'selection_verified': True, 'contiguous': True, 'no_fake_green': True}
    write_json(Path(args.receipt), receipt)
    return 0

def package(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    pilot_dir, receipt_dir = (Path(args.pilot_dir), Path(args.receipt_dir))
    mp4s = list(pilot_dir.glob('*.mp4'))
    if len(mp4s) != 1:
        fail('CANONICAL_MP4_COUNT_INVALID', str(len(mp4s)))
    required = ('contact_sheet.png', 'machine_QC.json', 'event_telemetry_summary.json', 'compiler_receipt.json', 'runtime_receipt.json', 'audio_window_receipt.json', 'caption_window_receipt.json', 'ffprobe.json')
    missing = [name for name in required if not (pilot_dir / name).is_file()]
    if missing:
        fail('OWNER_ARTIFACT_FILE_MISSING', ','.join(missing))
    if not list(receipt_dir.glob('*.json')):
        fail('RUN_RECEIPTS_MISSING')
    machine_qc = load_json(pilot_dir / 'machine_QC.json')
    telemetry = load_json(pilot_dir / 'event_telemetry_summary.json')
    if not isinstance(machine_qc, dict) or not isinstance(telemetry, dict):
        fail('QC_RECEIPT_OBJECT_REQUIRED')
    if machine_qc.get('premium_qc_green') is not True:
        fail('PREMIUM_QC_NOT_GREEN', args.pilot)
    required_gate = 'event_qc_green' if args.pilot == 'pilot_a' else 'code_event_qc_green'
    if machine_qc.get(required_gate) is not True:
        fail('EVENT_QC_NOT_GREEN', args.pilot)
    if machine_qc.get('audio_present') is not True or machine_qc.get('captions_present') is not True:
        fail('PILOT_MEDIA_QC_NOT_GREEN', args.pilot)
    if telemetry.get('telemetry_complete') is not True or telemetry.get('ignored_event_count') != 0:
        fail('EVENT_TELEMETRY_INCOMPLETE', args.pilot)
    manifest_body = {'schema_version': 'canonical_gold_s01_owner_review_manifest.v2', 'pilot': args.pilot, 'media_file': mp4s[0].name, 'media_sha256': sha256(mp4s[0]), 'contact_sheet_sha256': sha256(pilot_dir / 'contact_sheet.png'), 'machine_QC_sha256': sha256(pilot_dir / 'machine_QC.json'), 'event_telemetry_summary_sha256': sha256(pilot_dir / 'event_telemetry_summary.json'), 'compiler_receipt_sha256': sha256(pilot_dir / 'compiler_receipt.json'), 'runtime_receipt_sha256': sha256(pilot_dir / 'runtime_receipt.json'), 'audio_window_receipt_sha256': sha256(pilot_dir / 'audio_window_receipt.json'), 'caption_window_receipt_sha256': sha256(pilot_dir / 'caption_window_receipt.json'), 'ffprobe_sha256': sha256(pilot_dir / 'ffprobe.json'), 'source_head': data['SOURCE_HEAD_RECONCILED'], 'production_head': data['PRODUCTION_HEAD_RECONCILED'], 'OC_HEAD': data['OC_HEAD'], 'full_15_minute_rendered': False, 'human_final_acceptance': False, 'no_fake_green': True}
    write_json(pilot_dir / 'owner_review_manifest.json', manifest_body)
    sums = []
    for path in sorted(pilot_dir.iterdir()):
        if path.is_file() and path.name != 'SHA256SUMS':
            sums.append(f'{sha256(path)}  {path.name}')
    (pilot_dir / 'SHA256SUMS').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    return 0

def verify_artifact(args: argparse.Namespace) -> int:
    root, expected_path = (Path(args.artifact_dir), Path(args.expected))
    expected = load_json(expected_path)
    mp4s = list(root.rglob('*.mp4'))
    if len(mp4s) != 1:
        fail('DOWNLOADED_MP4_COUNT_INVALID', str(len(mp4s)))
    observed = sha256(mp4s[0])
    if expected.get('media_sha256') != observed:
        fail('PUBLIC_ARTIFACT_DOWNLOAD_HASH_MISMATCH')
    receipt = {'schema_version': 'canonical_gold_s01_public_artifact_identity.v2', 'media_sha256': observed, 'public_artifact_download_hash_verified': True, 'mp4_count': 1, 'full_15_minute_rendered': False, 'human_final_acceptance': False, 'no_fake_green': True}
    write_json(Path(args.receipt), receipt)
    return 0

def sanitize_artifact(args: argparse.Namespace) -> int:
    root = Path(args.artifact_dir)
    if not root.is_dir():
        fail('ARTIFACT_DIR_MISSING')
    forbidden_suffixes = {'.zip', '.tar', '.tgz', '.gz', '.7z', '.rar'}
    forbidden_names = {'.git', '.env', 'id_rsa', 'id_ed25519'}
    secret_pattern = re.compile(b'(BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/)')
    for path in root.rglob('*'):
        if path.name in forbidden_names or any((part == '.git' for part in path.parts)):
            fail('FORBIDDEN_ARTIFACT_PATH', path.name)
        if not path.is_file():
            continue
        if path.suffix.lower() in forbidden_suffixes:
            fail('PRIVATE_ARCHIVE_OR_RAW_BUNDLE_FORBIDDEN', path.name)
        if path.stat().st_size <= 10 * 1024 * 1024:
            data = path.read_bytes()
            if secret_pattern.search(data):
                fail('SECRET_OR_PRIVATE_PATH_IN_ARTIFACT', path.name)
    mp4s = list(root.glob('*.mp4'))
    if len(mp4s) != 1:
        fail('CANONICAL_MP4_COUNT_INVALID', str(len(mp4s)))
    return 0

def upstream_targets(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    for target in data['UPSTREAM_PR_TARGETS']:
        print(f"{target['repository']}|{target['pr_number']}")
    return 0

def final_summary(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    receipts = Path(args.receipt_dir)
    a = load_json(receipts / '29_pilot_a_identity.json')
    b = load_json(receipts / '29_pilot_b_identity.json')
    if a.get('public_artifact_download_hash_verified') is not True:
        fail('PILOT_A_IDENTITY_NOT_VERIFIED')
    if b.get('public_artifact_download_hash_verified') is not True:
        fail('PILOT_B_IDENTITY_NOT_VERIFIED')
    text = f"## Canonical Gold S01 minute proof receipt\n\n```text\nWORK_ORDER_ID=RWO-M1-L01-S01-PUBLIC-RUNNER-MINUTE-PROOFS-002\nRUN_ID={args.run_id}\nJOB_ID={args.job_id}\nPILOT_A_ARTIFACT_ID={args.artifact_a}\nPILOT_B_ARTIFACT_ID={args.artifact_b}\nSOURCE_HEAD={data['SOURCE_HEAD_RECONCILED']}\nPRODUCTION_HEAD={data['PRODUCTION_HEAD_RECONCILED']}\nPILOT_A_MP4_SHA256={a['media_sha256']}\nPILOT_B_MP4_SHA256={b['media_sha256']}\nPUBLIC_ARTIFACT_DOWNLOAD_HASH_VERIFIED=true\nOWNER_REVIEW_PACKAGE_READY=true\nHUMAN_FINAL_ACCEPTANCE=false\nFULL_15_MINUTE_RENDERED=false\nNO_FAKE_GREEN=true\n```\n"
    print(text)
    return 0
