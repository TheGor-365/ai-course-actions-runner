#!/usr/bin/env python3
"""Gold S01 public media runner v2 with sanitized ffprobe filename."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import gold_s01_public_media_v1 as core

_ORIGINAL_FFPROBE = core.ffprobe


def sanitized_ffprobe(path: Path) -> dict[str, Any]:
    value = _ORIGINAL_FFPROBE(path)
    format_record = value.get("format")
    if isinstance(format_record, dict):
        format_record["filename"] = path.name
    return value


core.ffprobe = sanitized_ffprobe

if __name__ == "__main__":
    raise SystemExit(core.main())
