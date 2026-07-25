# Factory Runner Automation Backlog v01

```text
DOCUMENT_ID=FACTORY_RUNNER_AUTOMATION_BACKLOG_v01
STATUS=ACTIVE_LAUNCH_5D_DAY2
FACTORY_ID=AI_COURSE_FACTORY
NO_FAKE_AUTOMATION_CLAIMS=true
```

## 1. Proven implementation scope

```text
EXACT_PRIVATE_SHA_CHECKOUT=proven
PRIVATE_BRANCH_HEAD_VERIFICATION=proven
RUNNER_CONTRACT_SELF_VALIDATOR=proven
GENERIC_FIXED_GATE_MANIFEST=proven
FACTORY_LAUNCH_CONTROL_PLANE_GATE=proven_exact_SHA
CONTENT_SEMANTICS_LAUNCH_GATE=implemented_pending_exact_SHA_result
PRIVATE_EXECUTOR_INTERFACE_V1=fixture_only
RESUME_RETRY=fixture_only
BACKUP_RESTORE_SHA=fixture_only
PUBLIC_BINARY_ARTIFACTS_DEFAULT_NONE=true
```

## 2. Limitations

```text
GENERAL_PURPOSE_SHELL_ALLOWED=false
A3502_GATE_IMPLEMENTED=false
PRIVATE_ARTIFACT_STORE_CONNECTION=false
SELF_HOSTED_PRIVATE_RENDER_RUNNER=false
ACTUAL_S01_RETRY_RESUME=false
ACTUAL_S01_BACKUP_RESTORE=false
```

## 3. Backlog

### R01/R02 — Self-validator and fixed gate manifest

```text
STATUS=PROVEN
```

### R03 — A3502 no-render gate

```text
STATUS=BLOCKED_BY_VISUAL_RUNTIME_REFERENCE_AND_RUNTIME_LOCK
```

### R04 — Production-side runner evidence consumer

```text
STATUS=NEXT
OWNER_REPO=TheGor-365/ai-course-production-system
```

### R05 — Factory-core dispatcher consumption

```text
STATUS=INTERFACE_AVAILABLE_launch-core-v1
NEXT=consume_real_station_envelope
```

### R06/R07/R08 — Retry, private executor and artifact pointer

```text
STATUS=FIXTURE_PROVEN_ACTUAL_HOST_PENDING
```

### R09 — Blind package orchestration

```text
STATUS=WAITING_FOR_REAL_STATION_OUTPUTS
```

### R10 — Cross-repository synchronization validator

```text
STATUS=NEXT
```

## 4. Required next evidence

```text
CONTENT_SEMANTICS_EXACT_SHA_GATE=PASS
PRODUCTION_EVIDENCE_CONSUMER=PASS
ALIGNMENT_PROVISIONING_RESUME_FIXTURE=PASS
CROSS_REPO_SYNC_GATE=PASS
ACTUAL_PRIVATE_ARTIFACT_STORE_CONNECTION=PASS
```
