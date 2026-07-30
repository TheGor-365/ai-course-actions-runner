from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.gold_v2.authority import validate_manifest
from scripts.gold_v2.common import RunnerError
from helpers import base_manifest, seal


class AuthorityTests(unittest.TestCase):
    def fixture(self, mode="validate-only"):
        tmp = tempfile.TemporaryDirectory()
        manifest, _ = base_manifest(Path(tmp.name), mode)
        self.addCleanup(tmp.cleanup)
        return manifest

    def rejected(self, code, manifest, mode):
        with self.assertRaisesRegex(RunnerError, code):
            validate_manifest(manifest, mode)

    def test_validate_only_authorized(self):
        self.assertEqual("validate-only", validate_manifest(self.fixture(), "validate-only")["mode"])

    def test_pre_render_manifest_authorized_static(self):
        self.assertEqual("pre-render-evidence", validate_manifest(self.fixture("pre-render-evidence"), "pre-render-evidence")["mode"])

    def test_render_manifest_authorized_static(self):
        self.assertEqual("render", validate_manifest(self.fixture("render"), "render")["mode"])

    def test_unauthorized_compile(self):
        m = self.fixture("compile"); m["execution_authorizations"]["compile"] = False; seal(m)
        self.rejected("MODE_NOT_AUTHORIZED", m, "compile")

    def test_unauthorized_evidence(self):
        m = self.fixture("pre-render-evidence"); m["execution_authorizations"]["still_evidence"] = False; seal(m)
        self.rejected("MODE_NOT_AUTHORIZED", m, "pre-render-evidence")

    def test_unauthorized_render(self):
        m = self.fixture("render"); m["execution_authorizations"]["render"] = False; seal(m)
        self.rejected("MODE_NOT_AUTHORIZED", m, "render")

    def test_wrong_source_head(self):
        m = self.fixture(); m["source_head"] = "z" * 40; seal(m)
        self.rejected("SOURCE_HEAD_INVALID", m, "validate-only")

    def test_provisional_head_rejected(self):
        m = self.fixture(); m["runner_head"] = "main"; seal(m)
        self.rejected("RUNNER_HEAD_INVALID", m, "validate-only")

    def test_missing_runtime_head(self):
        m = self.fixture("pre-render-evidence"); del m["runtime_head"]; seal(m)
        self.rejected("RUNTIME_HEAD_INVALID", m, "pre-render-evidence")

    def test_wrong_compiler_artifact_digest_shape(self):
        m = self.fixture("compile"); m["compiler_artifact_sha256"] = "0" * 63; seal(m)
        self.rejected("COMPILER_ARTIFACT_SHA256_INVALID", m, "compile")

    def test_preview_mislabeled_production(self):
        m = self.fixture(); m["artifact_class"] = "PREVIEW"; m["acceptance_state"] = "ACCEPTED"; seal(m)
        self.rejected("PREVIEW_ACCEPTANCE_STATE_INVALID", m, "validate-only")

    def test_branch_name_does_not_authorize(self):
        m = self.fixture("compile"); m["control_branch"] = "production-authorized-render"; m["execution_authorizations"]["compile"] = False; seal(m)
        self.rejected("MODE_NOT_AUTHORIZED", m, "compile")

    def test_automatic_aesthetic_pass_rejected(self):
        m = self.fixture(); m["human_review_gates"][0]["status"] = "PASS"; seal(m)
        self.rejected("AUTOMATIC_AESTHETIC_PASS_FORBIDDEN", m, "validate-only")

    def test_payload_tamper_rejected(self):
        m = self.fixture(); m["artifact_class"] = "PREVIEW"
        self.rejected("AUTHORIZATION_PAYLOAD_SHA256_MISMATCH", m, "validate-only")

    def test_secret_command_reference_rejected(self):
        m = self.fixture(); m["commands"]["source_validate"]["argv"] = ["echo", "GITHUB_TOKEN"]; seal(m)
        self.rejected("COMMAND_SECRET_REFERENCE_FORBIDDEN", m, "validate-only")


if __name__ == "__main__":
    unittest.main()
