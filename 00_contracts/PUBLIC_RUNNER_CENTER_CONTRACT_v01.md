# Public Runner Center Contract v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_CENTER_CONTRACT_v01
STATUS=ACTIVE_EXECUTION_PLANE_A3502_FACTORY_SYNC_CURRENT_ALLOWLIST_A3480
FACTORY_ID=AI_COURSE_FACTORY
REPO=TheGor-365/ai-course-actions-runner
ROLE=execution_only_machine_shop
NO_FAKE_GREEN=true
```

## 1. Complete factory boundary

```text
PRODUCTION_CONTROL_REPO=TheGor-365/ai-course-production-system
SOURCE_LIBRARY_REPO=TheGor-365/ai-course-source-library
EXECUTION_RUNNER_REPO=TheGor-365/ai-course-actions-runner
THREE_REPO_FACTORY=true
```

## 2. Authority model

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
CURRENT_FACTORY_STATE_AUTHORITY=TheGor-365/ai-course-production-system
SOURCE_AND_GOLD_AUTHORITY=TheGor-365/ai-course-source-library
RUNNER_AUTHORITY=execution_evidence_only_when_bound_to_exact_private_SHA
PRODUCTION_PROMOTION_AUTHORITY=false
FINAL_RELEASE_AUTHORITY=false
PRIVATE_ACTIONS_GREEN=false
```

A runner PASS means only that the specified allowlisted gate passed against the exact private SHA. It does not independently promote production state.

## 3. Safety boundaries

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
PUBLIC_ARTIFACTS_DEFAULT=none
```

## 4. Allowed execution model

The runner may:

1. accept only an allowlisted private repository;
2. accept an explicit branch and full 40-character SHA;
3. verify that branch head equals the supplied SHA;
4. execute only a named allowlisted gate;
5. print only sanitized compact evidence;
6. write a commit status and optional compact PR comment.

Required evidence fields:

```text
runner_repo
public_run_id
private_repo
private_branch
private_sha
gate_id
status_context
exit_code
result
sanitized_counts_or_hashes
private_content_public_exposure=false
```

## 5. Current private repository allowlist

```text
ALLOWLISTED_PRIVATE_REPO_1=TheGor-365/ai-course-production-system
ALLOWLISTED_PRIVATE_REPO_2=TheGor-365/ai-course-source-library
```

## 6. Current gate allowlist

```text
FACTORY_PUBLIC_RUNNER_SMOKE
A3479_CONTENT_ONLY_LOCAL_GATE
A3479_CI_SCOPE_GUARD_DOC_GATE
M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET
A3480_SCRIPT_FIT_PACK_LOCAL_GATE
```

Capability classification:

```text
FACTORY_PUBLIC_RUNNER_SMOKE=connectivity_and_exact_SHA_smoke
A3479_CONTENT_ONLY_LOCAL_GATE=real_bounded_contract_validator
A3479_CI_SCOPE_GUARD_DOC_GATE=inventory_only_not_production_green
M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET=count_only_smoke_not_full_import_validation
A3480_SCRIPT_FIT_PACK_LOCAL_GATE=real_bounded_text_contract_validator
```

The count-only gates must not be described as semantic production validation.

## 7. Current factory stage and execution gap

```text
SYNC_EPOCH=FACTORY_THREE_REPO_A3502_OC_RECONCILIATION_v01
RUNNER_AUDIT_BASE_SHA=0a32d184829456125401f25ffa8ffec0255d4a71
CURRENT_PRODUCTION_STAGE=A3502_STILL_FRAME_QC_GATE_NO_FULL_RENDER
CURRENT_PRODUCTION_NEXT_SAFE_STEP=run_no_render_TypeScript_static_validator_and_Remotion_composition_enumeration_on_locked_Linux_host
RUNNER_A3502_GATE_IMPLEMENTED=false
RUNNER_A3502_RENDER_ALLOWED=false
CURRENT_A3502_EXECUTION_PATH=private_locked_Linux_host
```

## 8. Conditions for adding a new runner gate

A gate may be added only when all are true:

```text
GATE_INPUT_SCHEMA_DEFINED=true
GATE_OUTPUT_SCHEMA_DEFINED=true
PRIVATE_CONTENT_SANITIZATION_PROVEN=true
ARBITRARY_COMMAND_INPUT_ABSENT=true
EXACT_PRIVATE_SHA_BINDING=true
REPRODUCIBLE_DEPENDENCIES_DEFINED=true
EXECUTION_HOST_REQUIREMENTS_DECLARED=true
TIMEOUT_AND_RESOURCE_LIMITS_DEFINED=true
FAILURE_CODES_DEFINED=true
STATUS_CONTEXT_DEFINED=true
PRODUCTION_CONSUMPTION_VALIDATOR_DEFINED=true
NON_CLAIMS_DEFINED=true
```

## 9. A3502 runner migration requirements

Before A3502 metadata validation can run here:

```text
A3502_SANITIZED_GATE_SCRIPT_REQUIRED=true
EXACT_NODE_REMOTION_DEPENDENCY_BOOTSTRAP_REQUIRED=true
EXACT_FONT_INSTALL_OR_CONTAINER_IMAGE_REQUIRED=true
BROWSER_PROVISIONING_POLICY_REQUIRED=true
HOST_CODEC_LOCK_COMPATIBILITY_POLICY_REQUIRED=true
PRIVATE_ARTIFACT_STORE_NOT_REQUIRED_FOR_NO_RENDER_GATE=true
PUBLIC_MEDIA_ARTIFACTS_FORBIDDEN=true
PRODUCTION_SHA_AND_LOCK_IDENTITY_REQUIRED=true
```

Before any media render can use an automated runner, a separate private/self-hosted runner contract and private artifact-store policy are required. Public GitHub-hosted media output remains forbidden.

## 10. Artifact policy

```text
TEXT_EVIDENCE_PUBLIC_ALLOWED_ONLY_IF_SANITIZED=true
AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
PUBLIC_RUNNER_UPLOAD_ARTIFACT_AUDIO=false
PUBLIC_RUNNER_UPLOAD_ARTIFACT_VIDEO=false
PROVIDER_RAW_PAYLOAD_PUBLICATION=false
PRIVATE_SOURCE_ARCHIVE_PUBLICATION=false
```

## 11. Important-step writeback

When the runner allowlist, workflow contract or execution authority changes:

```text
UPDATE_RUNNER_CENTER_CONTRACT=true
UPDATE_DISPATCH_RUNBOOK=true
UPDATE_RUNNER_AUTOMATION_BACKLOG=true
UPDATE_PRODUCTION_THREE_REPO_TOPOLOGY=true
UPDATE_PRODUCTION_AUTOMATION_PROCESS_MAP=true
UPDATE_CURRENT_PRODUCTION_HANDOFF=true
RECORD_RUNNER_HEAD_AND_PROVEN_RUNS=true
```

## 12. Current next runner action

```text
CURRENT_RUNNER_MODE=standby_execution_plane
NEXT_RUNNER_ENGINEERING_ACTION=design_A3502_no_render_sanitized_gate_after_local_reference_PASS
DO_NOT_ADD_MEDIA_RENDER_GATE=true
DO_NOT_CLAIM_A3502_SUPPORT=true
```
