# AI Course Actions Runner

```text
DOCUMENT_ID=AI_COURSE_ACTIONS_RUNNER_README
STATUS=PUBLIC_RUNNER_CENTER_BOOTSTRAP
ROLE=execution_only_public_github_actions_layer
```

This repository is the public execution-only runner center for the private AI course factory.

Private repositories remain the source of truth. This public repository must not store private course content, private repository archives, rendered private audio/video, provider responses, or full private documents.

```text
PUBLIC_RUNNER_REPO_IS_EXECUTION_ONLY=true
PRIVATE_REPOS_ARE_SOURCE_OF_TRUTH=true
NO_PRIVATE_CONTENT_IN_PUBLIC_LOGS=true
NO_PUBLIC_AUDIO_ARTIFACTS_BY_DEFAULT=true
ALLOWLISTED_GATES_ONLY=true
NO_ARBITRARY_SHELL_INPUT=true
EVERY_RUN_BINDS_TO_PRIVATE_SHA=true
EVERY_GREEN_HAS_EVIDENCE=true
NO_FAKE_GREEN=true
PRIVATE_ACTIONS_GREEN=false
AUDIO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
VIDEO_RENDER_IN_PUBLIC_RUNNER_ALLOWED=false
PUBLIC_RUNNER_ARTIFACTS_DEFAULT=none
```
