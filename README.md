# AI Course Actions Runner

```text
DOCUMENT_ID=AI_COURSE_ACTIONS_RUNNER_README
STATUS=ACTIVE_EXECUTION_PLANE_THREE_REPO_FACTORY_A3502_SYNC
FACTORY_ID=AI_COURSE_FACTORY
ROLE=execution_only_public_github_actions_layer
NO_FAKE_GREEN=true
```

This repository is one of the three repositories that make up the AI course factory:

```text
PRODUCTION_CONTROL_REPO=TheGor-365/ai-course-production-system
SOURCE_LIBRARY_REPO=TheGor-365/ai-course-source-library
EXECUTION_RUNNER_REPO=TheGor-365/ai-course-actions-runner
```

## Authority

The runner executes allowlisted jobs and returns evidence. It is not the source of truth for course content, factory state, production promotion or release readiness.

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
CURRENT_STATE_AUTHORITY=TheGor-365/ai-course-production-system
SOURCE_AND_GOLD_AUTHORITY=TheGor-365/ai-course-source-library
RUNNER_AUTHORITY=execution_evidence_bound_to_exact_private_SHA
INDEPENDENT_PRODUCTION_GREEN_AUTHORITY=false
```

## Safety

```text
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PRIVATE_REPO_ARCHIVE_IN_PUBLIC_ARTIFACTS=true
NO_PUBLIC_AUDIO_ARTIFACTS_BY_DEFAULT=true
NO_PUBLIC_VIDEO_ARTIFACTS_BY_DEFAULT=true
NO_SECRET_PRINTING=true
ALLOWLISTED_GATES_ONLY=true
NO_ARBITRARY_SHELL_INPUT=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
EVERY_GREEN_HAS_EVIDENCE=true
PUBLIC_RUNNER_ARTIFACTS_DEFAULT=none
AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
```

## Current capability reality

```text
CURRENT_ALLOWLIST_MAX_STAGE=A3480_TEXT_ONLY
CURRENT_PRODUCTION_STAGE=A3502_STILL_FRAME_QC_GATE_NO_FULL_RENDER
CURRENT_A3502_GATE_IMPLEMENTED_IN_RUNNER=false
CURRENT_A3502_EXECUTION_PATH=private_locked_Linux_host
RUNNER_IS_REQUIRED_FOR_FUTURE_AUTOMATION=true
RUNNER_IS_NOT_CURRENT_A3502_RENDER_HOST=true
```

The current A3502 worker depends on exact Linux runtime/font/codec locks, a private artifact store, local browser availability and installed Remotion dependencies. It must not be moved into this public runner until a sanitized, reproducible and explicitly allowlisted gate is designed and proven.

## Canonical documents

```text
RUNNER_CENTER_CONTRACT=00_contracts/PUBLIC_RUNNER_CENTER_CONTRACT_v01.md
DISPATCH_RUNBOOK=docs/PUBLIC_RUNNER_DISPATCH_RUNBOOK_v01.md
AUTOMATION_BACKLOG=docs/FACTORY_RUNNER_AUTOMATION_BACKLOG_v01.md
CANONICAL_FACTORY_OC=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
CANONICAL_FACTORY_PROCESS_MAP=TheGor-365/ai-course-production-system:00_control/FACTORY_AUTOMATION_PROCESS_MAP_v01.md
```
