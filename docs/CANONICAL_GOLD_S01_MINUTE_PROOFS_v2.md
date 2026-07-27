# Canonical Gold S01 minute proofs v2

```text
WORK_ORDER_ID=RWO-M1-L01-S01-PUBLIC-RUNNER-MINUTE-PROOFS-002
ROLE=PUBLIC_RUNNER_CANONICAL_MINUTE_PROOF_WORKER
TARGET_BRANCH=worker/canonical-gold-s01-minute-proofs-v2
BASE_HEAD=65a124cdbb5e3a0580a42e887bd59c3e4634d9e6
OC_DOCUMENT_ID=FACTORY_OPERATION_CENTER_v35
OC_HEAD=d2aa0ee07bc9323bcc4a2bd134806d09c217eeeb
MAIN_MERGE_AUTHORIZED=false
FULL_15_MINUTE_RENDER_AUTHORIZED=false
NO_FAKE_GREEN=true
```

## Current state

Infrastructure and fail-closed packaging are implemented. A qualifying media dispatch is blocked because lane A–E exact receipts and exact accepted caption bytes are not yet available.

```text
ONE_CANONICAL_MINUTE_WORKFLOW=true
DUPLICATE_TRIGGERING_WORKFLOW_COUNT=0
EXACT_UPSTREAM_HEAD_BINDING=SCHEMA_READY_NOT_RECEIVED
A3483_IDENTITY_VERIFICATION=IMPLEMENTED_NOT_RUN
ACCEPTED_CAPTION_JSON_MATERIALIZED=false
ACCEPTED_CAPTION_VTT_MATERIALIZED=false
PILOT_A_RENDERED=false
PILOT_B_RENDERED=false
OWNER_REVIEW_PACKAGE_READY=false
HUMAN_FINAL_ACCEPTANCE=false
FULL_15_MINUTE_RENDERED=false
```

## Dispatch gate

The committed file `config/canonical_gold_s01_exact_inputs_v2.json` must be replaced with one exact reconciled manifest. The validator rejects null/provisional heads, hashes, missing lane receipts, any policy bypass, missing VTT hash, non-contiguous windows, silent audio, draft captions, and full-render authority.

A qualifying dispatch requires:

- `status=EXACT_RECONCILED`;
- exact lane A–E heads and reconciled source/production heads;
- all required SHA-256 identities;
- `LANE_A_COMPLETE` through `LANE_E_COMPLETE`;
- `EXACT_HEAD_RECONCILIATION=true`;
- exact accepted caption JSON and VTT artifact variables;
- `execute_media=true`.

The workflow uses a production-owned bridge from the exact production commit. The runner validates the bridge path and SHA and invokes only committed argument arrays without a shell. It does not implement or lower compiler/runtime/QC policy.

## Caption blocker

The accepted JSON identity is known:

```text
CAPTION_JSON_SHA256=5ad105306f9e9e68c790494981692e685e4a8dcbd7d68aa60629ae495356ef18
```

The exact accepted JSON bytes, exact accepted VTT bytes, VTT SHA-256, artifact ID, and artifact ZIP SHA-256 were not provable from the live PR #347 Git tree or available Actions receipts. No draft SRT fallback or regeneration is permitted. Stage 14 remains fail-closed until those bytes are materialized as one content-addressed artifact.

## Stop boundary

After two successful artifacts, the workflow writes:

```text
OWNER_REVIEW_PACKAGE_READY=true
HUMAN_FINAL_ACCEPTANCE=false
FULL_15_MINUTE_RENDERED=false
NO_FAKE_GREEN=true
```

It contains no full-lesson render stage.
