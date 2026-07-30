#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from .common import RunnerError, require_relpath, scan_sensitive, sha256_file


def file_set_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise RunnerError(f"ARTIFACT_DIRECTORY_MISSING:{root}")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RunnerError(f"ARTIFACT_SYMLINK_FORBIDDEN:{path}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            require_relpath(relative, "ARTIFACT_PATH_INVALID")
            data = path.read_bytes()
            scan_sensitive(relative, data)
            result[relative] = sha256_file(path)
    return result


def require_exact_file_set(observed: Mapping[str, str], expected: Iterable[str], code: str) -> None:
    expected_set = {require_relpath(item, f"{code}:PATH_INVALID") for item in expected}
    if set(observed) != expected_set:
        missing = sorted(expected_set - set(observed))
        extra = sorted(set(observed) - expected_set)
        raise RunnerError(f"{code}:missing={missing}:extra={extra}")


def write_sha256sums(root: Path, hashes: Mapping[str, str], path: str = "SHA256SUMS") -> None:
    filtered = {name: digest for name, digest in hashes.items() if name != path}
    content = "".join(f"{digest}  {name}\n" for name, digest in sorted(filtered.items()))
    (root / path).write_text(content, encoding="utf-8")


def build_human_review_queue(gates: list[Mapping[str, Any]]) -> dict[str, Any]:
    items = []
    for gate in gates:
        items.append({
            "gate_id": gate["gate_id"],
            "frame": gate["frame"],
            "scene_event": gate["scene_event"],
            "expected": gate["expected"],
            "observed": gate["observed"],
            "reviewer_action": gate["reviewer_action"],
            "status": "REVIEW_REQUIRED",
            "automatic_aesthetic_pass": False,
        })
    return {
        "schema_version": "gold_v2_runner_human_review_queue.v1",
        "result": "REVIEW_REQUIRED" if items else "NO_AESTHETIC_GATES_DECLARED",
        "automatic_aesthetic_pass": False,
        "items": items,
        "no_fake_green": True,
    }
