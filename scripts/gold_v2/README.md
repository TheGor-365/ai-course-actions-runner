# Gold V2 one-command runner

This directory is an execution/evidence layer. It is not source authority, production policy, quality acceptance authority, or coordinator authority.

## Entry point

```bash
python3 scripts/gold_v2/runner.py \
  --mode validate-only \
  --authorization-manifest /absolute/path/authorization.json \
  --workspace /absolute/path/new-workspace
```

Modes are `validate-only`, `compile`, `pre-render-evidence`, and `render`. A higher mode never inherits permission from a branch, pull request, label, environment variable, previous run, artifact presence, deadline, or filename. The manifest must name the requested mode exactly and pass every live-OC binding.

## Authority binding

The manifest is `gold_v2_runner_authorization.v1`. It contains exact source, shared-source, production, runner, compiler, runtime, audio, timing, caption, composition, duration, artifact-state, expiry/single-use, command, binding, and expected-file-set identities applicable to its mode.

`authorization_payload_sha256` is the SHA-256 of canonical JSON after removing only:

- `authorization_payload_sha256`;
- `control_head`;
- `oc_blob_sha`.

Those two Git identities are filled after the OC successor is committed. The exact OC blob must then contain all three lines:

```text
RUNNER_AUTHORIZATION_MANIFEST_ID=<manifest_id>
RUNNER_AUTHORIZED_MODE=<mode>
RUNNER_AUTHORIZATION_PAYLOAD_SHA256=<authorization_payload_sha256>
```

The runner verifies its own clean tracked checkout and exact `runner_head`, fetches and checks out the exact `control_head` detached, verifies that the declared live control branch still points to it, verifies `oc_blob_sha` and `DOCUMENT_ID`, and only then accepts the payload binding. The branch is a freshness check, never permission authority.

## Execution guarantees

- exact 40-character commit heads only;
- detached clean checkouts and optional ancestry leases;
- Git tree, blob, SHA-256, command-log and artifact provenance receipts;
- source package identity, source materialization, source validation, shared-ID bindings and vendored-schema bindings;
- compiler execution twice with byte-identical file maps and exact compiler-output artifact hash;
- exact artifact file sets, `SHA256SUMS`, deterministic ZIPs and receipt-schema checks;
- traversal, absolute path, drive path, backslash path, duplicate, encrypted, symlink, special file, file-count, size, compression-ratio, secret and private-payload rejection;
- accepted audio/timing/caption identities before evidence/render modes;
- exact composition and duration checks for render;
- unresolved aesthetic gates emitted as `REVIEW_REQUIRED`; no automatic aesthetic `PASS`;
- preview state fixed to `NON_ACCEPTED_RECORDING_CANDIDATE`;
- accepted production state requires exact quality and coordinator `PASS` receipts and no unresolved Human review gate.

The reusable workflow is `workflow_call` only. It has no `workflow_dispatch`, push, pull-request, schedule, or branch-derived authorization trigger. Its repository token provides read transport only.

## Development validation

```bash
python3 -m unittest discover -s tests/gold_v2 -p 'test_*.py' -v
```

Fixture tests do not dispatch a workflow and do not start DOM evidence, still rendering, or video rendering.
