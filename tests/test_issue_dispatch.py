"""Security and input-validation regression tests for owner GitHub comment dispatch."""
import base64
import json
from pathlib import Path
import unittest

from tools.issue_dispatch import validate_command, validate_event

ROOT = Path(__file__).resolve().parents[1]
# Synthetic, deliberately NOT a real private key or user public key.
FAKE_RSA_N = "rsa-n:" + base64.urlsafe_b64encode(
    bytes([0x80]) + bytes([0x11]) * 254 + bytes([0x01])
).decode("ascii").rstrip("=")
DRIVE_ID = "SyntheticCiphertextId20261122"


def event(body, commenter="rayray12zx3-sys", issue_num=1):
    return {
        "action": "created",
        "repository": {"full_name": "rayray12zx3-sys/subtitle-srt-toolkit"},
        "issue": {
            "number": issue_num, "state": "open",
            "user": {"login": "rayray12zx3-sys"},
        },
        "comment": {"user": {"login": commenter}, "body": body},
    }


def run_request(**overrides):
    obj = {
        "encrypted_drive_file_id": DRIVE_ID,
        "output_public_key": FAKE_RSA_N,
    }
    obj.update(overrides)
    return "/srt-run " + json.dumps(obj, ensure_ascii=False)


class IssueCommentDispatchTests(unittest.TestCase):
    def test_owner_smoke_has_no_model_inputs(self):
        self.assertEqual(validate_event(event("/srt-check")), {"smoke": "true"})

    def test_owner_valid_real_request_is_normalized(self):
        result = validate_event(event(run_request()))
        self.assertEqual(result["smoke"], "false")
        self.assertEqual(result["chunk_seconds"], "600")
        self.assertEqual(result["model"], "large-v3-turbo")
        self.assertEqual(result["alignment"], "off")
        self.assertEqual(result["encrypted_drive_file_id"], DRIVE_ID)

    def test_all_supported_options(self):
        result = validate_command(run_request(model="small", language="zh",
                                             alignment="qwen", chunk_seconds=0))
        self.assertEqual(result["model"], "small")
        self.assertEqual(result["language"], "zh")
        self.assertEqual(result["alignment"], "qwen")
        self.assertEqual(result["chunk_seconds"], "0")

    def test_probe_command_requires_expiring_signed_cipher_link(self):
        from unittest.mock import patch
        with patch("tools.signed_cipher_transport.validate_signed_url",
                   return_value="https://approved.example.test/temporary"):
            result = validate_event(event("/srt-probe https://example.test"))
        self.assertEqual(result["smoke"], "probe")
        self.assertEqual(result["probe_url"], "https://approved.example.test/temporary")
        with self.assertRaises(ValueError):
            validate_event(event("/srt-probe https://example.com/plaintext.wav"))

    def test_signed_url_transport_needs_no_drive_id(self):
        command = "/srt-run " + json.dumps({
            "output_public_key": FAKE_RSA_N, "transport": "signed-url",
            "model": "large-v3-turbo"})
        result = validate_event(event(command))
        self.assertEqual(result["transport"], "signed-url")
        self.assertEqual(result["encrypted_drive_file_id"], "")
        self.assertEqual(result["model"], "large-v3-turbo")

    def test_signed_url_transport_rejects_drive_id(self):
        with self.assertRaisesRegex(ValueError, "Signed URL transport"):
            validate_command(run_request(transport="signed-url"))

    def test_unknown_ciphertext_transport_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Invalid ciphertext transport"):
            validate_command(run_request(transport="anything"))

    def test_no_public_url_or_plaintext_in_run_command(self):
        with self.assertRaisesRegex(ValueError, "Missing or unknown"):
            validate_command(run_request(signed_url="https://example.invalid/media"))
        with self.assertRaisesRegex(ValueError, "Invalid encrypted"):
            validate_command(run_request(encrypted_drive_file_id="http://example.org/a.wav"))

    def test_untrusted_commenter_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(event("/srt-check", commenter="anonymous"))

    def test_wrong_issue_number_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(event("/srt-check", issue_num=2))

    def test_pull_request_comment_rejected(self):
        e = event("/srt-check")
        e["issue"]["pull_request"] = {"url": "https://example.test"}
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(e)

    def test_cross_repo_rejected(self):
        e = event("/srt-check")
        e["repository"]["full_name"] = "someone/other"
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(e)

    def test_issue_not_owned_rejected(self):
        e = event("/srt-check")
        e["issue"]["user"]["login"] = "anonymous"
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(e)

    def test_edited_comment_event_rejected(self):
        e = event("/srt-check")
        e["action"] = "edited"
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(e)

    def test_closed_issue_rejected(self):
        e = event("/srt-check")
        e["issue"]["state"] = "closed"
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(e)

    def test_plaintext_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid encrypted"):
            validate_command(run_request(encrypted_drive_file_id="https://example.com/recording.wav"))

    def test_malformed_modulus_rejected(self):
        with self.assertRaisesRegex(ValueError, "RSA"):
            validate_command(run_request(output_public_key="not-rsa-key"))

    def test_false_boolean_alignment_rejected(self):
        with self.assertRaises(ValueError):
            validate_command(run_request(alignment=False))

    def test_extra_fields_not_allowed(self):
        with self.assertRaisesRegex(ValueError, "Missing or unknown"):
            validate_command(run_request(audio_url="https://example.test/private.wav"))

    def test_newline_injection_rejected(self):
        with self.assertRaisesRegex(ValueError, "multiline"):
            validate_command(run_request() + "\nextra=value")

    def test_wrong_types_rejected(self):
        for v in (True, 60.5, "600", -1, 3601):
            with self.subTest(v=v), self.assertRaises((ValueError, TypeError)):
                validate_command(run_request(chunk_seconds=v))

    def test_duplicate_field_rejected(self):
        command = '/srt-run {"encrypted_drive_file_id":"abc","encrypted_drive_file_id":"other","output_public_key":"key"}'
        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            validate_command(command)

    def test_no_public_media_fields_in_dispatch_workflow(self):
        workflow = (ROOT / ".github/workflows/issue-comment-dispatch.yml").read_text("utf-8")
        self.assertIn("issue_comment:", workflow)
        self.assertIn("github.event.issue.number == 1", workflow)
        self.assertIn("github.event.comment.user.login == 'rayray12zx3-sys'", workflow)
        self.assertIn("github.event.issue.pull_request == null", workflow)
        self.assertIn("tools.issue_dispatch", workflow)
        self.assertIn("uses: ./.github/workflows/cloud-handshake.yml", workflow)
        self.assertIn("SRT_COMMENT_DISPATCH_SMOKE_PASS", workflow)
        self.assertNotIn("secrets: inherit", workflow)

    def test_existing_workflow_is_still_manually_dispatchable(self):
        workflow = (ROOT / ".github/workflows/cloud-handshake.yml").read_text("utf-8")
        self.assertIn("workflow_call:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("default: 'off'", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)


if __name__ == "__main__":
    unittest.main()
