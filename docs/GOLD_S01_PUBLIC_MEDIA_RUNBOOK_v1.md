# Gold S01 public media runner v1

```text
ROLE=PUBLIC_GITHUB_HOSTED_MEDIA_EXECUTION_WORKER
FACTORY_ID=AI_COURSE_FACTORY
REFERENCE_CELL=M1_L01_S01_RU
EXECUTION_LAYER=public_github_hosted_runner
PUBLIC_WORKFLOW_EXECUTION_ALLOWED=true
PUBLIC_ACTIONS_ARTIFACT_UPLOAD_ALLOWED=true
PRIVATE_RUNNER_REQUIRED=false
SELF_HOSTED_RUNNER_REQUIRED=false
LOCKED_PRIVATE_LINUX_HOST_REQUIRED=false
LEGACY_PRIVATE_HOST_PATH=LEGACY_COMPATIBILITY_ONLY
MAIN_MERGE_AUTHORIZED=false
NO_FAKE_GREEN=true
```

## Active contour

The active entrypoint is `.github/workflows/gold-s01-public-media-render.yml`.

Primary trigger is a push to `repair/gold-s01-public-media-runner-v1`. `workflow_dispatch` exists only for an exact rerun with the same bounded fields. The workflow does not accept shell, command, script path or arbitrary arguments.

The runner uses the existing `PRIVATE_REPO_PAT` only to clone `TheGor-365/ai-course-production-system`, prove the exact branch head, checkout a detached exact SHA and bind the exact request path, Git blob SHA and SHA-256. Private repository content is not printed or archived.

## Fixed production contract

```text
FIXED_PRODUCTION_ADAPTER_PATH=11_tools/render_factory/gold_s01_private_execution_v1.py
FIXED_ADAPTER_INTERFACE=--request <exact_path> --render-mode pilot_60s|full_15m --output-dir <ephemeral> --receipt-dir <ephemeral>
FULL_COMPOSITION_ID=GoldS01FullVisualMaster
PILOT_DURATION_SECONDS=60
FULL_DURATION_SECONDS=900
RESOLUTION=1920x1080
FPS=30
VIDEO_CODEC=h264
AUDIO_CODEC=aac_when_included
```

The adapter must emit the expected MP4 and `adapter_qc.json`. The QC document must explicitly pass blank-frame, unexpected freeze, duplicate-frame, caption-collision, internal-ID leakage, technical-surface readability, audio/caption identity and scene/mode coverage checks. Missing composition, adapter, package lock, output or QC proof fails closed.

## Public artifacts

Only MP4, VTT/JSON captions, ffprobe JSON, QC JSON, SHA256SUMS and sanitized receipts are permitted. Media binaries remain outside Git. Private repository archives, secrets and raw provider payloads are forbidden.

Pilot PASS automatically continues to the full 15-minute render. The workflow re-downloads the primary artifact and verifies the contained MP4 SHA before posting sanitized receipts to production PRs #350, #346, #348 and issue #344.

Human Owner final video acceptance remains false until the owner reviews the actual preview.
