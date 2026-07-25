#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CONTENT_ROOT = Path("Module 1/Lesson 1/launch_5d/content_semantics")
CANONICAL_RU = Path(
    "Module 1/Lesson 1/1/M1-L01-S01_0000-1500_PRODUCTION_READY/"
    "02_voiceover/voiceover_segments_ru.json"
)


class GateError(RuntimeError):
    pass


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError("json_root_not_object")
    return value


def run_fixed(name: str, command: list[str], cwd: Path, timeout: int = 180) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=timeout,
    )
    if completed.returncode == 0:
        return
    diagnostic_hash = hashlib.sha256(
        completed.stdout.encode("utf-8", errors="replace")
    ).hexdigest()
    print("gate_id=CONTENT_SEMANTICS_LAUNCH_GATE")
    print("result=FAIL")
    print("error_class=content_semantics_validator_failure")
    print(f"failed_step={name}")
    print(f"diagnostic_hash={diagnostic_hash}")
    print("private_content_printed=false")
    raise SystemExit(1)


def run_gate(private: Path) -> int:
    if not (private / ".git").is_dir():
        raise GateError("private_checkout_missing")

    base = private / CONTENT_ROOT
    required = [
        "HANDOFF_v1.json",
        "M1-L01-S02_immutable_blind_request_v1.json",
        "M1-L01-S02_factory_request_v1.json",
        "M1-L01-S02_factory_source_manifest_v1.json",
        "S01_audio_authority_mapping_v1.json",
        "audio_authority_connector_attestation_v1.json",
        "shotir_freeze_reconciliation_v1.json",
        "factory_core_reconciliation_v1.json",
        "connector_preflight_attestation_v1.json",
        "build_content_semantics_handoff_v2.py",
        "build_ru_caption_source.py",
        "validate_content_semantics.py",
        "validate_policy_bindings.py",
        "validate_factory_request_bridge.py",
        "validate_audio_authority_mapping.py",
        "validate_factory_core_reconciliation.py",
        "validate_shotir_freeze_reconciliation.py",
        "validate_ru_caption_source.py",
        "test_validate_content_semantics.py",
        "test_build_content_semantics_handoff_v2.py",
    ]
    missing = sorted(name for name in required if not (base / name).is_file())
    if missing:
        print("gate_id=CONTENT_SEMANTICS_LAUNCH_GATE")
        print("result=FAIL")
        print("error_class=missing_required_file")
        print(f"missing_file_count={len(missing)}")
        print(
            "missing_set_hash="
            + hashlib.sha256(",".join(missing).encode("utf-8")).hexdigest()
        )
        print("private_content_printed=false")
        return 1

    if not (private / CANONICAL_RU).is_file():
        print("gate_id=CONTENT_SEMANTICS_LAUNCH_GATE")
        print("result=FAIL")
        print("error_class=missing_canonical_source")
        print("private_content_printed=false")
        return 1

    scripts = [
        str(CONTENT_ROOT / name)
        for name in (
            "build_content_semantics_handoff_v2.py",
            "build_ru_caption_source.py",
            "validate_content_semantics.py",
            "validate_policy_bindings.py",
            "validate_factory_request_bridge.py",
            "validate_audio_authority_mapping.py",
            "validate_factory_core_reconciliation.py",
            "validate_shotir_freeze_reconciliation.py",
            "validate_ru_caption_source.py",
            "test_validate_content_semantics.py",
            "test_build_content_semantics_handoff_v2.py",
        )
    ]

    with tempfile.TemporaryDirectory(prefix="content-semantics-") as temp_dir:
        generated_dir = Path(temp_dir) / "generated"
        generated_dir.mkdir()

        run_fixed("py_compile", [sys.executable, "-m", "py_compile", *scripts], private)
        run_fixed(
            "learner_scanner_tests",
            [sys.executable, str(CONTENT_ROOT / "test_validate_content_semantics.py")],
            private,
        )
        run_fixed(
            "handoff_normalization_tests",
            [
                sys.executable,
                str(CONTENT_ROOT / "test_build_content_semantics_handoff_v2.py"),
            ],
            private,
        )
        run_fixed(
            "build_handoff",
            [
                sys.executable,
                str(CONTENT_ROOT / "build_content_semantics_handoff_v2.py"),
                "--repo-root",
                ".",
                "--out-dir",
                str(generated_dir),
            ],
            private,
        )
        run_fixed(
            "build_caption_source",
            [
                sys.executable,
                str(CONTENT_ROOT / "build_ru_caption_source.py"),
                "--repo-root",
                ".",
                "--out-dir",
                str(generated_dir),
            ],
            private,
        )

        committed_request = base / "M1-L01-S02_immutable_blind_request_v1.json"
        generated_request = generated_dir / committed_request.name
        if committed_request.read_bytes() != generated_request.read_bytes():
            raise GateError("immutable_request_rebuild_mismatch")

        commands = [
            (
                "policy_bindings",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_policy_bindings.py"),
                    "--repo-root",
                    ".",
                    "--request",
                    str(CONTENT_ROOT / committed_request.name),
                ],
            ),
            (
                "audio_authority",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_audio_authority_mapping.py"),
                    "--mapping",
                    str(CONTENT_ROOT / "S01_audio_authority_mapping_v1.json"),
                    "--attestation",
                    str(CONTENT_ROOT / "audio_authority_connector_attestation_v1.json"),
                    "--self-test",
                ],
            ),
            (
                "shotir_freeze",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_shotir_freeze_reconciliation.py"),
                    "--reconciliation",
                    str(CONTENT_ROOT / "shotir_freeze_reconciliation_v1.json"),
                    "--self-test",
                ],
            ),
            (
                "ru_caption_source",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_ru_caption_source.py"),
                    "--caption-source",
                    str(generated_dir / "M1-L01-S01_ru_caption_source_v1.json"),
                    "--canonical-source",
                    str(CANONICAL_RU),
                    "--audio-mapping",
                    str(CONTENT_ROOT / "S01_audio_authority_mapping_v1.json"),
                    "--self-test",
                ],
            ),
            (
                "content_semantics",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_content_semantics.py"),
                    "--package",
                    str(generated_dir / "M1-L01-S01_content_semantics_v1.json"),
                    "--request",
                    str(generated_request),
                    "--attestation",
                    str(CONTENT_ROOT / "connector_preflight_attestation_v1.json"),
                ],
            ),
            (
                "factory_request_bridge",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_factory_request_bridge.py"),
                    "--repo-root",
                    ".",
                    "--request",
                    str(CONTENT_ROOT / "M1-L01-S02_factory_request_v1.json"),
                    "--manifest",
                    str(CONTENT_ROOT / "M1-L01-S02_factory_source_manifest_v1.json"),
                    "--content-request",
                    str(CONTENT_ROOT / committed_request.name),
                    "--self-test",
                ],
            ),
            (
                "factory_core_reconciliation",
                [
                    sys.executable,
                    str(CONTENT_ROOT / "validate_factory_core_reconciliation.py"),
                    "--request",
                    str(CONTENT_ROOT / "M1-L01-S02_factory_request_v1.json"),
                    "--reconciliation",
                    str(CONTENT_ROOT / "factory_core_reconciliation_v1.json"),
                    "--self-test",
                ],
            ),
        ]
        for name, command in commands:
            run_fixed(name, command, private)

        package = load_object(generated_dir / "M1-L01-S01_content_semantics_v1.json")
        captions = load_object(generated_dir / "M1-L01-S01_ru_caption_source_v1.json")
        handoff = load_object(base / "HANDOFF_v1.json")
        expected = {
            "semantic_units": 13,
            "shot_intents": 26,
            "semantic_slots": 13,
            "shotir_source_inputs": 26,
        }
        errors = [
            key for key, count in expected.items() if len(package.get(key, [])) != count
        ]
        if len(captions.get("caption_blocks", [])) != 13:
            errors.append("caption_blocks")
        reference = handoff.get("s01_reference_contract", {})
        for key, count in expected.items():
            if reference.get(key) != count:
                errors.append("handoff_" + key)
        blind = handoff.get("s02_blind_contract", {})
        if blind.get("canonical_source_beats") != 12:
            errors.append("s02_canonical_source_beats")
        if blind.get("normalized_factory_shot_intents") != 12:
            errors.append("s02_factory_shot_intents")
        if package.get("production_green_claimed") is not False:
            errors.append("package_fake_green")
        if captions.get("production_green_claimed") is not False:
            errors.append("caption_fake_green")
        if errors:
            raise GateError("content_semantics_contract_mismatch")

        private_sha = subprocess.check_output(
            ["git", "-C", str(private), "rev-parse", "HEAD"], text=True
        ).strip()
        print("gate_id=CONTENT_SEMANTICS_LAUNCH_GATE")
        print(f"private_sha={private_sha}")
        for key, count in expected.items():
            print(f"{key}={count}")
        print("caption_blocks=13")
        print("s02_canonical_beats=12")
        print("s02_factory_shot_intents=12")
        print(
            "handoff_sha256="
            + hashlib.sha256((base / "HANDOFF_v1.json").read_bytes()).hexdigest()
        )
        print(
            "s02_request_sha256="
            + hashlib.sha256(committed_request.read_bytes()).hexdigest()
        )
        print("resolved_shotir=false")
        print("measured_timestamps=false")
        print("audio_production_green=false")
        print("public_media_allowed=false")
        print("private_content_printed=false")
        print("result=PASS")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", required=True)
    args = parser.parse_args()
    try:
        return run_gate(Path(args.private_dir).resolve())
    except SystemExit as exc:
        return int(exc.code or 0)
    except (GateError, OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print("gate_id=CONTENT_SEMANTICS_LAUNCH_GATE")
        print("result=TERMINAL_FAILURE")
        print("failure_class=STATION_TERMINAL_FAILURE")
        print("retryable=false")
        print(f"error_code={type(exc).__name__}")
        print("private_content_public_exposure=false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
