from __future__ import annotations

from pathlib import Path

source_path = Path(__file__).resolve().parent.parent / "final_pipeline_orchestrator_v2.py"
source = source_path.read_text(encoding="utf-8")
needle = "LEDGER_ISSUE = 377"
if source.count(needle) != 1:
    raise RuntimeError("ORCHESTRATOR_LEDGER_BINDING_NOT_UNIQUE")
source = source.replace(needle, "LEDGER_ISSUE = 376", 1)
namespace = {
    "__name__": "final_pipeline_orchestrator_v2_runtime",
    "__file__": str(source_path),
    "__package__": "",
}
exec(compile(source, str(source_path), "exec"), namespace, namespace)
