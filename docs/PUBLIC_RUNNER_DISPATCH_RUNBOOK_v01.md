# Public Runner Dispatch Runbook v01

```text
DOCUMENT_ID=PUBLIC_RUNNER_DISPATCH_RUNBOOK_v01
STATUS=ACTIVE_LAUNCH_5D_DAY2
NO_FAKE_GREEN=true
```

## 1. Read before dispatch

```text
RUNNER_CONTRACT=00_contracts/PUBLIC_RUNNER_CENTER_CONTRACT_v01.md
FIXED_GATE_MANIFEST=config/public_gate_manifest_v1.json
SELF_VALIDATOR=scripts/runner_infrastructure_v1.py validate-contract
```

## 2. Safety model

Exact branch-head equality is mandatory. Public artifacts, private source text, validator stdout, media and provider payloads are forbidden.

## 3. Generic validator dispatch

Use `run-private-validator.yml` with an allowlisted repository, branch, full SHA, gate ID, request ID and status context. No command-like input exists.

## 4. Dispatch preflight

```text
RUNNER_CONTRACT_SELF_VALIDATOR=PASS
PRIVATE_REPO_ALLOWLISTED=true
PRIVATE_BRANCH_HEAD_EQUALS_PRIVATE_SHA=true
GATE_ID_ALLOWLISTED=true
EXPECTED_OUTPUT_IS_SANITIZED=true
PUBLIC_ARTIFACTS_EXPECTED=none
```

## 5. Current gate capability matrix

| Gate | Private repo | Validation strength | Current use |
|---|---|---|---|
| `FACTORY_PUBLIC_RUNNER_SMOKE` | production or source | exact-SHA smoke | infrastructure |
| `A3479_CONTENT_ONLY_LOCAL_GATE` | production | bounded contract | historical |
| `A3479_CI_SCOPE_GUARD_DOC_GATE` | production | inventory only | non-green |
| `M1_L01_IMPORT_VALIDATORS_SAFE_SUBSET` | production or source | count-only | non-semantic |
| `A3480_SCRIPT_FIT_PACK_LOCAL_GATE` | production | bounded text contract | text-only |
| `FACTORY_LAUNCH_CONTROL_PLANE_GATE` | production | launch metadata | Day 1 |
| `CONTENT_SEMANTICS_LAUNCH_GATE` | source | fixed build and validation matrix | Day 2 source handoff |

## 6. Content semantics gate

Fixed private entrypoint:

```text
Module 1/Lesson 1/launch_5d/content_semantics/HANDOFF_v1.json
```

The gate compiles fixed scripts, runs the source-owned tests/builders/validators, rebuilds the immutable S02 request, and emits only counts and hashes. Failure output is represented by a fixed step ID and diagnostic hash; raw private validator output is not printed.

## 7. Non-claims

```text
FINAL_SHOTIR=false
MEASURED_TIMESTAMPS=false
AUDIO_PRODUCTION_GREEN=false
MEDIA_RENDERED=false
PRODUCTION_GREEN=false
RELEASE_GREEN=false
```

## 8. Private executor fixture

Fixture evidence remains interface-only. It is not actual S01 execution.

## 9. Acceptance criteria

```text
POLICY_GUARD_RAN=true
PRIVATE_BRANCH_HEAD_VERIFIED=true
PRIVATE_SHA_BOUND=true
ALLOWLISTED_GATE_RAN=true
RESULT_AND_EXIT_CODE_PRESENT=true
OUTPUT_SCHEMA_HASH_PRESENT=true
PRIVATE_CONTENT_PUBLIC_EXPOSURE=false
PUBLIC_ARTIFACTS_CREATED=false
NO_FAKE_GREEN=true
```

## 10. Production consumption

Production must validate runner SHA, run ID, private SHA, gate ID, request ID, status context, result, exit code and output schema hash before bounded writeback.
