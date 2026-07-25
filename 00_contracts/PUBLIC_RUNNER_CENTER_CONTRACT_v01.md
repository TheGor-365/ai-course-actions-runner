# Public Runner Center Contract v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_CENTER_CONTRACT_v01
STATUS=ACTIVE_LAUNCH_5D_DAY1_EXECUTION_FRAMEWORK
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

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
CURRENT_FACTORY_STATE_AUTHORITY=TheGor-365/ai-course-production-system
SOURCE_AND_GOLD_AUTHORITY=TheGor-365/ai-course-source-library
RUNNER_AUTHORITY=execution_evidence_only_when_bound_to_exact_private_SHA
PRODUCTION_PROMOTION_AUTHORITY=false
FINAL_RELEASE_AUTHORITY=false
PRIVATE_ACTIONS_GREEN=false
```

A runner PASS means only that the named allowlisted gate passed against the exact private SHA.

## 3. Safety boundaries

```text
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PRIVATE_REPO_ARCHIVE_IN_PUBLIC_ARTIFACTS=true
NO_PUBLIC_AUDIO_ARTIFACTS_BY_DEFAULT=true
NO_PUBLIC_VIDEO_ARTIFACTS_BY_DEFAULT=true
NO_SECRET_PRINTING=true
NO_ARBITRARY_SHELL=true
ALLOWLISTED_GATES_ONLY=true
FIXED_GATE_MANIFEST=config/public_gate_manifest_v1.json
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
EVERY_GREEN_HAS_EVIDENCE=true
PUBLIC_ARTIFACTS_DEFAULT=none
```

## 4. Allowed execution model

The public runner may accept only an allowlisted repository, explicit branch, full 40-character SHA, fixed gate ID and sanitized writeback metadata. It verifies branch head equality before execution.

Required public request additions:

```text
REQUEST_ID_REQUIRED=true
REQUEST_ID_PATTERN=^[A-Za-z0-9._:-]{1,128}$
DYNAMIC_COMMAND_INPUT=false
DYNAMIC_SCRIPT_PATH_INPUT=false
```

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
```

Capability classification:

```text
FACTORY_PUBLIC_RUNNER_SMOKE=connectivity_and_exact_SHA_smoke
A3479_CONTENT_ONLY_LOCAL_GATE=real_bounded_contract_validator
A3479_CI_SCOPE_GUARD_DOC_GATE=inventory_only_not_production_green
M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET=count_only_smoke_not_full_import_validation
A3480_SCRIPT_FIT_PACK_LOCAL_GATE=real_bounded_text_contract_validator
FACTORY_LAUNCH_CONTROL_PLANE_GATE=bounded_launch_plan_and_OC_metadata_validator_not_production_green
```

## 7. Current factory stage and non-claims

```text
CURRENT_PRODUCTION_STAGE=A3502_STILL_FRAME_QC_GATE_NO_FULL_RENDER
RUNNER_A3502_GATE_IMPLEMENTED=false
RUNNER_A3502_RENDER_ALLOWED=false
CURRENT_A3502_EXECUTION_PATH=private_locked_Linux_host
FACTORY_LAUNCH_CONTROL_PLANE_GATE_ADVANCES_A3502=false
FACTORY_LAUNCH_CONTROL_PLANE_GATE_CREATES_MEDIA=false
```

## 8. Gate admission policy

A gate is valid only when present in the workflow choice list, fixed manifest, dispatcher, this contract and the dispatch runbook matrix. `scripts/runner_infrastructure_v1.py validate-contract` enforces set equality.

```text
GATE_INPUT_SCHEMA_DEFINED=true
GATE_OUTPUT_SCHEMA_DEFINED=true
PRIVATE_CONTENT_SANITIZATION_REQUIRED=true
ARBITRARY_COMMAND_INPUT_ABSENT=true
EXACT_PRIVATE_SHA_BINDING=true
TIMEOUT_AND_RESOURCE_LIMITS_DEFINED=true
FAILURE_CODES_DEFINED=true
NON_CLAIMS_DEFINED=true
```

## 9. Private executor interface v1

The public runner does not execute private media. The repository now contains schemas and a local non-media fixture proving interface mechanics only:

```text
REQUEST_SCHEMA=schemas/private_executor_v1.schemas.json#private_executor_request_v1
RECEIPT_SCHEMA=schemas/private_executor_v1.schemas.json#private_executor_receipt_v1
ARTIFACT_POINTER_SCHEMA=schemas/private_executor_v1.schemas.json#artifact_pointer_record_v1
FIXED_PROFILE=FIXTURE_ARTIFACT_V1
FIXTURE_EXECUTOR=scripts/runner_infrastructure_v1.py execute-fixture
ACTUAL_PRIVATE_ARTIFACT_STORE_CONNECTED=false
SELF_HOSTED_PRIVATE_MEDIA_RUNNER_CONNECTED=false
```

The fixture proves idempotency, retry/resume, pointer-only sanitized stdout and SHA-verified backup/restore. It does not prove S01 execution.

## 10. Artifact policy

```text
TEXT_EVIDENCE_PUBLIC_ALLOWED_ONLY_IF_SANITIZED=true
AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
PUBLIC_RUNNER_UPLOAD_ARTIFACT_AUDIO=false
PUBLIC_RUNNER_UPLOAD_ARTIFACT_VIDEO=false
PROVIDER_RAW_PAYLOAD_PUBLICATION=false
PRIVATE_SOURCE_ARCHIVE_PUBLICATION=false
PRIVATE_POINTER_IN_PUBLIC_LOGS=false
```

## 11. Day 1 capability truth

```text
RUNNER_CONTRACT_SELF_VALIDATOR=implemented_changed_path_test_required
GENERIC_FIXED_GATE_MANIFEST=implemented_changed_path_test_required
FACTORY_LAUNCH_CONTROL_PLANE_GATE=implemented_not_live_dispatched
PRIVATE_EXECUTOR_INTERFACE_V1=implemented_fixture_only
RETRY_RESUME=implemented_fixture_only
ARTIFACT_POINTER_RECEIPT=implemented_fixture_only
BACKUP_RESTORE_SHA=implemented_fixture_only
PUBLIC_MEDIA_ARTIFACTS=false
PRIVATE_CONTENT_PUBLIC_EXPOSURE=false
DAY1_STATUS=YELLOW_UNTIL_GITHUB_ACTIONS_AND_EXACT_PRIVATE_SHA_GATE_RUN
```
