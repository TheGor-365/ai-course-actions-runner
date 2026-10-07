# AI Course Actions Runner

```text
DOCUMENT_ID=AI_COURSE_ACTIONS_RUNNER_README
STATUS=ACTIVE_EXECUTION_PLANE_WITH_OC_V33_PRECEDENCE
FACTORY_ID=AI_COURSE_FACTORY
ROLE=execution_only_public_github_actions_layer
MANDATORY_FIRST_READ=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
CURRENT_OC_DOCUMENT_ID=FACTORY_OPERATION_CENTER_v33
WORKER_MUST_REPORT_OC_BLOB_SHA=true
CONFLICT_SEARCH_REQUIRED=true
MEMORY_CANNOT_OVERRIDE_LIVE_OC=true
NO_FAKE_GREEN=true
```

This repository is the public execution-only machine shop for the three-repository AI course factory. It is not content, production-state, promotion or release authority.

## Mandatory entry

```text
RUNNER_ENTRYPOINT=00_control/FACTORY_OC_ENTRYPOINT_v33.md
SOURCE_AUTHORITY_REPO=TheGor-365/ai-course-source-library
PRODUCTION_AUTHORITY_REPO=TheGor-365/ai-course-production-system
EXECUTION_REPO=TheGor-365/ai-course-actions-runner
EXECUTION_LAYER=PUBLIC_GITHUB_HOSTED_RUNNER
```

## Current execution and artifact authority

```text
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
MEDIA_BINARIES_IN_GIT_COMMITS=false
```

The current public-artifact allowance is bounded by the live production OC. Private repository archives, secrets, raw provider payloads and unsanitized private content remain forbidden.

## Safety invariants

```text
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PRIVATE_REPO_ARCHIVE_IN_PUBLIC_ARTIFACTS=true
NO_SECRET_PRINTING=true
NO_ARBITRARY_SHELL_INPUT=true
ALLOWLISTED_GATES_ONLY=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
EVERY_GREEN_HAS_EVIDENCE=true
RUNNER_CAN_PROMOTE_PRODUCTION=false
FINAL_HUMAN_VIDEO_ACCEPTANCE_REQUIRED=true
```

The existing `PRIVATE_REPO_PAT` is already installed and proven. Do not recreate or rotate it without an observed authentication failure.

## Legacy routing

The former A3502-only public-media prohibition, `private_locked_Linux_host` execution path and private/self-hosted runner requirement are historical snapshots only.

```text
HISTORICAL_A3502_POLICY=LEGACY_SUPERSEDED
SUPERSEDED_BY=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
```

## Canonical documents

```text
RUNNER_CENTER_CONTRACT=00_contracts/PUBLIC_RUNNER_CENTER_CONTRACT_v01.md
RUNNER_ENTRYPOINT=00_control/FACTORY_OC_ENTRYPOINT_v33.md
CANONICAL_FACTORY_OC=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
```
