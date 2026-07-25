# Factory Runner Automation Backlog v01

```text
DOCUMENT_ID=FACTORY_RUNNER_AUTOMATION_BACKLOG_v01
STATUS=ACTIVE_LAUNCH_5D_DAY1_IMPLEMENTATION
FACTORY_ID=AI_COURSE_FACTORY
OWNER_REPO=TheGor-365/ai-course-actions-runner
NO_FAKE_AUTOMATION_CLAIMS=true
```

## 1. Current proven implementation scope

```text
EXACT_PRIVATE_SHA_CHECKOUT=existing
PRIVATE_BRANCH_HEAD_VERIFICATION=existing
PRIVATE_REPO_ALLOWLIST=manifest_and_workflow
GATE_ID_ALLOWLIST=manifest_workflow_dispatcher_docs
RUNNER_CONTRACT_SELF_VALIDATOR=implemented_pending_CI
GENERIC_FIXED_GATE_MANIFEST=implemented_pending_CI
FACTORY_LAUNCH_CONTROL_PLANE_GATE=implemented_pending_exact_SHA_dispatch
PRIVATE_EXECUTOR_INTERFACE_V1=implemented_fixture_only
ARTIFACT_POINTER_RECORD=implemented_fixture_only
RESUME_RETRY=implemented_fixture_only
BACKUP_RESTORE_SHA=implemented_fixture_only
PUBLIC_BINARY_ARTIFACTS_DEFAULT_NONE=true
```

## 2. Current capability limitations

```text
GENERAL_PURPOSE_SHELL_ALLOWED=false
DYNAMIC_VALIDATOR_PATH_INPUT_ALLOWED=false
A3502_GATE_IMPLEMENTED=false
EXACT_FONT_CONTAINER_IMAGE=false
REMOTION_BROWSER_IMAGE=false
PRIVATE_ARTIFACT_STORE_CONNECTION=false
SELF_HOSTED_PRIVATE_RENDER_RUNNER=false
MEDIA_ARTIFACT_POINTER_WRITEBACK=false
PACKAGE_STATE_MACHINE=false
BATCH_DISPATCH=false
ACTUAL_S01_RETRY_RESUME=false
ACTUAL_S01_BACKUP_RESTORE=false
```

## 3. Backlog

### R01 — Runner contract self-validator

```text
IMPLEMENTATION=scripts/runner_infrastructure_v1.py validate-contract
STATUS=IMPLEMENTED_PENDING_GITHUB_ACTIONS
ACCEPTANCE=workflow_manifest_dispatcher_contract_runbook_gate_sets_equal
```

### R02 — Generic sanitized gate framework

```text
IMPLEMENTATION=config/public_gate_manifest_v1.json+scripts/runner_infrastructure_v1.py resolve-gate
STATUS=IMPLEMENTED_PENDING_GITHUB_ACTIONS
ARBITRARY_COMMAND_INPUT=false
```

### R03 — A3502 no-render composition validation gate

```text
STATUS=BLOCKED_BY_LOCAL_PRIVATE_REFERENCE_PASS_AND_RUNTIME_LOCK
PUBLIC_MEDIA=false
```

### R04 — Production-side runner evidence consumer

```text
STATUS=NOT_IMPLEMENTED
OWNER_REPO=TheGor-365/ai-course-production-system
```

### R05 — Package state-machine dispatcher

```text
STATUS=WAITING_FOR_FACTORY_CORE_STATION_ENVELOPE
```

### R06 — Resume/retry controller

```text
FIXTURE_IMPLEMENTATION=scripts/runner_infrastructure_v1.py execute-fixture
FIXTURE_STATUS=IMPLEMENTED_PENDING_CI
ACTUAL_STATION_STATUS=NOT_PROVEN
```

### R07 — Self-hosted private executor

```text
SCHEMAS=schemas/private_executor_v1.schemas.json#private_executor_request_v1,schemas/private_executor_v1.schemas.json#private_executor_receipt_v1
FIXED_PROFILE=config/private_executor_profiles_v1.json
FIXTURE_STATUS=IMPLEMENTED_NON_MEDIA_ONLY
SELF_HOSTED_MEDIA_STATUS=NOT_CONNECTED
```

### R08 — Artifact pointer writeback

```text
SCHEMA=schemas/private_executor_v1.schemas.json#artifact_pointer_record_v1
FIXTURE_RECEIPT=IMPLEMENTED_PRIVATE_FILE_ONLY
PRODUCTION_REGISTRY_CALLBACK=NOT_IMPLEMENTED
```

### R09 — Batch package orchestrator

```text
STATUS=NOT_IMPLEMENTED
```

### R10 — Cross-repository synchronization validator

```text
STATUS=NOT_IMPLEMENTED
KNOWN_BLOCKER=production_integration_branch_diverged_from_main
```

## 4. Required next evidence

```text
RUNNER_SELF_TEST_WORKFLOW=PASS
FACTORY_LAUNCH_CONTROL_PLANE_GATE_EXACT_SHA_RUN=PASS
PRIVATE_EXECUTOR_FIXTURE_CI=PASS
PRODUCTION_EVIDENCE_CONSUMER=PASS
ACTUAL_PRIVATE_ARTIFACT_STORE_CONNECTION=PASS
ACTUAL_S01_RESUME_RESTORE=PASS
```

No fixture result is production GREEN.
