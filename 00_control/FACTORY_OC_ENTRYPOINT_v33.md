# AI Course Factory OC Entrypoint v33 — Public Runner

```text
DOCUMENT_ID=RUNNER_FACTORY_OC_ENTRYPOINT_v33
STATUS=ACTIVE_MANDATORY_ENTRYPOINT
FACTORY_ID=AI_COURSE_FACTORY
REPOSITORY=TheGor-365/ai-course-actions-runner
ROLE=execution_only_public_GitHub_Actions_machine_shop
MANDATORY_FIRST_READ=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
EXPECTED_OC_DOCUMENT_ID=FACTORY_OPERATION_CENTER_v33
WORKER_MUST_REPORT_OC_BLOB_SHA=true
CONFLICT_SEARCH_REQUIRED=true
MEMORY_CANNOT_OVERRIDE_LIVE_OC=true
NO_FAKE_GREEN=true
```

Every runner worker, workflow author, reviewer and dispatcher must read the live production OC before any write, workflow dispatch or artifact operation.

```text
SOURCE_AUTHORITY_REPO=TheGor-365/ai-course-source-library
PRODUCTION_AUTHORITY_REPO=TheGor-365/ai-course-production-system
EXECUTION_REPO=TheGor-365/ai-course-actions-runner
EXECUTION_LAYER=PUBLIC_GITHUB_HOSTED_RUNNER
PUBLIC_RUNNER_IS_PRIMARY=true
PRIVATE_RUNNER_REQUIRED=false
SELF_HOSTED_RUNNER_REQUIRED=false
LOCKED_PRIVATE_LINUX_HOST_REQUIRED=false
PRIVATE_ACTIONS_GREEN=false
PUBLIC_RUNNER_AUDIO_RENDER_ALLOWED=true
PUBLIC_RUNNER_VIDEO_RENDER_ALLOWED=true
PUBLIC_RUNNER_STILL_RENDER_ALLOWED=true
PUBLIC_ACTIONS_ARTIFACT_UPLOAD_ALLOWED=true
PUBLIC_AUDIO_ARTIFACT_ALLOWED=true
PUBLIC_VIDEO_ARTIFACT_ALLOWED=true
PUBLIC_STILL_ARTIFACT_ALLOWED=true
```

The existing `PRIVATE_REPO_PAT` is already installed and proven. Do not recreate, rotate or reinstall it without an observed authentication failure.

Before any write or dispatch, record:

```text
OC_DOCUMENT_ID=<observed_live_document_id>
OC_BLOB_SHA=<observed_live_blob_sha>
TARGET_REPO=TheGor-365/ai-course-actions-runner
TARGET_BRANCH=<exact_branch>
ACTION_TYPE=<read|write|pr|merge|workflow_dispatch|artifact_download>
EXECUTION_LAYER=PUBLIC_GITHUB_HOSTED_RUNNER
CONFLICT_SEARCH=PASS|FAIL
```

Historical A3502 host restrictions, public-media prohibitions and private/self-hosted runner requirements cannot override the live OC.

```text
SUPERSEDED_BY=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
CURRENT_OC_DOCUMENT_ID=FACTORY_OPERATION_CENTER_v33
```
