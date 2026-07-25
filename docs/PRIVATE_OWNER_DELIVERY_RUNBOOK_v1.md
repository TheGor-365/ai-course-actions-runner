# Private Owner Delivery Runbook v1

```text
CHANNEL_CLASS=private_local_capability_channel
AUTHORITATIVE_ENTRYPOINT=scripts/run_private_owner_delivery_exact_v1.py
VISUAL_ASSEMBLER=production:11_tools/render_factory/visual_runtime_v1/owner_review_pack.py
VISUAL_GATE=runner_PR_9
PUBLIC_WORKFLOW_EXECUTION_ALLOWED=false
PUBLIC_ARTIFACT_UPLOAD_ALLOWED=false
PRIVATE_MEDIA_IN_GIT=false
NO_FAKE_GREEN=true
```

## Supported delivery artifacts

- `contact_sheet`: assembled from the exact authorized 17-still manifest by the validated visual owner-pack builder;
- `still_archive`: deterministic full-resolution ZIP of the same 17 stills;
- `cross_scene_clip`: delivery and registration of a pre-existing exact authorized private clip;
- `RU_preview`: delivery and registration of a pre-existing exact authorized private preview.

The first profile also causes the visual builder to create its private HTML index, checksum ledger, visual owner manifest and human-decision receipt inside private staging. The runner registers and exposes only the authorized contact sheet and still archive plus its sanitized delivery manifest and receipts.

Cross-scene clip and RU preview require an accepted timing contract, exact audio head, exact SHA-256 and size for each source artifact. This component does not authorize or perform a media render.

## Security boundary

The authoritative entrypoint refuses GitHub Actions execution. Media bytes, capability token, store paths and delivery paths stay on the locked private host. Git receives only the exact request, schemas, sanitized manifest, pointers, hashes, sizes and receipts. The owner pointer has the form `private-owner-delivery://<channel>/<package>` and requires a local capability token stored with mode `0600`.

The implementation module `private_owner_delivery_v1.py` is internal. Real execution must use `run_private_owner_delivery_exact_v1.py`, which invokes the exact production visual owner-pack builder and finalizes the receipt chain so the restore receipt references the canonical final registration receipt hash and the owner manifest references both final receipt hashes.

## Real execution sequence

1. Detach an exact clean production checkout at the authorized visual-runtime SHA.
2. Validate the committed request and separate visual content authority SHA.
3. Validate the input manifest Git blob and every private input SHA and size.
4. Run the fixed visual owner-pack builder or adopt only allowlisted pre-existing video outputs.
5. Copy each authorized output into the content-addressed store, backup store and owner channel.
6. Emit the sanitized final registration receipt.
7. Restore every artifact into scratch, verify SHA and size, then delete scratch.
8. Emit the restore receipt bound to the final registration hash.
9. Emit the Git-safe owner delivery manifest bound to both final receipt hashes.

A controlled `--inject-failure-after-registration 1` run returns exit `75` and a private resume token. Resume skips the already verified registration and completes without replaying it.
