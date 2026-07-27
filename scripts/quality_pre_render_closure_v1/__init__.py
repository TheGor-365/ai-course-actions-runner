from __future__ import annotations

from pathlib import Path

source_path = Path(__file__).resolve().parent.parent / "quality_pre_render_closure_v1.py"
source = source_path.read_text(encoding="utf-8")nneedle = '''    if git("diff", "--cached", "--quiet", cwd=quality_dir) == "":
        pass
'''
if source.count(needle) != 1:
    raise RuntimeError("QUALITY_DIFF_CONTROL_PATCH_NOT_UNIQUE")
source = source.replace(needle, "", 1)
namespace = {
    "__name__": "quality_pre_render_closure_v1_runtime",
    "__file__": str(source_path),
    "__package__": "",
}
exec(compile(source, str(source_path), "exec"), namespace, namespace)
globals().update({key: value for key, value in namespace.items() if not key.startswith("__")})
