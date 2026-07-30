# Gold V2 one-command runner

This directory is an execution/evidence layer. It is not source authority, production policy, quality acceptance authority, or coordinator authority.

The single entrypoint is `python3 scripts/gold_v2/runner.py`. Modes are `validate-only`, `compile`, `pre-render-evidence`, and `render`.

Every mode requires an exact live-OC-bound authorization manifest. Source package identity includes exact repository head, relative path, SHA-256 and Git blob SHA. Higher modes require strict exact output file sets. Compiler reproducibility is checked in two independent detached exact-head checkouts. Preview artifacts are always `NON_ACCEPTED_RECORDING_CANDIDATE`; production artifacts are `ACCEPTED` only with exact quality/coordinator PASS receipts and no unresolved Human review gates.

The workflow is `workflow_call` only, must itself be invoked at the exact runner SHA, pins every third-party action to an immutable commit, stores manifest/workspace outside the checkout, and uses transport credentials only for exact repository fetches. Credentials are scrubbed before provider/compiler/runtime commands.

Single-use manifests require a durable ledger path shared across invocations. Claims are atomically serialized and consumed only after live OC verification.

Development validation:

```bash
python3 -m unittest discover -s tests/gold_v2 -p 'test_*.py' -v
```

Fixture tests do not dispatch a workflow and do not start DOM evidence, still rendering, or video rendering.
