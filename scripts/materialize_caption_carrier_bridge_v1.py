#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "s01_ru_accepted_timing_contract_v01.json": (
        "716b539630ad501d16e2dac13d1a6107b601a9094a3c57941cc962dc185b4b61",
        328657,
        "bcd93af85719bbabd53846a466294144410e1bb6ba7f12cfb9d15387ec7b9932",
        34011,
        4,
    ),
    "s01_ru_final_captions_v01.json": (
        "5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18",
        24058,
        "fa9f01084bd2f4853ad1de9a5c7c8ebf824dc08d245e41fd2c8118be7ab48894",
        7529,
        1,
    ),
    "s01_ru_final_captions_v01.vtt": (
        "6be0d0cc2df0955ce7779275af2cec9c3c71137a91a75796384c1ad17cacb855",
        20198,
        "7a5bd1f924aecf8c028d4409684284eb9b1014fbe3f4fd25df5f037aa2e51751",
        6220,
        1,
    ),
    "caption_recovery_receipt.json": (
        "79be42708b70cd046f88f00fe6020370357b8150b159308debb4c77977f22b2e",
        770,
        "329efb14720e59d531f0c8bc6d856c43a7b97b68d4a661df03ddc012801a53a8",
        428,
        1,
    ),
    "SHA256SUMS": (
        "04ba3009a5f3a697681e8c1f25002ec5b7331ad15c4d8eb9f4bfef1edfb4f254",
        396,
        "a4a4dd64f8a1755c5a93b3f8655178d49b7f59ebc2406ce50cbe9a9d42a454fa",
        264,
        1,
    ),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def timestamp_ms(value: str) -> int:
    match = re.fullmatch(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})", value)
    if not match:
        raise AssertionError(f"INVALID_VTT_TIMESTAMP:{value}")
    hours, minutes, seconds, millis = map(int, match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comments", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    comments = json.loads(args.comments.read_text(encoding="utf-8"))
    bodies = [item.get("body", "") for item in comments]
    manifests = [
        body for body in bodies
        if body.startswith("CAPTION_BYTE_TRANSPORT_MANIFEST_V1\n")
    ]
    assert len(manifests) == 1, "TRANSPORT_MANIFEST_COUNT_MISMATCH"
    manifest_lines = manifests[0].splitlines()
    for field in (
        "encoding=gzip+base64",
        "gzip_mtime=0",
        "zip_sha256=16319e5664765aa29625311b7d4c2f27618c763054971fcdf7bb430beb1ef7b4",
        "chunk_count=8",
    ):
        assert field in manifest_lines, f"MANIFEST_FIELD_MISSING:{field}"

    grouped: dict[str, dict[int, str]] = {name: {} for name in EXPECTED}
    chunk_bodies = [
        body for body in bodies
        if body.startswith("CAPTION_BYTE_GZIP_CHUNK_V1\n")
    ]
    assert len(chunk_bodies) == 8, "TRANSPORT_CHUNK_COUNT_MISMATCH"
    for body in chunk_bodies:
        fields = dict(line.split("=", 1) for line in body.splitlines()[1:])
        name = fields["file"]
        assert name in EXPECTED, f"UNEXPECTED_TRANSPORT_FILE:{name}"
        raw_hash, _, gzip_hash, _, total = EXPECTED[name]
        index = int(fields["index"])
        assert int(fields["total"]) == total, f"CHUNK_TOTAL_MISMATCH:{name}"
        assert fields["raw_sha256"] == raw_hash, f"RAW_DECLARATION_MISMATCH:{name}"
        assert fields["gzip_sha256"] == gzip_hash, f"GZIP_DECLARATION_MISMATCH:{name}"
        assert index not in grouped[name], f"DUPLICATE_CHUNK:{name}:{index}"
        grouped[name][index] = fields["payload_base64"]

    args.output.mkdir(parents=True, exist_ok=False)
    raw_files: dict[str, bytes] = {}
    for name, spec in EXPECTED.items():
        raw_hash, raw_size, gzip_hash, gzip_size, total = spec
        chunks = grouped[name]
        assert sorted(chunks) == list(range(1, total + 1)), f"CHUNK_SEQUENCE_MISMATCH:{name}"
        compressed = base64.b64decode(
            "".join(chunks[index] for index in sorted(chunks)),
            validate=True,
        )
        assert len(compressed) == gzip_size, f"GZIP_SIZE_MISMATCH:{name}"
        assert sha256(compressed) == gzip_hash, f"GZIP_HASH_MISMATCH:{name}"
        raw = gzip.decompress(compressed)
        assert len(raw) == raw_size, f"RAW_SIZE_MISMATCH:{name}"
        assert sha256(raw) == raw_hash, f"RAW_HASH_MISMATCH:{name}"
        (args.output / name).write_bytes(raw)
        raw_files[name] = raw

    assert {item.name for item in args.output.iterdir()} == set(EXPECTED), "FINAL_FILE_SET_MISMATCH"

    sums: dict[str, str] = {}
    for line in raw_files["SHA256SUMS"].decode("utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/]+)", line)
        assert match, f"INVALID_SHA256SUMS_LINE:{line}"
        sums[match.group(2)] = match.group(1)
    assert set(sums) == set(EXPECTED) - {"SHA256SUMS"}, "SHA256SUMS_FILE_SET_MISMATCH"
    for name, digest in sums.items():
        assert sha256(raw_files[name]) == digest, f"SHA256SUMS_MISMATCH:{name}"

    timing = json.loads(raw_files["s01_ru_accepted_timing_contract_v01.json"])
    captions = json.loads(raw_files["s01_ru_final_captions_v01.json"])
    receipt = json.loads(raw_files["caption_recovery_receipt.json"])
    timing_blocks = timing["final_ru_captions"]
    json_blocks = captions["caption_blocks"]
    assert len(timing_blocks) == len(json_blocks) == 13, "JSON_BLOCK_COUNT_MISMATCH"
    assert timing_blocks == json_blocks, "TIMING_CAPTION_JSON_IDENTITY_MISMATCH"

    vtt_blocks = [
        block
        for block in raw_files["s01_ru_final_captions_v01.vtt"]
        .decode("utf-8")
        .strip()
        .split("\n\n")
        if block
    ]
    assert vtt_blocks[0] == "WEBVTT", "VTT_HEADER_MISMATCH"
    assert len(vtt_blocks[1:]) == 13, "VTT_CUE_COUNT_MISMATCH"
    previous_end = -1
    for index, (cue_text, json_block) in enumerate(
        zip(vtt_blocks[1:], json_blocks, strict=True)
    ):
        lines = cue_text.splitlines()
        start_text, end_text = lines[1].split(" --> ", 1)
        start_ms, end_ms = timestamp_ms(start_text), timestamp_ms(end_text)
        assert 0 <= start_ms < end_ms <= 908398, f"VTT_RANGE_INVALID:{index}"
        assert start_ms >= previous_end, f"VTT_NON_MONOTONIC:{index}"
        previous_end = end_ms
        assert lines[0] == json_block["caption_block_id"], f"JSON_VTT_ID_MISMATCH:{index}"
        assert start_ms == json_block["start_ms"], f"JSON_VTT_START_MISMATCH:{index}"
        assert end_ms == json_block["end_ms"], f"JSON_VTT_END_MISMATCH:{index}"
        assert "\n".join(lines[2:]) == json_block["text"], f"JSON_VTT_TEXT_MISMATCH:{index}"
    assert previous_end == 908398, "FINAL_CAPTION_END_MISMATCH"

    assert receipt["accepted_audio_execution_head"] == "755b8a3558b08b4b7c5d9b45d0ef01212f10ecc4"
    assert receipt["accepted_timing_sha256"] == EXPECTED["s01_ru_accepted_timing_contract_v01.json"][0]
    assert receipt["caption_json_sha256"] == EXPECTED["s01_ru_final_captions_v01.json"][0]
    assert receipt["caption_vtt_sha256"] == EXPECTED["s01_ru_final_captions_v01.vtt"][0]
    assert receipt["json_block_count"] == receipt["vtt_cue_count"] == 13
    assert receipt["final_caption_end_ms"] == 908398
    assert receipt["json_vtt_timing_identity"] is True
    for key in (
        "regeneration_performed",
        "editorial_mutation_performed",
        "timing_mutation_performed",
        "segmentation_mutated",
    ):
        assert receipt[key] is False, f"FORBIDDEN_MUTATION:{key}"

    print("CAPTION_CARRIER_BYTE_MATERIALIZATION=PASS")
    print("JSON_VTT_TIMING_IDENTITY=true")
    print("FINAL_CAPTION_END_MS=908398")
    print("MEDIA_RENDER_STARTED=false")


if __name__ == "__main__":
    main()
