# Public Runner Dispatch Runbook v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_DISPATCH_RUNBOOK_v01
STATUS=ACTIVE_PUBLIC_RUNNER_RUNBOOK_A3480_TEXT_GATE_READY
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
PRIVATE_CONTENT_SOURCE_OF_TRUTH=false
NO_FAKE_GREEN=true
```

## 1. Safety model

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
PRIVATE_REPOS_ARE_SOURCE_OF_TRUTH=true
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PUBLIC_AUDIO_ARTIFACTS_BY_DEFAULT=true
NO_ARBITRARY_SHELL_INPUT=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
PUBLIC_RUNNER_ARTIFACTS_DEFAULT=none
PUBLIC_RUNNER_TEXT_VALIDATION_ONLY_FOR_NOW=true
```

## 2. Smoke command

```bash
gh workflow run run-private-status-writeback-smoke.yml \
  --repo TheGor-365/ai-course-actions-runner \
  --ref main \
  -f private_repo=TheGor-365/ai-course-production-system \
  -f private_branch=<private_branch> \
  -f private_sha=<private_sha> \
  -f status_context=public-runner/factory/smoke
```

## 3. Validator command

```bash
gh workflow run run-private-validator.yml \
  --repo TheGor-365/ai-course-actions-runner \
  --ref main \
  -f private_repo=TheGor-365/ai-course-production-system \
  -f private_branch=<private_branch> \
  -f private_sha=<private_sha> \
  -f gate_id=<allowlisted_gate_id> \
  -f status_context=public-runner/<module>/<lesson>/<gate> \
  -F write_status=true \
  -F write_pr_comment=true \
  -f private_pr=<private_pr_number>
```

## 4. Current allowlist

```text
FACTORY_PUBLIC_RUNNER_SMOKE
A3479_CONTENT_ONLY_LOCAL_GATE
A3479_CI_SCOPE_GUARD_DOC_GATE
M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET
A3480_SCRIPT_FIT_PACK_LOCAL_GATE
```

Deferred until audio artifact policy:

```text
DO_NOT_ADD_YET=A3481_TTS_CANDIDATE_POLICY_GATE,A3482_AUDIO_RENDER_POLICY_GATE
A3480_IS_TEXT_PROSODY_ONLY=true
PUBLIC_RUNNER_AUDIO_RENDER=false_until_external_private_artifact_store_exists
```

## 5. Proven A3479 command

```bash
gh workflow run run-private-validator.yml \
  --repo TheGor-365/ai-course-actions-runner \
  --ref main \
  -f private_repo=TheGor-365/ai-course-production-system \
  -f private_branch=factory/a3479-target-timing-contract-content-only-v01 \
  -f private_sha=d05d0820fe248b601c24215a591978285253ca5d \
  -f gate_id=A3479_CONTENT_ONLY_LOCAL_GATE \
  -f status_context=public-runner/M1-L01/A3479-content-only \
  -F write_status=true \
  -F write_pr_comment=true \
  -f private_pr=121
```

Known successful runs:

```text
SMOKE_RUN_ID=29004760312
A3479_PRIMARY_RUN_ID=29004920199
A3479_DUPLICATE_RUN_ID=29005272141
A3479_PR121_MERGED=true
A3479_MERGE_SHA=6636e7ea4ab200a88e6528755e46034b2592f88d
```

## 6. Planned A3480 command

Use only after the A3480 private production PR exists.

```bash
gh workflow run run-private-validator.yml \
  --repo TheGor-365/ai-course-actions-runner \
  --ref main \
  -f private_repo=TheGor-365/ai-course-production-system \
  -f private_branch=factory/a3480-ru-script-fit-prosody-source-contract-v01 \
  -f private_sha=<exact_40_char_sha> \
  -f gate_id=A3480_SCRIPT_FIT_PACK_LOCAL_GATE \
  -f status_context=public-runner/M1-L01/A3480-script-fit-pack \
  -F write_status=true \
  -F write_pr_comment=true \
  -f private_pr=<A3480_pr_number>
```

A3480 gate output is sanitized and must not print full RU script text.

## 7. Inspect command

```bash
gh run watch <public_run_id> --repo TheGor-365/ai-course-actions-runner
```

## 8. Acceptance criteria

```text
JOB_COMPLETED=true
JOB_CONCLUSION=success|failure
POLICY_GUARD_RAN=true
PRIVATE_BRANCH_HEAD_VERIFIED=true
PRIVATE_SHA_BOUND=true
ALLOWLISTED_GATE_RAN=true
PRIVATE_COMMIT_STATUS_WRITTEN=true
PRIVATE_PR_COMMENT_WRITTEN=true_if_requested
PRIVATE_CONTENT_PUBLIC_EXPOSURE=false
PUBLIC_ARTIFACTS_CREATED=false
AUDIO_CREATED=false
VIDEO_CREATED=false
NO_FAKE_GREEN=true
```
