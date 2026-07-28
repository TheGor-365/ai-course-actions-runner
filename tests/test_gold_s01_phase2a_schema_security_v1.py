#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "schemas/gold_v2_diamond"
CODEGEN_PATH = ROOT / "scripts/gold_s01_schema_contract_v1.py"
codegen_spec = importlib.util.spec_from_file_location("diamond_schema_codegen", CODEGEN_PATH)
assert codegen_spec and codegen_spec.loader
codegen = importlib.util.module_from_spec(codegen_spec)
sys.modules[codegen_spec.name] = codegen
codegen_spec.loader.exec_module(codegen)

SECURITY_PATH = ROOT / "scripts/gold_s01_archive_security_v1.py"
security_spec = importlib.util.spec_from_file_location("diamond_archive_security", SECURITY_PATH)
assert security_spec and security_spec.loader
security = importlib.util.module_from_spec(security_spec)
sys.modules[security_spec.name] = security
security_spec.loader.exec_module(security)

RECEIPT_PATH = "receipts/provider.json"
DATA_PATH = "evidence/data.txt"
SUMS_PATH = "SHA256SUMS"
EXPECTED = frozenset({RECEIPT_PATH, DATA_PATH, SUMS_PATH})


def build_zip(path: Path, *, receipt=None, data=b"fixture\n", omit_sums=False, extra=None, traversal=False, symlink=False, special=False, secret=False, checksum_mismatch=False):
    if receipt is None:
        receipt = {"schema_version": "fixture.provider.v1", "result": "BLOCKED"}
    receipt_raw = json.dumps(receipt, sort_keys=True).encode()
    data_raw = b"github_pat_forbidden" if secret else data
    sums = {
        RECEIPT_PATH: hashlib.sha256(receipt_raw).hexdigest(),
        DATA_PATH: ("0" * 64 if checksum_mismatch else hashlib.sha256(data_raw).hexdigest()),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(RECEIPT_PATH, receipt_raw)
        archive.writestr(DATA_PATH, data_raw)
        if not omit_sums:
            archive.writestr(SUMS_PATH, "".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())))
        if extra:
            archive.writestr(extra, b"extra")
        if traversal:
            archive.writestr("../escape.txt", b"escape")
        if symlink or special:
            info = zipfile.ZipInfo("unsafe")
            kind = stat.S_IFLNK if symlink else stat.S_IFIFO
            info.create_system = 3
            info.external_attr = (kind | 0o777) << 16
            archive.writestr(info, b"target")


def policy():
    return security.ArchivePolicy(
        expected_files=EXPECTED,
        receipt_schemas={RECEIPT_PATH: "fixture.provider.v1"},
        forbidden_suffixes=frozenset({".mp4", ".wav"}),
    )


class SchemaGenerationTests(unittest.TestCase):
    def test_committed_generation_is_byte_identical(self) -> None:
        result = codegen.verify_vendor(
            BASE,
            BASE / "SCHEMA_GENERATION_MANIFEST_v1.json",
            BASE / "VENDORED_SCHEMA_PROVENANCE_v1.json",
        )
        self.assertEqual("PASS", result["result"])
        self.assertEqual(8, result["generated_file_count"])
        self.assertEqual(7, result["component_schema_count"])

    def test_unresolved_identity_cannot_create_pass(self) -> None:
        payload = {
            "schema_version": "gold_v2_diamond_provider_receipt_envelope.v1",
            "receipt_id": "fixture",
            "result": "PASS",
            "identity_bindings": [{
                "identity_kind": "runtime",
                "binding_state": "UNRESOLVED",
                "commit_sha": None,
                "artifact_id": None,
                "artifact_sha256": None,
                "provisional": True,
                "authority_source": "phase2a_fixture",
                "required_for_pass": True,
            }],
            "gate_proofs": [{
                "proof_path": "fixture.json",
                "proof_sha256": "a" * 64,
                "measurement": "fixture",
                "machine_result": "PASS",
                "human_review_required": False,
            }],
            "still_render_started": False,
            "video_render_started": False,
            "workflow_dispatched": False,
            "no_fake_green": True,
        }
        with self.assertRaisesRegex(ValueError, "PASS_WITH_UNRESOLVED_IDENTITY"):
            codegen.validate_provider_envelope(payload)

    def test_vendor_rejects_embedded_head_constant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in BASE.glob("*.schema.json"):
                (root / path.name).write_bytes(path.read_bytes())
            manifest = json.loads((BASE / "SCHEMA_GENERATION_MANIFEST_v1.json").read_text(encoding="utf-8"))
            target = root / "identity_binding_v1.schema.json"
            schema = json.loads(target.read_text(encoding="utf-8"))
            schema["properties"]["forbidden"] = {"const": "a" * 40}
            target.write_text(json.dumps(schema, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            manifest["generated_files"][target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
            provenance = json.loads((BASE / "VENDORED_SCHEMA_PROVENANCE_v1.json").read_text(encoding="utf-8"))
            provenance["schema_generation_manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            provenance["generated_files"] = manifest["generated_files"]
            provenance_path = root / "provenance.json"
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "HEAD_CONSTANT_FORBIDDEN"):
                codegen.verify_vendor(root, manifest_path, provenance_path)


class ArchiveSecurityTests(unittest.TestCase):
    def assert_rejected(self, code: str, **kwargs) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            build_zip(archive, **kwargs)
            with self.assertRaisesRegex(security.ArchiveSecurityError, code):
                security.inspect_archive(archive, policy())

    def test_valid_exact_archive_passes_and_extracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            output = Path(tmp) / "out"
            build_zip(archive)
            receipt = security.extract_verified_archive(archive, output, policy())
            self.assertEqual("PASS", receipt["result"])
            self.assertEqual(EXPECTED, frozenset(p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()))

    def test_traversal_rejected(self) -> None:
        self.assert_rejected("PATH_TRAVERSAL", traversal=True)

    def test_symlink_rejected(self) -> None:
        self.assert_rejected("SYMLINK_FORBIDDEN", symlink=True)

    def test_special_file_rejected(self) -> None:
        self.assert_rejected("SPECIAL_FILE_FORBIDDEN", special=True)

    def test_extra_file_rejected(self) -> None:
        self.assert_rejected("EXACT_FILE_SET_MISMATCH", extra="extra.txt")

    def test_missing_checksums_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "fixture.zip"
            build_zip(archive, omit_sums=True)
            with self.assertRaisesRegex(security.ArchiveSecurityError, "SHA256SUMS_MISSING"):
                security.inspect_archive(archive, policy())

    def test_checksum_mismatch_rejected(self) -> None:
        self.assert_rejected("SHA256SUMS_IDENTITY_FAILED", checksum_mismatch=True)

    def test_receipt_without_schema_rejected(self) -> None:
        self.assert_rejected("RECEIPT_SCHEMA_MISMATCH", receipt={"result": "BLOCKED"})

    def test_secret_marker_rejected(self) -> None:
        self.assert_rejected("SENSITIVE_MARKER_FORBIDDEN", secret=True)

    def test_forbidden_media_suffix_rejected(self) -> None:
        self.assert_rejected("SUFFIX_FORBIDDEN", extra="leak.mp4")


if __name__ == "__main__":
    unittest.main()
