#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import private_owner_delivery_v1 as core


class VisualOwnerPackAdapterError(core.DeliveryError):
    pass


def load_visual_builder(checkout: Path) -> Callable[..., Mapping[str, Any]]:
    package_root = checkout / "11_tools/render_factory"
    module_file = package_root / "visual_runtime_v1/owner_review_pack.py"
    if not module_file.is_file():
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_BUILDER_MISSING",
            "11_tools/render_factory/visual_runtime_v1/owner_review_pack.py",
        )
    package_text = str(package_root)
    if package_text not in sys.path:
        sys.path.insert(0, package_text)
    try:
        module = importlib.import_module("visual_runtime_v1.owner_review_pack")
    except Exception as exc:  # exact error is intentionally not exposed publicly
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_IMPORT_FAILED",
            type(exc).__name__,
        ) from exc
    builder = getattr(module, "build_owner_review_pack", None)
    if not callable(builder):
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_BUILDER_INVALID",
            "build_owner_review_pack",
        )
    return builder


def assemble_owner_pack(
    request: Mapping[str, Any],
    checkout: Path,
    manifest_path: Path,
    manifest: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    staging: Path,
    *,
    builder: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Path]:
    inputs = request["authorized_inputs"]
    visual_content_head = inputs.get("visual_content_head")
    if not isinstance(visual_content_head, str) or not core.HEX40.fullmatch(visual_content_head):
        raise VisualOwnerPackAdapterError(
            "VISUAL_CONTENT_HEAD_REQUIRED",
            "authorized_inputs.visual_content_head",
        )
    if inputs["visual_runtime_head"] != inputs["production_sha"]:
        raise VisualOwnerPackAdapterError(
            "VISUAL_RUNTIME_HEAD_MISMATCH",
            "visual_runtime_head must equal exact production checkout SHA",
        )

    runtime_request = deepcopy(dict(manifest))
    by_name = {str(item["filename"]): item for item in items}
    for item in runtime_request["review_items"]:
        item["private_path"] = by_name[str(item["filename"])]["resolved_private_path"]

    staging.mkdir(parents=True, exist_ok=True)
    runtime_request_path = staging / "private_owner_review_request_runtime_v1.json"
    core.atomic_json(runtime_request_path, runtime_request)
    package_root = staging / "visual_owner_review_pack"
    delivery_pointer = (
        f"private-artifact://owner-delivery/{request['channel_id']}/{request['package_id']}"
    )

    build = builder or load_visual_builder(checkout)
    try:
        result = build(
            runtime_request,
            package_root,
            source_head=inputs["source_snapshot_sha"],
            visual_content_head=visual_content_head,
            delivery_pointer=delivery_pointer,
            execute=True,
        )
    except core.DeliveryError:
        raise
    except Exception as exc:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_EXECUTION_FAILED",
            type(exc).__name__,
        ) from exc

    if not isinstance(result, Mapping):
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_RESULT_INVALID",
            "result root must be object",
        )
    if result.get("status") != "PRIVATE_OWNER_REVIEW_PACK_CREATED_HUMAN_DECISION_PENDING":
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_STATUS_INVALID",
            str(result.get("status")),
        )
    if result.get("still_count") != 17:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_COUNT_INVALID",
            str(result.get("still_count")),
        )
    if result.get("human_visual_qc_green") is not False:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_HUMAN_QC_INVALID",
            "human QC must remain false",
        )
    if result.get("source_head") != inputs["source_snapshot_sha"]:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_SOURCE_HEAD_MISMATCH",
            "source head",
        )
    if result.get("visual_content_head") != visual_content_head:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_CONTENT_HEAD_MISMATCH",
            "visual content head",
        )
    if result.get("owner_delivery_pointer") != delivery_pointer:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_PACK_POINTER_MISMATCH",
            "owner delivery pointer",
        )

    contact_sheet = package_root / "contact_sheet_5x4_v1.png"
    still_archive = package_root / "full_resolution_stills_v1.zip"
    manifest_output = package_root / "owner_review_manifest_v1.json"
    checksums = package_root / "SHA256SUMS.txt"
    owner_index = package_root / "owner_review_index_v1.html"
    receipt = package_root / "owner_review_pack_receipt_v1.json"
    for path in (
        contact_sheet,
        still_archive,
        manifest_output,
        checksums,
        owner_index,
        receipt,
    ):
        if not path.is_file() or path.stat().st_size < 1:
            raise VisualOwnerPackAdapterError(
                "VISUAL_OWNER_PACK_OUTPUT_MISSING",
                path.name,
            )

    expected = {
        "contact_sheet_sha256": core.sha256_file(contact_sheet),
        "full_resolution_archive_sha256": core.sha256_file(still_archive),
        "manifest_sha256": core.sha256_file(manifest_output),
        "sha256sums_sha256": core.sha256_file(checksums),
    }
    for field, observed in expected.items():
        if result.get(field) != observed:
            raise VisualOwnerPackAdapterError(
                "VISUAL_OWNER_PACK_HASH_MISMATCH",
                field,
            )

    manifest_value = json.loads(manifest_output.read_text(encoding="utf-8"))
    if manifest_value.get("human_visual_qc_green") is not False:
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_MANIFEST_HUMAN_QC_INVALID",
            "human_visual_qc_green",
        )
    if manifest_value.get("cross_scene_clip") != "BLOCKED_UNTIL_ACCEPTED_TIMING":
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_MANIFEST_VIDEO_BOUNDARY_INVALID",
            "cross_scene_clip",
        )
    if manifest_value.get("ru_preview") != "BLOCKED_UNTIL_ACCEPTED_TIMING":
        raise VisualOwnerPackAdapterError(
            "VISUAL_OWNER_MANIFEST_VIDEO_BOUNDARY_INVALID",
            "ru_preview",
        )

    return {
        "contact_sheet": contact_sheet,
        "still_archive": still_archive,
    }
