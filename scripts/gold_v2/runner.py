#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.gold_v2.common import MODES, RunnerError, require_sha40
    from scripts.gold_v2.pipeline import GoldV2Pipeline
else:
    from .common import MODES, RunnerError, require_sha40
    from .pipeline import GoldV2Pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fail-closed Gold V2 one-command execution/evidence runner")
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--authorization-manifest", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--single-use-ledger", type=Path)
    return parser


def execution_head() -> str:
    root = Path(__file__).resolve().parents[2]
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RunnerError("EXECUTION_RUNNER_GIT_CHECKOUT_REQUIRED") from exc
    if dirty:
        raise RunnerError("EXECUTION_RUNNER_TREE_DIRTY")
    return require_sha40(head, "EXECUTION_RUNNER_HEAD_INVALID")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = GoldV2Pipeline(
            manifest_path=args.authorization_manifest,
            mode=args.mode,
            workspace=args.workspace,
            single_use_ledger=args.single_use_ledger,
            execution_runner_head=execution_head(),
        ).run()
    except RunnerError as exc:
        print(f"BLOCKED:{str(exc).split(':', 1)[0]}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"BLOCKED:UNEXPECTED_{type(exc).__name__.upper()}", file=sys.stderr)
        return 3
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
