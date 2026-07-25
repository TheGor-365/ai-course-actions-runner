# Gold S01 private visual master and RU preview runbook v1

```text
PROFILE_ID=M1_L01_S01_RU_GOLD_V2_PRIVATE_PREVIEW_V1
SCOPE=M1-L01-S01_0000-1500_ONLY
PRIVATE_HOST_ONLY=true
PUBLIC_WORKFLOW_EXECUTION_ALLOWED=false
PUBLIC_ARTIFACT_UPLOAD_ALLOWED=false
ARBITRARY_COMMANDS_ALLOWED=false
DYNAMIC_SCRIPT_PATH_ALLOWED=false
NETWORK_PROVIDER_CALLS_DEFAULT=false
NO_FAKE_GREEN=true
```

## Current execution boundary

Public CI may validate contracts, but private rendering is refused whenever `GITHUB_ACTIONS=true`. Final mutation requires exact runner, control and production SHAs; an externally supplied exact request blob; the fixed production adapter at `11_tools/render_factory/gold_s01_private_execution_v1.py`; a non-provisional Gold v2 no-render manifest with 26 ShotIR and 26 SceneIR records; accepted timing with `unresolved_rows=0`; final RU captions; exact A3483 identity; the visual input fingerprint; runtime/browser/font locks; and explicit execution authorization.

Any missing, provisional or mismatched input stops before render mutation.

## Host bootstrap

`host-probe` is read-only unless `--authorize-store-probe` is supplied. The optional probe writes random non-media bytes to the primary and replica probe namespaces, reads them, and deletes them. It never installs dependencies.

The generated install plan keeps `npm ci` unauthorized until exact Node/npm/browser/font locks and a separate install authorization are published. Infrastructure retry cannot alter content inputs.

## State machine

The executor records 15 ordered stations. A GREEN station with the same input fingerprint is skipped. Failure evidence is append-only. Retry is capped by the profile. An injected retryable failure exits `75`; resume requires the private token and does not replay completed stations.

Stations 03–09 call only the fixed production adapter with fixed flags. A request cannot supply a command or script path.

## Output safety

Expected outputs are a clean H.264 1920×1080/30 visual master with no audio stream and an H.264/AAC 1920×1080/30 RU preview with stereo 48 kHz audio.

The executor validates file existence, SHA-256, size and ffprobe profile before registration. It writes content-addressed primary and replica copies, performs clean restore with byte and codec verification, removes restore scratch, and emits sanitized receipts. Existing mismatched content-addressed outputs are never overwritten.

Git may receive only hashes, sizes, codec probes, opaque pointer classes and receipt hashes. Media bytes, capability tokens, absolute private paths, caches and secrets stay outside Git.

## Owner review

`owner_review_gold_s01_v1.py` verifies exact runner/control/production heads, the externally supplied request blob, receipt-chain hashes and local preview hash. It opens a local player only with `--open`. It accepts only `ACCEPT`, `REPAIR_REQUIRED` or `REJECT`, writes a local-only decision receipt, performs no GitHub write and does not invent owner acceptance.
