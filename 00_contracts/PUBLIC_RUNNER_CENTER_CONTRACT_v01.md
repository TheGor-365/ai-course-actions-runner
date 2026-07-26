# Public Runner Center Contract v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_CENTER_CONTRACT_v01
STATUS=ACTIVE_EXECUTION_CONTRACT_WITH_OC_V33_PRECEDENCE
FACTORY_ID=AI_COURSE_FACTORY
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
MANDATORY_FIRST_READ=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
CURRENT_OC_DOCUMENT_ID=FACTORY_OPERATION_CENTER_v33
WORKER_MUST_REPORT_OC_BLOB_SHA=true
CONFLICT_SEARCH_REQUIRED=true
MEMORY_CANNOT_OVERRIDE_LIVE_OC=true
NO_FAKE_GREEN=true
```

## 1. Authority model

```text
SOURCE_AUTHORITY_REPO=TheGor-365/ai-course-source-library
PRODUCTION_AUTHORITY_REPO=TheGor-365/ai-course-production-system
EXECUTION_REPO=TheGor-365/ai-course-actions-runner
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
RUNNER_AUTHORITY=execution_evidence_only_when_bound_to_exact_private_SHA
PRODUCTION_PROMOTION_AUTHORITY=false
FINAL_RELEASE_AUTHORITY=false
PRIVATE_ACTIONS_GREEN=false
```

A runner PASS means only that an allowlisted gate passed against the exact private repository, branch and SHA. It does not independently promote production state or imply Human Owner acceptance.

## 2. Current execution layer

```text
EXECUTION_LAYER=PUBLIC_GITHUB_HOSTED_RUNNER
PUBLIC_RUNNER_IS_PRIMARY=true
PRIVATE_RUNNER_REQUIRED=false
SELF_HOSTED_RUNNER_REQUIRED=false
LOCKED_PRIVATE_LINUX_HOST_REQUIRED=false
PUBLIC_RUNNER_TEXT_VALIDATION_ALLOWED=true
PUBLIC_RUNNER_AUDIO_RENDER_ALLOWED=true
PUBLIC_RUNNER_VIDEO_RENDER_ALLOWED=true
PUBLIC_RUNNER_STILL_RENDER_ALLOWED=true
PUBLIC_ACTIONS_ARTIFACT_UPLOAD_ALLOWED=true
PUBLIC_AUDIO_ARTIFACT_ALLOWED=true
PUBLIC_VIDEO_ARTIFACT_ALLOWED=true
PUBLIC_STILL_ARTIFACT_ALLOWED=true
```

The exact scope, current package authorization and any later restriction are controlled exclusively by the live production OC.

## 3. Safety boundaries

```text
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PRIVATE_REPO_ARCHIVE_IN_PUBLIC_ARTIFACTS=true
NO_SECRET_PRINTING=true
NO_ARBITRARY_SHELL=true
ALLOWLISTED_GATES_ONLY=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
EVERY_GREEN_HAS_EVIDENCE=true
MEDIA_BINARIES_IN_GIT_COMMITS=false
RAW_PROVIDER_PAYLOADS_IN_PUBLIC_ARTIFACTS=false
```

Public Actions artifacts may contain only the bounded outputs permitted by the live OC. Artifact names and receipts must bind to the exact private SHA and input fingerprint.

## 4. Credential rule

```text
PRIVATE_REPO_PAT_ALREADY_INSTALLED=true
PRIVATE_REPO_PAT_PREVIOUSLY_TESTED=true
RECREATE_CREDENTIAL_WITHOUT_AUTH_FAILURE=false
ROTATE_CREDENTIAL_WITHOUT_AUTH_FAILURE=false
```

## 5. Required dispatch record

```text
OC_DOCUMENT_ID=<observed_live_document_id>
OC_BLOB_SHA=<observed_live_blob_sha>
TARGET_REPO=<exact_repo>
TARGET_BRANCH=<exact_branch>
ACTION_TYPE=workflow_dispatch|artifact_download|writeback
EXECUTION_LAYER=PUBLIC_GITHUB_HOSTED_RUNNER
CONFLICT_SEARCH=PASS|FAIL
PRIVATE_SHA=<exact_40_character_sha>
GATE_ID=<allowlisted_gate>
```

## 6. Evidence requirements

```text
runner_repo
public_run_id
public_job_id
private_repo
private_branch
private_sha
gate_id
status_context
exit_code
result
sanitized_counts_or_hashes
artifact_ids_if_any
artifact_sha256_if_any
private_content_public_exposure=false
```

## 7. Legacy A3502 policy

The former A3502-only execution restrictions are preserved as historical evidence and are not active policy:

```text
HISTORICAL_STATUS=LEGACY_SUPERSEDED
HISTORICAL_EXECUTION_PATH=private_locked_Linux_host
HISTORICAL_PUBLIC_MEDIA_ARTIFACTS_FORBIDDEN=true
HISTORICAL_AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
HISTORICAL_VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
HISTORICAL_PRIVATE_OR_SELF_HOSTED_RUNNER_REQUIRED=true
SUPERSEDED_BY=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
```

## 8. Non-claims

```text
RUNNER_CAN_OVERRIDE_LIVE_OC=false
RUNNER_CAN_PROMOTE_PRODUCTION=false
RUNNER_CAN_INFER_FINAL_VIDEO_ACCEPTANCE=false
FIXTURE_PASS_COUNTS_AS_PRODUCTION_PASS=false
NO_FAKE_GREEN=true
```
