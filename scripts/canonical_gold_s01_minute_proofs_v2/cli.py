from .common import ProofError, argparse
from .authority import get_value, verify_authority, bridge, verify_identity, verify_audio
from .media import verify_captions, caption_window, extract_audio
from .evidence import verify_pilot_b_selection, package, verify_artifact, sanitize_artifact, upstream_targets, final_summary

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('get'); p.add_argument('--manifest', required=True); p.add_argument('--key', required=True); p.set_defaults(func=get_value)
    p = sub.add_parser('verify-authority'); p.add_argument('--manifest', required=True); p.add_argument('--source-dir', required=True); p.add_argument('--production-dir', required=True); p.add_argument('--receipt', required=True); p.set_defaults(func=verify_authority)
    p = sub.add_parser('bridge'); p.add_argument('--manifest', required=True); p.add_argument('--stage', required=True); p.add_argument('--source-dir', required=True); p.add_argument('--production-dir', required=True); p.add_argument('--compiled-dir', required=True); p.add_argument('--receipt-dir', required=True); p.add_argument('--output-dir'); p.set_defaults(func=bridge)
    p = sub.add_parser('verify-identity'); p.add_argument('--manifest', required=True); p.add_argument('--key', required=True); p.add_argument('--source-dir', required=True); p.add_argument('--production-dir', required=True); p.add_argument('--compiled-dir', required=True); p.set_defaults(func=verify_identity)
    p = sub.add_parser('verify-audio'); p.add_argument('--manifest', required=True); p.add_argument('--audio', required=True); p.add_argument('--receipt', required=True); p.set_defaults(func=verify_audio)
    p = sub.add_parser('verify-captions'); p.add_argument('--manifest', required=True); p.add_argument('--json', required=True); p.add_argument('--vtt', required=True); p.add_argument('--receipt', required=True); p.set_defaults(func=verify_captions)
    p = sub.add_parser('caption-window'); p.add_argument('--manifest', required=True); p.add_argument('--pilot', choices=('pilot_a', 'pilot_b'), required=True); p.add_argument('--selection'); p.add_argument('--json', required=True); p.add_argument('--vtt', required=True); p.add_argument('--output-dir', required=True); p.set_defaults(func=caption_window)
    p = sub.add_parser('extract-audio'); p.add_argument('--audio', required=True); p.add_argument('--start-ms', required=True, type=int); p.add_argument('--duration-ms', required=True, type=int); p.add_argument('--output', required=True); p.add_argument('--receipt', required=True); p.set_defaults(func=extract_audio)
    p = sub.add_parser('verify-pilot-b-selection'); p.add_argument('--manifest', required=True); p.add_argument('--events', required=True); p.add_argument('--selection', required=True); p.add_argument('--receipt', required=True); p.set_defaults(func=verify_pilot_b_selection)
    p = sub.add_parser('package'); p.add_argument('--manifest', required=True); p.add_argument('--pilot', choices=('pilot_a', 'pilot_b'), required=True); p.add_argument('--pilot-dir', required=True); p.add_argument('--receipt-dir', required=True); p.set_defaults(func=package)
    p = sub.add_parser('verify-artifact'); p.add_argument('--artifact-dir', required=True); p.add_argument('--expected', required=True); p.add_argument('--receipt', required=True); p.set_defaults(func=verify_artifact)
    p = sub.add_parser('sanitize-artifact'); p.add_argument('--artifact-dir', required=True); p.set_defaults(func=sanitize_artifact)
    p = sub.add_parser('upstream-targets'); p.add_argument('--manifest', required=True); p.set_defaults(func=upstream_targets)
    p = sub.add_parser('final-summary'); p.add_argument('--manifest', required=True); p.add_argument('--run-id', required=True); p.add_argument('--job-id', required=True); p.add_argument('--artifact-a', required=True); p.add_argument('--artifact-b', required=True); p.add_argument('--receipt-dir', required=True); p.set_defaults(func=final_summary)
    return parser

def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ProofError as exc:
        print(str(exc))
        raise SystemExit(2)
