# Public Runner Dispatch Runbook v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_DISPATCH_RUNBOOK_v01
STATUS=ACTIVE_THREE_REPO_FACTORY_RUNBOOK_CURRENT_ALLOWLIST_A3480
FACTORY_ID=AI_COURSE_FACTORY
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
CURRENT_PRODUCTION_STAGE=A3502_STILL_FRAME_QC_GATE_NO_FULL_RENDER
NO_FAKE_GREEN=true
```

## 1. Read before dispatch

```text
RUNNER_CONTRACT=00_contracts/PUBLIC_RUNNER_CENTER_CONTRACT_v01.md
RUNNER_BACKLOG=docs/FACTORY_RUNNER_AUTOMATION_BACKLOG_v01.md
PRODUCTION_OC=TheGor-365/ai-course-production-system:00_control/FACTORY_OPERATION_CENTER.md
PRODUCTION_MACHINE_STATE=TheGor-365/ai-course-production-system:00_control/FACTORY_CURRENT_STATE_INDEX_v01.json
```

Do not dispatch a gate merely because a similarly named production validator exists. The exact gate ID must be present in both the workflow choice list and `scripts/run_allowlisted_validator.sh`.

## 2. Safety model

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
PRIVATE_REPOS_ARE_SOURCE_OF_TRUTH=true
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PUBLIC_AUDIO_ARTIFACTS=true
NO_PUBLIC_VIDEO_ARTIFACTS=true
NO_ARBITRARY_SHELL_INPUT=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
PUBLIC_RUNNER_ARTIFACTS_DEFAULT=none
PRODUCTION_PROMOTION_REQUIRES_PRIVATE_REPO_WRITEBACK=true
```

## 3. Generic validator dispatch

```bash
gh workflow run run-private-validator.yml \
  --repo TheGor-365/ai-course-actions-runner \
  --ref main \
  -f private_repo=<allowlisted_private_repo> \
  -f private_branch=<private_branch> \
  -f private_sha=<exact_40_character_private_sha> \
  -f gate_id=<allowlisted_gate_id> \
  -f status_context=public-runner/<module>/<lesson>/<gate> \
  -F write_status=true \
  -F write_pr_comment=true \
  -f private_pr=<private_pr_number>
```

## 4. Dispatch preflight

Before dispatch, record:

```text
PRIVATE_REPO_ALLOWLISTED=true
PRIVATE_BRANCH_HEAD_EQUALS_PRIVATE_SHA=true
PRIVATE_SHA_LENGTH=40
GATE_ID_ALLOWLISTED_IN_WORKFLOW=true
GATE_ID_IMPLEMENTED_IN_SCRIPT=true
EXPECTED_OUTPUT_IS_SANITIZED=true
STATUS_CONTEXT_UNIQUE=true
PRIVATE_PR_EXISTS_if_comment_requested=true
```

## 5. Current gate capability matrix

| Gate | Private repo | Validation strength | Current use |
|---|---|---|---|
| `FACTORY_PUBLIC_RUNNER_SMOKE` | production or source | connectivity / exact SHA smoke | infrastructure check |
| `A3479_CONTENT_ONLY_LOCAL_GATE` | production | bounded contract validation | historical proven gate |
| `A3479_CI_SCOPE_GUARD_DOC_GATE` | production | file inventory only | smoke; not production GREEN |
| `M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET` | production or source | count-only inventory | smoke; not semantic import validation |
| `A3480_SCRIPT_FIT_PACK_LOCAL_GATE` | production | bounded text/prosody contract validation | supported text-only gate |

```text
CURRENT_ALLOWLIST_MAX_STAGE=A3480_TEXT_ONLY
A3502_NO_RENDER_GATE_AVAILABLE=false
A3502_STILL_RENDER_GATE_AVAILABLE=false
A3502_VIDEO_RENDER_GATE_AVAILABLE=false
```

## 6. Proven A3479 example

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

```text
SMOKE_RUN_ID=29004760312
A3479_PRIMARY_RUN_ID=29004920199
A3479_DUPLICATE_RUN_ID=29005272141
A3479_PR121_MERGED=true
A3479_MERGE_SHA=6636e7ea4ab200a88e6528755e46034b2592f88d
```

## 7. Current A3502 rule

Do not dispatch A3502 through this repository yet.

```text
A3502_CURRENT_EXECUTION_REPO=TheGor-365/ai-course-production-system
A3502_CURRENT_EXECUTION_HOST=locked_private_Linux_x86_64
A3502_CURRENT_COMMAND_CLASS=TypeScript_static_validator_Remotion_composition_enumeration_no_render
A3502_REQUIRES_LOCAL_EXACT_DEPENDENCY_AND_FONT_LOCKS=true
A3502_PUBLIC_RUNNER_GATE_NOT_IMPLEMENTED=true
```

The current local reference PASS must be obtained first. Only then should a separate engineering PR add a sanitized runner gate.

## 8. Inspect a dispatched run

```bash
gh run watch <public_run_id> --repo TheGor-365/ai-course-actions-runner
gh run view <public_run_id> --repo TheGor-365/ai-course-actions-runner --log
```

The run may be classified as a validator failure only when actual job steps or logs identify the failing gate. A workflow conclusion without steps/logs is infrastructure-unknown evidence.

## 9. Acceptance criteria

```text
JOB_COMPLETED=true
POLICY_GUARD_RAN=true
PRIVATE_BRANCH_HEAD_VERIFIED=true
PRIVATE_SHA_BOUND=true
ALLOWLISTED_GATE_RAN=true
GATE_RESULT_AND_EXIT_CODE_PRESENT=true
PRIVATE_COMMIT_STATUS_WRITTEN=true_if_requested
PRIVATE_PR_COMMENT_WRITTEN=true_if_requested
PRIVATE_CONTENT_PUBLIC_EXPOSURE=false
PUBLIC_ARTIFACTS_CREATED=false
AUDIO_CREATED=false
VIDEO_CREATED=false
NO_FAKE_GREEN=true
```

## 10. Production consumption

A runner PASS does not mutate production state. The production controller must:

1. verify runner repository, run ID, private SHA, gate ID and status context;
2. verify sanitized output and exit code;
3. create immutable evidence in the private production repository;
4. run the production-side consumption validator;
5. promote only the explicitly authorized gate;
6. update machine state, OC, handoff and automation debt.

## 11. New gate engineering sequence

```text
STEP_1=prove_reference_gate_locally
STEP_2=define_sanitized_input_output_schema
STEP_3=implement_allowlisted_runner_script
STEP_4=add_workflow_choice_and_policy_guard
STEP_5=add_self_tests_and_negative_policy_tests
STEP_6=run_smoke_against_exact_private_SHA
STEP_7=write_private_commit_status_and_PR_comment
STEP_8=add_private_consumption_validator
STEP_9=record_runner_capability_in_three_repo_topology
STEP_10=only_then_use_in_batch_orchestrator
```
