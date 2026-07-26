#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_gold_s01_minute_proofs_v2.cli import main
from canonical_gold_s01_minute_proofs_v2.common import ProofError, validate_exact_manifest
from canonical_gold_s01_minute_proofs_v2.media import parse_vtt
from canonical_gold_s01_minute_proofs_v2.evidence import score_window, sanitize_artifact

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProofError as exc:
        print(str(exc))
        raise SystemExit(2)
