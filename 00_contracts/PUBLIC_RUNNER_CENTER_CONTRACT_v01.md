# Public Runner Center Contract v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_CENTER_CONTRACT_v01
STATUS=ACTIVE_BOOTSTRAP_CONTRACT
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
```

## 1. Authority model

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
PRIVATE_REPOS_ARE_SOURCE_OF_TRUTH=true
PUBLIC_RUNNER_AUTHORITY=execution_evidence_only_when_bound_to_private_sha
PRIVATE_ACTIONS_GREEN=false
NO_FAKE_GREEN=true
```

## 2. Safety boundaries

```text
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PRIVATE_REPO_ARCHIVE_IN_PUBLIC_ARTIFACTS=true
NO_PUBLIC_AUDIO_ARTIFACTS_BY_DEFAULT=true
NO_PUBLIC_VIDEO_ARTIFACTS_BY_DEFAULT=true
NO_SECRET_PRINTING=true
NO_ARBITRARY_SHELL=true
ALLOWLISTED_GATES_ONLY=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
EVERY_GREEN_HAS_EVIDENCE=true
```

## 3. Allowed execution model

The runner may clone an explicitly selected private repository, checkout an explicitly provided branch and SHA, execute an allowlisted gate, and publish compact evidence.

Allowed evidence:

```text
repo_name
branch
private_sha
public_run_id
public_job_id
status_context
gate_id
exit_code
counts
hashes
short_summary
```

Forbidden evidence:

```text
full_private_lesson_text
full_private_source_bundle
private_repo_archive
api_keys
provider_raw_payloads
rendered_private_audio
rendered_private_video
```

## 4. Initial allowlist

```text
FACTORY_PUBLIC_RUNNER_SMOKE
A3479_CONTENT_ONLY_LOCAL_GATE
A3479_CI_SCOPE_GUARD_DOC_GATE
M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET
```

## 5. Artifact policy

```text
PUBLIC_RUNNER_ARTIFACTS_DEFAULT=none
TEXT_EVIDENCE_PUBLIC_ALLOWED_ONLY_IF_SANITIZED=true
AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
```
