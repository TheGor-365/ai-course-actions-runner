# Private Owner Delivery Runbook v1

```text
CHANNEL_CLASS=private_local_capability_channel
PUBLIC_WORKFLOW_EXECUTION_ALLOWED=false
PUBLIC_ARTIFACT_UPLOAD_ALLOWED=false
PRIVATE_MEDIA_IN_GIT=false
NO_FAKE_GREEN=true
```

## Supported delivery artifacts

- `contact_sheet`: assembled from the exact authorized 17-still manifest;
- `still_archive`: deterministic full-resolution TAR of the same 17 stills;
- `cross_scene_clip`: delivery and registration of a pre-existing exact authorized private clip;
- `RU_preview`: delivery and registration of a pre-existing exact authorized private preview.

The latter two require an accepted timing contract, exact audio head, exact SHA-256 and size for each source artifact. This component does not authorize or perform a media render.

## Security boundary

The executor refuses GitHub Actions execution. Media bytes, capability token, store paths and delivery paths stay on the locked private host. Git receives only the exact request, schemas, sanitized manifest, pointers, hashes, sizes and receipts. The owner pointer has the form `private-owner-delivery://<channel>/<package>` and requires a local capability token stored with mode `0600`.

## Real execution sequence

1. Detach an exact clean production checkout at the authorized SHA.
2. Validate the committed request.
3. Validate the input manifest Git blob and every private input SHA and size.
4. Assemble or adopt only allowlisted outputs.
5. Copy each output into the content-addressed store, backup store and owner channel.
6. Emit the sanitized registration receipt.
7. Restore every artifact into scratch, verify SHA and size, then delete scratch.
8. Emit the restore receipt and Git-safe owner delivery manifest.

A controlled `--inject-failure-after-registration 1` run returns exit `75` and a private resume token. Resume skips the already verified registration and completes without replaying it.
