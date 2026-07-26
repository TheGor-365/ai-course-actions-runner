from .common import *

def parse_vtt_timestamp(value: str) -> int:
    parts = value.strip().split(':')
    if len(parts) == 2:
        hours = 0
        minutes, seconds = parts
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        fail('VTT_TIMESTAMP_INVALID', value)
    sec, millis = seconds.replace(',', '.').split('.')
    return ((int(hours) * 60 + int(minutes)) * 60 + int(sec)) * 1000 + int(millis.ljust(3, '0')[:3])

def format_vtt_timestamp(ms: int) -> str:
    ms = max(0, int(ms))
    hours, rest = divmod(ms, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, millis = divmod(rest, 1000)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}'

def parse_vtt(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding='utf-8-sig')
    if not text.startswith('WEBVTT'):
        fail('ACCEPTED_CAPTION_VTT_INVALID')
    blocks = re.split('\\r?\\n\\r?\\n+', text.strip())
    cues: list[dict[str, Any]] = []
    timing = re.compile('(?P<start>(?:\\d{2}:)?\\d{2}:\\d{2}[.,]\\d{3})\\s+-->\\s+(?P<end>(?:\\d{2}:)?\\d{2}:\\d{2}[.,]\\d{3})(?:\\s+.*)?$')
    for block in blocks[1:]:
        lines = block.splitlines()
        idx = 0
        if lines and '-->' not in lines[0]:
            idx = 1
        if idx >= len(lines):
            continue
        match = timing.match(lines[idx].strip())
        if not match:
            fail('VTT_CUE_TIMING_INVALID', hashlib.sha256(block.encode()).hexdigest())
        cues.append({'start_ms': parse_vtt_timestamp(match.group('start')), 'end_ms': parse_vtt_timestamp(match.group('end')), 'text': '\n'.join(lines[idx + 1:])})
    if not cues:
        fail('VTT_CUES_MISSING')
    return cues

def verify_captions(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    json_path, vtt_path = (Path(args.json), Path(args.vtt))
    json_hash, vtt_hash = (sha256(json_path), sha256(vtt_path))
    if json_hash != data['CAPTION_JSON_SHA256']:
        fail('ACCEPTED_CAPTION_JSON_HASH_MISMATCH')
    if vtt_hash != data['CAPTION_VTT_SHA256']:
        fail('ACCEPTED_CAPTION_VTT_HASH_MISMATCH')
    payload = load_json(json_path)
    cues = parse_vtt(vtt_path)
    receipt = {'schema_version': 'canonical_gold_s01_caption_identity.v2', 'caption_json_sha256': json_hash, 'caption_vtt_sha256': vtt_hash, 'json_type': type(payload).__name__, 'vtt_cue_count': len(cues), 'accepted_caption_json_materialized': True, 'accepted_caption_vtt_materialized': True, 'draft_srt_fallback_used': False, 'silent_regeneration_used': False, 'no_fake_green': True}
    write_json(Path(args.receipt), receipt)
    return 0

def caption_entries(payload: Any) -> list[dict[str, Any]]:
    candidates: Any = payload
    if isinstance(payload, dict):
        for key in ('captions', 'blocks', 'items', 'segments', 'cues'):
            if isinstance(payload.get(key), list):
                candidates = payload[key]
                break
    if not isinstance(candidates, list):
        fail('CAPTION_JSON_LIST_NOT_FOUND')
    result = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        start = item.get('start_ms', item.get('start'))
        end = item.get('end_ms', item.get('end'))
        text = item.get('text', item.get('caption', item.get('content')))
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and isinstance(text, str):
            if 'start_ms' not in item:
                start = round(float(start) * 1000)
            if 'end_ms' not in item:
                end = round(float(end) * 1000)
            result.append({'start_ms': int(start), 'end_ms': int(end), 'text': text})
    if not result:
        fail('CAPTION_JSON_CUES_MISSING')
    return result

def resolve_window(data: Mapping[str, Any], pilot: str, selection: Path | None) -> tuple[int, int]:
    if pilot == 'pilot_a':
        return (0, 60000)
    if pilot != 'pilot_b' or selection is None:
        fail('PILOT_WINDOW_INVALID', pilot)
    selected = load_json(selection)
    if not isinstance(selected, dict):
        fail('PILOT_B_SELECTION_OBJECT_REQUIRED')
    start = selected.get('start_ms')
    end = selected.get('end_ms')
    if not isinstance(start, int) or end != start + 60000:
        fail('PILOT_B_SELECTION_DURATION_INVALID')
    return (start, end)

def caption_window(args: argparse.Namespace) -> int:
    data = manifest(Path(args.manifest))
    start, end = resolve_window(data, args.pilot, Path(args.selection) if args.selection else None)
    json_entries = caption_entries(load_json(Path(args.json)))
    vtt_entries = parse_vtt(Path(args.vtt))
    selected_json = [c for c in json_entries if c['end_ms'] > start and c['start_ms'] < end]
    selected_vtt = [c for c in vtt_entries if c['end_ms'] > start and c['start_ms'] < end]
    if not selected_json or not selected_vtt:
        fail('CAPTION_WINDOW_EMPTY', args.pilot)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    normalized = []
    for cue in selected_json:
        normalized.append({**cue, 'start_ms': max(0, cue['start_ms'] - start), 'end_ms': min(60000, cue['end_ms'] - start)})
    write_json(out / 'caption_window.json', {'pilot': args.pilot, 'start_ms': start, 'end_ms': end, 'captions': normalized})
    lines = ['WEBVTT', '']
    for idx, cue in enumerate(selected_vtt, 1):
        cue_start = max(start, cue['start_ms']) - start
        cue_end = min(end, cue['end_ms']) - start
        lines.extend((str(idx), f'{format_vtt_timestamp(cue_start)} --> {format_vtt_timestamp(cue_end)}', cue['text'], ''))
    (out / 'caption_window.vtt').write_text('\n'.join(lines), encoding='utf-8')
    receipt = {'schema_version': 'canonical_gold_s01_caption_window.v2', 'pilot': args.pilot, 'source_start_ms': start, 'source_end_ms': end, 'duration_ms': 60000, 'json_cue_count': len(selected_json), 'vtt_cue_count': len(selected_vtt), 'caption_window_json_sha256': sha256(out / 'caption_window.json'), 'caption_window_vtt_sha256': sha256(out / 'caption_window.vtt'), 'contiguous': True, 'no_fake_green': True}
    write_json(out / 'caption_window_receipt.json', receipt)
    return 0

def extract_audio(args: argparse.Namespace) -> int:
    audio, output = (Path(args.audio), Path(args.output))
    start_ms, duration_ms = (int(args.start_ms), int(args.duration_ms))
    if start_ms < 0 or duration_ms != 60000:
        fail('AUDIO_WINDOW_INVALID')
    output.parent.mkdir(parents=True, exist_ok=True)
    run(('ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', f'{start_ms / 1000:.3f}', '-t', f'{duration_ms / 1000:.3f}', '-i', audio.as_posix(), '-c:a', 'pcm_s24le', output.as_posix()))
    receipt = {'schema_version': 'canonical_gold_s01_audio_window.v2', 'source_audio_sha256': sha256(audio), 'start_ms': start_ms, 'end_ms': start_ms + duration_ms, 'duration_ms': duration_ms, 'audio_window_sha256': sha256(output), 'audio_present': output.stat().st_size > 0, 'contiguous': True, 'no_fake_green': True}
    write_json(Path(args.receipt), receipt)
    return 0
