from __future__ import annotations

from .common import *
from .contracts import validate_profile


def public_diagnostic(profile: Mapping[str, Any]) -> dict[str, Any]:
    validate_profile(profile)
    return {
        "diagnostic_class": "PUBLIC_RUNNER_CONTRACT_TEST_ONLY",
        "profile_id": profile["profile_id"],
        "private_media_execution": False,
        "public_artifacts_created": False,
        "private_content_public_exposure": False,
        "actions_steps_none_classification": "PRE_STEP_INFRASTRUCTURE_FAILURE_NOT_CODE_VERDICT",
        "no_fake_green": True,
    }


def assert_repo_hygiene(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            raise PreviewError("MEDIA_BINARY_IN_REPOSITORY", path.name)
        if path.is_file() and path.suffix.lower() in {".py", ".json", ".md", ".yml", ".yaml", ".sh"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"/home/[A-Za-z0-9._-]+/", text):
                raise PreviewError("RAW_PRIVATE_PATH_IN_REPOSITORY", path.name)
            if re.search(r"(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})", text):
                raise PreviewError("SECRET_IN_REPOSITORY", path.name)
