# Public Runner Dispatch Runbook v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_DISPATCH_RUNBOOK_v01
STATUS=ACTIVE_LAUNCH_5D_DAY1
FACTORY_ID=AI_COURSE_FACTORY
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
NO_FAKE_GREEN=true
```

## 1. Read before dispatch

```text
RUNNER_CONTRACT=00_contracts/PUBLIC_RUNNER_CENTER_CONTRACT_v01.md
RUNNER_BACKLOG=docs/FACTORY_RUNNER_AUTOMATION_BACKLOG_v01.md
FIXED_GATE_MANIFEST=config/public_gate_manifest_v1.json
SELF_VALIDATOR=scripts/runner_infrastructure_v1.py validate-contract
```

A gate is dispatchable only when the self-validator passes and the gate exists in the workflow, manifest, dispatcher, contract and this runbook.

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
```

## 3. Generic validator dispatch

```bash
gh workflow run run-private-validator.yml \
  --repo TheGor-365/ai-course-actions-runner \
  --ref <reviewed-runner-sha-or-branch> \
  -f private_repo=<allowlisted_private_repo> \
  -f private_branch=<private_branch> \
  -f private_sha=<exact_40_character_private_sha> \
  -f gate_id=<allowlisted_gate_id> \
  -f request_id=<stable_request_id> \
  -f status_context=public-runner/<module>/<lesson>/<gate> \
  -F write_status=true \
  -F write_pr_comment=false
```

No command, shell, script path or validator path input exists.

## 4. Dispatch preflight

```text
RUNNER_CONTRACT_SELF_VALIDATOR=PASS
PRIVATE_REPO_ALLOWLISTED=true
PRIVATE_BRANCH_HEAD_EQUALS_PRIVATE_SHA=true
PRIVATE_SHA_LENGTH=40
GATE_ID_ALLOWLISTED_IN_MANIFEST=true
GATE_ID_ALLOWLISTED_IN_WORKFLOW=true
GATE_ID_IMPLEMENTED_IN_DISPATCHER=true
EXPECTED_OUTPUT_IS_SANITIZED=true
STATUS_CONTEXT_UNIQUE=true
REQUEST_ID_STABLE=true
PUBLIC_ARTIFACTS_EXPECTED=none
```

## 5. Current gate capability matrix

| Gate | Private repo | Validation strength | Current use |
|---|---|---|---|
| `FACTORY_PUBLIC_RUNNER_SMOKE` | production or source | connectivity / exact SHA smoke | infrastructure check |
| `A3479_CONTENT_ONLY_LOCAL_GATE` | production | bounded contract validation | historical gate |
| `A3479_CI_SCOPE_GUARD_DOC_GATE` | production | file inventory only | not production GREEN |
| `M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET` | production or source | count-only inventory | not semantic validation |
| `A3480_SCRIPT_FIT_PACK_LOCAL_GATE` | production | bounded text/prosody contract | supported text-only gate |
| `FACTORY_LAUNCH_CONTROL_PLANE_GATE` | production | bounded launch plan and OC metadata | Day 1 launch control-plane check; not A3502 |

## 6. Launch control-plane gate

Required fixed private paths:

```text
00_control/FACTORY_5_DAY_LAUNCH_PLAN_v01.md
00_control/FACTORY_OPERATION_CENTER.md
```

Sanitized output:

```text
private_sha
control_file_count
launch_plan_sha256
operation_center_sha256
no_fake_green_declared
public_media_allowed=false
output_schema_hash
private_content_public_exposure=false
artifacts_created=false
```

Non-claims:

```text
A3502_GATE_AVAILABLE=false
MEDIA_RENDERED=false
PRODUCTION_GREEN=false
RELEASE_GREEN=false
```

## 7. Current A3502 rule

Do not dispatch A3502 through this repository yet.

```text
A3502_CURRENT_EXECUTION_HOST=locked_private_Linux_x86_64
A3502_PUBLIC_RUNNER_GATE_NOT_IMPLEMENTED=true
A3502_PUBLIC_MEDIA_RENDER_ALLOWED=false
```

## 8. Private executor fixture

Local/private-host reference command:

```bash
python3 scripts/runner_infrastructure_v1.py execute-fixture \
  --request fixtures/private_executor/request_attempt_1.json \
  --state-dir <private_state_dir> \
  --artifact-dir <private_artifact_dir> \
  --receipt <private_receipt_path> \
  --inject-failure-once
```

Retry with the emitted resume token in a second request. Stdout is sanitized; private pointers exist only in the private receipt file.

## 9. Acceptance criteria

```text
POLICY_GUARD_RAN=true
PRIVATE_BRANCH_HEAD_VERIFIED=true
PRIVATE_SHA_BOUND=true
ALLOWLISTED_GATE_RAN=true
GATE_RESULT_AND_EXIT_CODE_PRESENT=true
OUTPUT_SCHEMA_HASH_PRESENT=true
PRIVATE_CONTENT_PUBLIC_EXPOSURE=false
PUBLIC_ARTIFACTS_CREATED=false
AUDIO_CREATED=false
VIDEO_CREATED=false
NO_FAKE_GREEN=true
```

## 10. Production consumption

A public runner PASS does not mutate production state. Production must validate runner SHA, run ID, private SHA, gate ID, request ID, status context, exit code and output schema hash before any bounded state transition.
