# Public Runner Center Contract v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_CENTER_CONTRACT_v01
STATUS=ACTIVE_LAUNCH_5D_DAY2_CONTENT_SEMANTICS_GATE
FACTORY_ID=AI_COURSE_FACTORY
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
NO_FAKE_GREEN=true
```

## 1. Complete factory boundary

```text
PRODUCTION_CONTROL_REPO=TheGor-365/ai-course-production-system
SOURCE_LIBRARY_REPO=TheGor-365/ai-course-source-library
EXECUTION_RUNNER_REPO=TheGor-365/ai-course-actions-runner
THREE_REPO_FACTORY=true
```

## 2. Authority model

Runner PASS is evidence for one allowlisted gate against one exact private SHA. It is not production or release promotion.

## 3. Safety boundaries

```text
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PRIVATE_REPO_ARCHIVE_IN_PUBLIC_ARTIFACTS=true
NO_PUBLIC_AUDIO_OR_VIDEO=true
NO_SECRET_PRINTING=true
NO_ARBITRARY_SHELL=true
ALLOWLISTED_GATES_ONLY=true
FIXED_GATE_MANIFEST=config/public_gate_manifest_v1.json
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
PUBLIC_ARTIFACTS_DEFAULT=none
```

## 4. Allowed execution model

Only repository, branch, full SHA, fixed gate ID, stable request ID and sanitized writeback metadata are accepted. Dynamic commands, script paths and validator paths are absent.

## 5. Current private repository allowlist

```text
TheGor-365/ai-course-production-system
TheGor-365/ai-course-source-library
```

## 6. Current gate allowlist

```text
FACTORY_PUBLIC_RUNNER_SMOKE
A3479_CONTENT_ONLY_LOCAL_GATE
A3479_CI_SCOPE_GUARD_DOC_GATE
M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET
A3480_SCRIPT_FIT_PACK_LOCAL_GATE
FACTORY_LAUNCH_CONTROL_PLANE_GATE
CONTENT_SEMANTICS_LAUNCH_GATE
```

## 7. Current factory stage and non-claims

```text
CONTENT_SEMANTICS_LAUNCH_GATE=bounded_fixed_build_and_contract_matrix
CONTENT_SEMANTICS_PRIVATE_REPO=TheGor-365/ai-course-source-library
CONTENT_SEMANTICS_PUBLIC_ARTIFACTS=false
CONTENT_SEMANTICS_PRIVATE_LOGS_PUBLIC=false
RESOLVED_SHOTIR_CLAIM=false
MEASURED_TIMESTAMPS_CLAIM=false
AUDIO_PRODUCTION_GREEN_CLAIM=false
RENDER_GREEN_CLAIM=false
RELEASE_GREEN_CLAIM=false
A3502_GATE_IMPLEMENTED=false
PUBLIC_MEDIA_RENDER_ALLOWED=false
```

## 8. Gate admission policy

Workflow, manifest, dispatcher, contract and runbook gate sets must be equal. `validate-contract` fails closed on drift.

## 9. Private executor interface v1

The non-media fixture proves request/receipt mechanics, idempotency, retry/resume, pointer-only output and SHA restore. Actual media host and artifact store remain external and unproven.

## 10. Artifact policy

```text
TEXT_EVIDENCE_PUBLIC_ALLOWED_ONLY_IF_SANITIZED=true
AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
PROVIDER_RAW_PAYLOAD_PUBLICATION=false
PRIVATE_POINTER_IN_PUBLIC_LOGS=false
```

## 11. Day 2 capability truth

```text
RUNNER_CONTRACT_SELF_VALIDATOR=implemented
GENERIC_FIXED_GATE_MANIFEST=implemented
FACTORY_LAUNCH_CONTROL_PLANE_GATE=exact_SHA_proven
CONTENT_SEMANTICS_LAUNCH_GATE=implemented_pending_exact_SHA_result
PRIVATE_EXECUTOR_INTERFACE_V1=fixture_only
DAY2_STATUS=YELLOW_UNTIL_REAL_SOURCE_GATE_AND_ACTUAL_STATION_EXECUTION
```
