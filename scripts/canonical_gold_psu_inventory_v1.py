#!/usr/bin/env python3
"""Build a sanitized, content-addressed inventory for the canonical Gold PSU.

The output contains repository paths, Git blob identities, SHA-256 digests and
sizes only. It never emits source file contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Iterable

PACKAGE_ROOT = Path("Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY")
EXTERNAL_FILES = [
    Path("Module 1/Lesson 1/02_voiceover/reference_narration_anchor_map_v01.json"),
    Path("Module 1/Lesson 1/04_visual/lesson_visual_bible_v1.json"),
    Path("Module 1/Lesson 1/04_visual/lesson_visual_bible_v2.json"),
    Path("Module 1/Lesson 1/04_visual/lesson_asset_registry_v1.json"),
    Path("Module 1/Lesson 1/04_visual/reference_shot_ir_spec_plan_v01.json"),
    Path("Module 1/Lesson 1/04_visual/reference_shot_ir_spec_plan_v01_binding_amendment_v01.json"),
    Path("Module 1/Lesson 1/04_visual/reference_technical_truth_authority_map_v01.json"),
    Path("Module 1/Lesson 1/04_visual/hybrid_psu_contracts_v1.json"),
    Path("Module 1/Lesson 1/04_visual/s01_hybrid_reference_psu_v1.json"),
    Path("Module 1/Lesson 1/04_visual/s01_hybrid_reference_units_v1.json"),
    Path("Module 1/Lesson 1/04_visual/s01_hybrid_reference_scenes_shard_01_v1.json"),
    Path("Module 1/Lesson 1/04_visual/s01_hybrid_reference_scenes_shard_02_v1.json"),
    Path("Module 1/Lesson 1/04_visual/s01_hybrid_reference_scenes_shard_03_v1.json"),
    Path("Module 1/Lesson 1/04_visual/s01_hybrid_reference_scenes_shard_04_v1.json"),
    Path("План завода/OPERATING_CENTER/REPAIR/M1_L01/M1_L01_FULL_LESSON_VISUAL_GOLD_REPAIR_CONTRACT_v01.md"),
    Path("План завода/OPERATING_CENTER/REPAIR/M1_L01/M1_L01_FULL_LESSON_VISUAL_GOLD_EXECUTOR_WORK_ORDER_v01.md"),
    Path("План завода/OPERATING_CENTER/REPAIR/M1_L01/M1_L01_FULL_LESSON_VISUAL_TREATMENT_MATRIX_v01.json"),
    Path("План завода/OPERATING_CENTER/REPAIR/M1_L01/M1_L01_VISUAL_REFERENCE_SPINE_v01.json"),
    Path("План завода/OPERATING_CENTER/STANDARDS_VNEXT/VISUAL_SCENE_COMPILER_V2_RUNTIME_IDENTITY_CONTRACT_v01.json"),
    Path("План завода/OPERATING_CENTER/HYBRID_VISUAL_GOLD_V2_LEGACY_MAP_v01.json"),
    Path("План завода/OPERATING_CENTER/HYBRID_VISUAL_GOLD_V2_SCHEMA_INDEX_v01.json"),
]
EXTERNAL_DIRS = [
    Path("План завода/OPERATING_CENTER/STANDARDS_VNEXT/SCHEMAS/VISUAL_GOLD"),
    Path("План завода/OPERATING_CENTER/VALIDATORS/M1_L01"),
]


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def tracked_files(repo: Path, root: Path) -> list[Path]:
    output = git(repo, "ls-files", "--", root.as_posix())
    return [Path(line) for line in output.splitlines() if line]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify(path: Path, in_package: bool) -> str:
    text = path.as_posix()
    if "/09_quality/" in text or "/10_pipeline/before_after_" in text or text.endswith("validators_not_run.txt"):
        return "EVIDENCE_ONLY"
    if text.endswith("import_manifest_draft.json") or text.endswith("package_manifest.json"):
        return "LEGACY_WITH_SUCCESSOR"
    if text.endswith("99_manifest.txt"):
        return "LEGACY_WITH_SUCCESSOR"
    if "/10_pipeline/" in text and path.suffix == ".py":
        return "REQUIRED_EXECUTABLE_INPUT"
    if in_package and ("/03_timeline/" in text or "/04_visual/" in text or "/02_voiceover/" in text):
        return "REQUIRED_EXECUTABLE_INPUT"
    if in_package:
        return "REQUIRED_AUTHORITY"
    if "/fixtures/" in text:
        return "EVIDENCE_ONLY"
    if "/VALIDATORS/" in text:
        return "REQUIRED_EXECUTABLE_INPUT"
    return "REQUIRED_AUTHORITY"


def record(repo: Path, source_repo: str, source_sha: str, path: Path, in_package: bool) -> dict:
    absolute = repo / path
    if not absolute.is_file():
        raise FileNotFoundError(path)
    return {
        "repository": source_repo,
        "source_commit": source_sha,
        "path": path.as_posix(),
        "git_blob_sha": git(repo, "rev-parse", f"HEAD:{path.as_posix()}"),
        "content_sha256": sha256(absolute),
        "size_bytes": absolute.stat().st_size,
        "classification_seed": classify(path, in_package),
        "scope": "PACKAGE_CLOSURE" if in_package else "EXTERNAL_NORMATIVE_DEPENDENCY",
    }


def unique_paths(paths: Iterable[Path]) -> list[Path]:
    return sorted(set(paths), key=lambda item: item.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    observed_head = git(repo, "rev-parse", "HEAD")
    if observed_head != args.source_sha:
        raise SystemExit(f"SOURCE_HEAD_MISMATCH:{observed_head}")

    package_files = tracked_files(repo, PACKAGE_ROOT)
    external_paths = list(EXTERNAL_FILES)
    for directory in EXTERNAL_DIRS:
        external_paths.extend(tracked_files(repo, directory))
    external_paths = unique_paths(external_paths)

    records = [record(repo, args.source_repo, args.source_sha, p, True) for p in package_files]
    records.extend(record(repo, args.source_repo, args.source_sha, p, False) for p in external_paths)
    records.sort(key=lambda item: (item["scope"], item["path"]))

    payload = {
        "schema_version": "canonical_gold_psu_inventory.v1",
        "source_repository": args.source_repo,
        "source_commit": args.source_sha,
        "canonical_psu_root": PACKAGE_ROOT.as_posix(),
        "package_file_count": len(package_files),
        "external_dependency_file_count": len(external_paths),
        "record_count": len(records),
        "records": records,
        "private_content_included": False,
        "no_fake_green": True,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    args.output.write_text(canonical, encoding="utf-8")
    print(f"PACKAGE_FILE_COUNT={len(package_files)}")
    print(f"EXTERNAL_DEPENDENCY_FILE_COUNT={len(external_paths)}")
    print(f"INVENTORY_SHA256={hashlib.sha256(canonical.encode('utf-8')).hexdigest()}")
    print("PRIVATE_CONTENT_INCLUDED=false")
    print("NO_FAKE_GREEN=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
