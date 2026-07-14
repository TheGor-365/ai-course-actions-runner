# Factory Runner Automation Backlog v01

```text
DOCUMENT_ID=FACTORY_RUNNER_AUTOMATION_BACKLOG_v01
STATUS=ACTIVE_BACKLOG_FROM_REFERENCE_CELL_A3502
FACTORY_ID=AI_COURSE_FACTORY
OWNER_REPO=TheGor-365/ai-course-actions-runner
CURRENT_PRODUCTION_STAGE=A3502_STILL_FRAME_QC_GATE_NO_FULL_RENDER
NO_FAKE_AUTOMATION_CLAIMS=true
```

## 1. Purpose

This backlog translates proven manual/private reference-cell operations into future allowlisted automated execution gates. It does not authorize the gates by itself.

## 2. Current capabilities

```text
EXACT_PRIVATE_SHA_CHECKOUT=true
PRIVATE_BRANCH_HEAD_VERIFICATION=true
PRIVATE_REPO_ALLOWLIST=true
GATE_ID_ALLOWLIST=true
SANITIZED_TEXT_OUTPUT=true
PRIVATE_COMMIT_STATUS_WRITEBACK=true
OPTIONAL_PRIVATE_PR_COMMENT=true
PUBLIC_BINARY_ARTIFACTS_DEFAULT_NONE=true
CURRENT_REAL_BOUNDED_GATES=A3479_CONTENT_ONLY_LOCAL_GATE,A3480_SCRIPT_FIT_PACK_LOCAL_GATE
```

## 3. Current capability limitations

```text
GENERAL_PURPOSE_SHELL_ALLOWED=false
DYNAMIC_VALIDATOR_PATH_INPUT_ALLOWED=false
A3502_GATE_IMPLEMENTED=false
EXACT_FONT_CONTAINER_IMAGE=false
REMOTION_BROWSER_IMAGE=false
PRIVATE_ARTIFACT_STORE_CONNECTION=false
SELF_HOSTED_PRIVATE_RENDER_RUNNER=false
MEDIA_ARTIFACT_POINTER_WRITEBACK=false
PACKAGE_STATE_MACHINE=false
BATCH_DISPATCH=false
RESUME_RETRY=false
```

## 4. Backlog ordering

### R01 — Runner contract self-validator

```text
GOAL=validate_workflow_allowlist_matches_script_case_allowlist_and_docs_matrix
INPUTS=runner_repo_SHA
OUTPUTS=allowlist_consistency_result
MEDIA=false
PRIORITY=P0
```

### R02 — Generic sanitized metadata-validator gate framework

```text
GOAL=reduce_duplicate_gate_shell_while_preserving_no_arbitrary_shell
MODEL=gate_ID_to_fixed_script_manifest
INPUTS=private_repo,branch,SHA,gate_ID
OUTPUTS=fixed_sanitized_schema
PRIORITY=P0
```

### R03 — A3502 no-render composition validation gate

```text
PREREQUISITE=local_private_reference_PASS
GOAL=run_TypeScript_static_validator_and_composition_enumeration_reproducibly
REQUIRES=node_and_Remotion_lock,fonts_or_container,browser_policy,sanitized_output,negative_tests
MEDIA=false
PRIVATE_ARTIFACT_STORE_REQUIRED=false
PRIORITY=P1_after_A3502_local_PASS
```

### R04 — Production-side runner evidence consumer

```text
OWNER_REPO=TheGor-365/ai-course-production-system
GOAL=validate_runner_repo_run_ID_private_SHA_gate_ID_status_context_exit_code_and_output_hash
OUTPUT=immutable_private_evidence_and_bounded_state_transition
PRIORITY=P1
```

### R05 — Package state-machine dispatcher

```text
GOAL=dispatch_next_authorized_non_media_station_from_machine_state
REQUIRES=package_state_schema,station_manifest,authorization_manifest,retry_taxonomy
PRIORITY=P2_after_reference_cell
```

### R06 — Resume/retry controller

```text
GOAL=resume_from_last_green_state_without_repeating_closed_work
REQUIRES=immutable_attempt_records,failure_classification,idempotent_station_contracts
PRIORITY=P2
```

### R07 — Self-hosted private render executor contract

```text
GOAL=execute_stills_clips_and_full_private_preview_without_public_media_exposure
EXECUTION_CLASS=self_hosted_private_runner_or_locked_private_host
REQUIRES=host_locks,private_artifact_store,artifact_pointer_writeback,resource_limits,cleanup_policy
PUBLIC_RUNNER_MEDIA=false
PRIORITY=P2_after_A3502_machine_and_human_still_QC
```

### R08 — Artifact pointer writeback

```text
GOAL=write_only_hash_size_codec_duration_private_location_pointer_and_QC_identity_to_production
RAW_BINARY_IN_GIT=false
PRIORITY=P2
```

### R09 — Batch package orchestrator

```text
GOAL=generate_remaining_S02_S06_and_later_packages_without_manual_chat_replication
REQUIRES=reference_cell_green,station_graph,state_machine,artifact_registry,resume_retry,human_gate_queue
PRIORITY=P3
```

### R10 — Cross-repository synchronization validator

```text
GOAL=detect_stale_role_OC_handoff_and_runner_capability_mirrors_across_three_repositories
INPUTS=exact_heads_or_declared_sync_epoch
OUTPUTS=drift_report_only_until_bounded_repair_authorized
PRIORITY=P1
```

## 5. Required tests for every new gate

```text
POSITIVE_VALID_FIXTURE=true
NEGATIVE_REPO_NOT_ALLOWLISTED=true
NEGATIVE_GATE_NOT_ALLOWLISTED=true
NEGATIVE_SHA_NOT_40_HEX=true
NEGATIVE_BRANCH_SHA_MISMATCH=true
NEGATIVE_PRIVATE_CONTENT_LEAK_PATTERN=true
NEGATIVE_UNEXPECTED_ARTIFACT=true
NEGATIVE_OUTPUT_SCHEMA_DRIFT=true
TIMEOUT_TEST=true
STATUS_WRITEBACK_TEST=true
PR_COMMENT_SANITIZATION_TEST=true
```

## 6. Runner-to-production evidence schema target

```text
schema_version
factory_id
runner_repo
runner_sha
public_run_id
public_job_id
private_repo
private_branch
private_sha
gate_id
status_context
start_time
end_time
exit_code
result
sanitized_metrics
output_schema_hash
private_content_public_exposure
artifacts_created
consumption_status
```

## 7. Media boundary

```text
GITHUB_HOSTED_PUBLIC_RUNNER_AUDIO_RENDER_ALLOWED=false
GITHUB_HOSTED_PUBLIC_RUNNER_VIDEO_RENDER_ALLOWED=false
PRIVATE_SELF_HOSTED_MEDIA_EXECUTOR_DESIGN_REQUIRED=true
BINARY_MEDIA_MUST_STAY_OUTSIDE_GIT_REPOSITORIES=true
MEDIA_EVIDENCE_MUST_USE_POINTER_HASH_SIZE_AND_QC=true
```

## 8. Current next action

```text
RUNNER_ENGINEERING_ACTION_NOW=none_until_A3502_local_no_render_validation_PASS
FOLLOWING_ACTION=design_R03_and_R04_from_proven_local_worker_contract
CURRENT_PRODUCTION_ACTION=run_A3502_no_render_validation_on_locked_private_Linux_host
```
