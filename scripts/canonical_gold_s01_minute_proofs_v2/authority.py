from .common import *

def git_output(repo: Path, *args: str) -> str:
    return run(('git', *args), cwd=repo, capture=True)

def verify_checkout(repo: Path, expected: str, key: str) -> None:
    if not repo.is_dir():
        fail('CHECKOUT_MISSING', key)
    observed = git_output(repo, 'rev-parse', 'HEAD')
    if observed != expected:
        fail('CHECKOUT_HEAD_MISMATCH', f'{key}:{observed}')
    if git_output(repo, 'status', '--porcelain'):
        fail('CHECKOUT_DIRTY', key)

def verify_authority(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    source = Path(args.source_dir)
    production = Path(args.production_dir)
    verify_checkout(source, data['SOURCE_HEAD_RECONCILED'], 'source')
    verify_checkout(production, data['PRODUCTION_HEAD_RECONCILED'], 'production')
    run(('git', 'cat-file', '-e', f"{data['OC_HEAD']}^{{commit}}"), cwd=production)
    oc = git_output(production, 'show', f"{data['OC_HEAD']}:00_control/FACTORY_OPERATION_CENTER.md")
    program = git_output(production, 'show', f"{data['OC_HEAD']}:00_control/GOLD_PSU_PARALLEL_EXECUTION_PROGRAM_v01.md")
    if 'DOCUMENT_ID=FACTORY_OPERATION_CENTER_v35' not in oc:
        fail('OC_DOCUMENT_ID_MISMATCH')
    if 'OWNER_AUTHORITY_COMMENT=5085651807' not in oc or 'FULL_15_MINUTE_RENDER_AUTHORIZED=false' not in oc:
        fail('OC_POLICY_MISMATCH')
    if 'DOCUMENT_ID=GOLD_PSU_PARALLEL_EXECUTION_PROGRAM_v01' not in program:
        fail('PARALLEL_PROGRAM_MISMATCH')
    ancestry = {'A': ('source', data['SOURCE_HEAD_LANE_A'], data['SOURCE_HEAD_RECONCILED']), 'B': ('source', data['SOURCE_HEAD_LANE_B'], data['SOURCE_HEAD_RECONCILED']), 'C': ('production', data['PRODUCTION_HEAD_LANE_C'], data['PRODUCTION_HEAD_RECONCILED']), 'D': ('production', data['PRODUCTION_HEAD_LANE_D'], data['PRODUCTION_HEAD_RECONCILED']), 'E': ('production', data['PRODUCTION_HEAD_LANE_E'], data['PRODUCTION_HEAD_RECONCILED'])}
    for lane, (repo_name, head, reconciled) in ancestry.items():
        repo = source if repo_name == 'source' else production
        run(('git', 'merge-base', '--is-ancestor', head, reconciled), cwd=repo)
    observed_receipts: dict[str, Any] = {}
    for lane in REQUIRED_LANES:
        record = data['LANE_RECEIPTS'][lane]
        expected_head = ancestry[lane][1]
        if record['head'] != expected_head:
            fail('LANE_RECEIPT_DECLARED_HEAD_MISMATCH', lane)
        root = source if record['repository'] == 'source' else production
        receipt = root / safe_rel(record['path'], f'LANE_{lane}_RECEIPT_PATH')
        observed = sha256(receipt)
        if observed != record['sha256']:
            fail('LANE_RECEIPT_HASH_MISMATCH', lane)
        body = load_json(receipt)
        if not isinstance(body, dict) or body.get('FINAL_HEAD') != record['head']:
            fail('LANE_RECEIPT_HEAD_MISMATCH', lane)
        if body.get('NO_FAKE_GREEN') is not True:
            fail('LANE_RECEIPT_NO_FAKE_GREEN_MISSING', lane)
        if body.get('MAIN_MERGE_AUTHORIZED') is not False:
            fail('LANE_RECEIPT_MERGE_POLICY_MISMATCH', lane)
        if body.get('FULL_15_MINUTE_RENDER_AUTHORIZED') is not False:
            fail('LANE_RECEIPT_FULL_RENDER_POLICY_MISMATCH', lane)
        observed_receipts[lane] = {'path': record['path'], 'sha256': observed, 'head': record['head']}
    receipt = {'schema_version': 'canonical_gold_s01_authority_receipt.v2', 'status': 'PASS', 'OC_HEAD': data['OC_HEAD'], 'source_head': data['SOURCE_HEAD_RECONCILED'], 'production_head': data['PRODUCTION_HEAD_RECONCILED'], 'lane_receipts': observed_receipts, 'exact_head_reconciliation': True, 'full_15_minute_render_authorized': False, 'human_final_acceptance': False, 'no_fake_green': True}
    write_json(Path(args.receipt), receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0

def get_value(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    value = data
    for part in args.key.split('.'):
        if not isinstance(value, dict) or part not in value:
            fail('MANIFEST_KEY_MISSING', args.key)
        value = value[part]
    if value is None:
        fail('MANIFEST_KEY_PROVISIONAL', args.key)
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    elif isinstance(value, bool):
        print(str(value).lower())
    else:
        print(value)
    return 0

def bridge(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    production = Path(args.production_dir)
    bridge_path = production / safe_rel(data['PRODUCTION_BRIDGE_PATH'], 'PRODUCTION_BRIDGE_PATH')
    if sha256(bridge_path) != data['PRODUCTION_BRIDGE_SHA256']:
        fail('PRODUCTION_BRIDGE_HASH_MISMATCH')
    argv = [sys.executable, bridge_path.as_posix(), '--stage', args.stage, '--source-dir', Path(args.source_dir).as_posix(), '--production-dir', production.as_posix(), '--compiled-dir', Path(args.compiled_dir).as_posix(), '--receipt-dir', Path(args.receipt_dir).as_posix()]
    if args.output_dir:
        argv.extend(('--output-dir', Path(args.output_dir).as_posix()))
    run(argv)
    return 0

def verify_identity(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    validate_exact_manifest(data)
    if args.key not in data['IDENTITY_BINDINGS']:
        fail('IDENTITY_BINDING_KEY_INVALID', args.key)
    record = data['IDENTITY_BINDINGS'][args.key]
    roots = {'source': Path(args.source_dir), 'production': Path(args.production_dir), 'compiled': Path(args.compiled_dir)}
    path = roots[record['root']] / safe_rel(record['path'], f'{args.key}_PATH')
    observed = sha256(path)
    if observed != data[args.key]:
        fail('IDENTITY_HASH_MISMATCH', args.key)
    print(json.dumps({'key': args.key, 'path': record['path'], 'sha256': observed}, sort_keys=True))
    return 0

def verify_audio(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    audio = Path(args.audio)
    observed = sha256(audio)
    size = audio.stat().st_size
    expected = data['A3483']
    if observed != expected['sha256'] or size != expected['size']:
        fail('A3483_IDENTITY_MISMATCH')
    receipt = {'schema_version': 'canonical_gold_s01_audio_identity.v2', 'asset': expected['asset'], 'release_tag': expected['tag'], 'size': size, 'sha256': observed, 'A3483_identity_verified': True, 'no_fake_green': True}
    write_json(Path(args.receipt), receipt)
    return 0
