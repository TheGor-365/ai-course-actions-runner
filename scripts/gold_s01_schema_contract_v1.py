#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_MANIFEST_SCHEMA = "gold_v2_diamond_schema_bundle_receipt.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from iter_strings(item)


def verify_vendor(schema_dir: Path, manifest_path: Path, provenance_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != EXPECTED_MANIFEST_SCHEMA or manifest.get("result") != "PASS":
        raise ValueError("SCHEMA_GENERATION_MANIFEST_NOT_PASS")
    if manifest.get("head_constants_in_generated_schema_count") != 0:
        raise ValueError("SCHEMA_HEAD_CONSTANT_COUNT_NONZERO")
    if provenance.get("vendor_role") != "NON_AUTHORITY_SNAPSHOT":
        raise ValueError("VENDOR_ROLE_NOT_NON_AUTHORITY")
    for key in ("final_head_binding_authorized", "workflow_execution_changes_authorized", "final_manifest_materialization_authorized"):
        if provenance.get(key) is not False:
            raise ValueError(f"VENDOR_AUTHORIZATION_BOUNDARY:{key}")
    if provenance.get("schema_generation_manifest_sha256") != sha256(manifest_path):
        raise ValueError("VENDORED_MANIFEST_SHA256_MISMATCH")
    generated = manifest.get("generated_files")
    if not isinstance(generated, dict) or len(generated) != 8:
        raise ValueError("GENERATED_SCHEMA_FILE_SET_REQUIRED")
    observed: dict[str, str] = {}
    for name, expected in sorted(generated.items()):
        if not isinstance(name, str) or "/" in name or "\\" in name or not name.endswith(".schema.json"):
            raise ValueError(f"VENDORED_SCHEMA_NAME_INVALID:{name}")
        path = schema_dir / name
        if not path.is_file():
            raise ValueError(f"VENDORED_SCHEMA_MISSING:{name}")
        digest = sha256(path)
        if digest != expected:
            raise ValueError(f"VENDORED_SCHEMA_SHA256_MISMATCH:{name}")
        schema = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise ValueError(f"VENDORED_SCHEMA_DRAFT_INVALID:{name}")
        for text in iter_strings(schema):
            if HEX40.fullmatch(text):
                raise ValueError(f"FINAL_OR_PROVISIONAL_HEAD_CONSTANT_FORBIDDEN:{name}")
        observed[name] = digest
    if provenance.get("generated_files") != observed:
        raise ValueError("VENDORED_PROVENANCE_FILE_MAP_MISMATCH")
    return {
        "schema_version": "gold_v2_diamond_vendored_schema_verification.v1",
        "generated_file_count": len(observed),
        "component_schema_count": len(observed) - 1,
        "generated_files": observed,
        "production_source_sha256": manifest.get("source_sha256"),
        "result": "PASS",
        "no_fake_green": True,
    }


def validate_provider_envelope(value: dict[str, Any]) -> None:
    if value.get("schema_version") != "gold_v2_diamond_provider_receipt_envelope.v1":
        raise ValueError("PROVIDER_ENVELOPE_SCHEMA")
    if value.get("no_fake_green") is not True:
        raise ValueError("PROVIDER_NO_FAKE_GREEN")
    if value.get("result") != "PASS":
        return
    if value.get("workflow_dispatched") is not False:
        raise ValueError("PASS_WORKFLOW_DISPATCHED")
    if value.get("still_render_started") is not False or value.get("video_render_started") is not False:
        raise ValueError("PASS_MEDIA_STARTED")
    identities = value.get("identity_bindings")
    if not isinstance(identities, list) or not identities:
        raise ValueError("PASS_WITHOUT_IDENTITIES")
    for index, identity in enumerate(identities):
        if not isinstance(identity, dict) or identity.get("binding_state") != "FROZEN":
            raise ValueError(f"PASS_WITH_UNRESOLVED_IDENTITY:{index}")
        if identity.get("provisional") is not False:
            raise ValueError(f"PASS_WITH_PROVISIONAL_IDENTITY:{index}")
        if not isinstance(identity.get("commit_sha"), str) or not HEX40.fullmatch(identity["commit_sha"]):
            raise ValueError(f"PASS_WITHOUT_FROZEN_HEAD:{index}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    result = verify_vendor(args.schema_dir, args.manifest, args.provenance)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
