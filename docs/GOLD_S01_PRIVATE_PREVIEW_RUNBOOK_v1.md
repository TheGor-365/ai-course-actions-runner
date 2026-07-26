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

## Authority boundary

The final request is accepted only when all of these are exact and non-provisional: runner SHA; externally supplied control head and request Git blob; visual successor SHA; PR #15 exact-gate PASS receipt for PR #349; no-render manifest Git blob, SHA-256 and visual fingerprint; 26 ShotIR and 26 SceneIR; AcceptedTimingContract with `unresolved_rows=0`; final RU captions; A3483 identity; sanitized host-lock receipt; primary/replica read-write-read-delete receipt; explicit execution authorization.

Any missing, stale, failed or provisional authority stops before media mutation. Public workflows cannot execute the private contour.

## Locked-host readiness

`host-readiness` performs no dependency installation and no media render. It records exact identities for Python, Node, npm, Chromium-compatible browser, ffmpeg and ffprobe; verifies the committed package lock and Remotion 4.0.489 closure; resolves only the Gold v2 font aliases `sans-serif` and `monospace` and hashes their actual files; verifies private-root permissions and free space; then performs bounded non-media read-write-read-delete probes in distinct primary and replica namespaces.

The generated receipts contain hashes, versions, sizes and status only. They contain no absolute private paths, media, tokens or secrets.

## Atomic request rebind

`rebind-request` consumes four sanitized authorities: accepted audio handoff, visual exact-gate PASS handoff, host-lock receipt and store-probe receipt. It rejects a failed visual gate, non-zero unresolved rows, stale heads, malformed hashes, missing locks, failed store proof or absent authorization. It replaces only a provisional request; repeating the identical rebind returns `UNCHANGED`; a different already-authorized request is never overwritten.

The committed request uses external exact control binding. Execution verifies that the request path at the supplied control head has the supplied Git blob and that the request base is an ancestor, avoiding a self-referential commit SHA.

## State machine and artifact safety

The executor records 15 ordered stations. A GREEN station with the same input fingerprint is skipped. Failure evidence is append-only. Retry is capped by the profile. An injected retryable failure exits `75`; resume requires the private token and does not replay completed stations.

Stations 03–09 call only the fixed production adapter. The request cannot provide a command or script path. Before registration, outputs must exist and pass SHA-256, size and ffprobe checks. Primary and replica writes are content-addressed; mismatched existing outputs are never overwritten. Restore is performed into clean scratch, byte and codec identity is verified, and scratch is removed.

Git may receive only sanitized hashes, sizes, codec probes, opaque pointer classes and receipt hashes. Media bytes, capability tokens, raw private paths, caches and secrets remain outside Git.

## Owner review

`owner_review_gold_s01_v1.py` verifies exact heads, request blob and receipt chain, and opens a local player only with `--open`. It accepts only `ACCEPT`, `REPAIR_REQUIRED` or `REJECT`; it never writes owner acceptance automatically.
