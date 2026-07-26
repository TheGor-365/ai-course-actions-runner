import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("public_media", ROOT / "scripts/gold_s01_public_media_v1.py")
PUBLIC_MEDIA = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PUBLIC_MEDIA)


class PublicMediaTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / "config/gold_s01_public_media_profile_v1.json").read_text(encoding="utf-8"))

    def test_active_profile_allows_public_execution(self):
        profile = PUBLIC_MEDIA.validate_profile(self.profile)
        self.assertTrue(profile["public_workflow_execution_allowed"])
        self.assertTrue(profile["public_artifact_upload_allowed"])
        self.assertEqual(profile["execution_layer"], "public_github_hosted_runner")
        self.assertFalse(profile["arbitrary_commands_allowed"])
        self.assertFalse(profile["dynamic_script_path_allowed"])

    def test_safe_inputs_reject_dynamic_fields(self):
        args = Namespace(
            private_repo="TheGor-365/ai-course-production-system",
            private_branch="repair/gold-s01-visual-runtime-v2",
            private_sha="a" * 40,
            request_path="03_modules/M1/L01/request.json",
            request_blob="b" * 40,
            request_sha256="c" * 64,
            render_mode="pilot_60s",
            request_id="gold-s01",
        )
        PUBLIC_MEDIA.validate_fixed_inputs(args)
        args.private_branch = "../bad"
        with self.assertRaises(PUBLIC_MEDIA.PublicMediaError):
            PUBLIC_MEDIA.validate_fixed_inputs(args)

    def test_forbidden_execution_keys_fail_closed(self):
        for key in ("shell", "command", "script_path", "arguments", "provider_payload"):
            with self.assertRaises(PUBLIC_MEDIA.PublicMediaError):
                PUBLIC_MEDIA.scan_forbidden_keys({"safe": {"nested": {key: "x"}}})

    def test_artifact_allowlist_blocks_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "receipt.json").write_text("{}\n", encoding="utf-8")
            PUBLIC_MEDIA.enforce_artifact_allowlist(root)
            (root / "private-repo.zip").write_bytes(b"zip")
            with self.assertRaises(PUBLIC_MEDIA.PublicMediaError):
                PUBLIC_MEDIA.enforce_artifact_allowlist(root)


if __name__ == "__main__":
    unittest.main()
