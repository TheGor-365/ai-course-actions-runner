# Gold S01 pre-render finalization v1

```text
WORK_ORDER_ID=RWO-GOLD-PSU-FINALIZATION-QUALITY-RUNNER-001
ASSIGNMENT_ISSUE=TheGor-365/ai-course-production-system#372
OC_DOCUMENT_ID=FACTORY_OPERATION_CENTER_v36
MODE=PRE_RENDER_ONLY
TWO_MINUTE_RENDER_AUTHORIZED=false
FULL_15_MINUTE_RENDER_AUTHORIZED=false
NO_FAKE_GREEN=true
```

The canonical workflow exposes two permitted modes:

- `caption_packaging`: clone the exact accepted audio execution head, require the exact accepted JSON/VTT/timing bytes, verify their hashes and 13 monotonic caption blocks, upload a content-addressed artifact, then re-download and verify it;
- `pre_render_only`: verify exact source/production receipts and compiler/component evidence, exact A3483 and accepted caption artifact identities, composition discovery, typecheck, and all no-render validators, then upload and re-download a sanitized receipt.

The predecessor media stages remain in the same canonical workflow as an unreachable held job. No dispatch option can start them under this work order.

Current execution remains blocked until provider receipts #370/#371, authoritative accepted caption JSON/VTT bytes, and the immutable non-provisional pre-render manifest exist. Static contract tests do not constitute public-runner preflight GREEN, media QC, Human acceptance, or render authorization.
