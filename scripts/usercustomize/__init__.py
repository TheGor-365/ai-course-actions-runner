from __future__ import annotations

import os
import sys
from pathlib import Path

ACTIVE = (
    os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
    and Path(sys.argv[0]).name == "materialize_caption_carrier_bridge_v1.py"
)

if ACTIVE:
    import final_pipeline_orchestrator_v2  # noqa: F401,E402
