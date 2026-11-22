"""Synthetic-only regression for Qwen 1.7B on existing owner Issue path.

The Qwen candidate is TEXT ONLY, never a proven SRT alignment.
Tests perform no model downloads, real media reads or hosted inference.
"""
from pathlib import Path
import base64
import unittest
from tools.issue_dispatch import validate_command, validate_event

ROOT = Path(__file__).resolve().parents[1]
KEY = "rsa-n:" + base64.urlsafe_b64encode(
    bytes([0x80]) + bytes([0x11]) * 254 + bytes([0x01])
).decode("ascii").rstrip("=")


class CandidateQwen17Tests(unittest.TestCase):
    def test_qwen17_owner_signed_dispatch_is_authorized(self):
        body = '/srt-run {"transport":"signed-url","output_public_key":"' + KEY + '","model":"qwen3-asr-1.7b"}'
        result = validate_command(body)
        self.assertEqual(result["model"], "qwen3-asr-1.7b")
        self.assertEqual(result["transport"], "signed-url")
        self.assertEqual(result["alignment"], "off")
        self.assertEqual(result["encrypted_drive_file_id"], "")

    def test_untrusted_actor_fails_for_qwen_candidate(self):
        evt = {
            "action": "created",
            "repository": {"full_name": "rayray12zx3-sys/subtitle-srt-toolkit"},
            "issue": {"number": 1, "state": "open", "user": {"login": "rayray12zx3-sys"}},
            "comment": {"body": '/srt-run {"transport":"signed-url","output_public_key":"'
                        + KEY + '","model":"qwen3-asr-1.7b"}',
                        "user": {"login": "untrusted"}},
        }
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_event(evt)

    def test_unapproved_model_fails_closed(self):
        body = '/srt-run {"transport":"signed-url","output_public_key":"' + KEY + '","model":"arbitrary-remote-api"}'
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_command(body)

    def test_pinned_c_cpu_and_encrypted_output(self):
        text = (ROOT / "tools/qwen_private_benchmark.py").read_text("utf-8")
        self.assertIn('PINNED_QWEN_C_COMMIT = "924694251d9e0f18e5d86bbd06aa3ab5f870002d"', text)
        self.assertIn('publish_runner_public_key(', text)
        self.assertIn('find_packet_urls(', text)
        self.assertIn('fetch_signed_ciphertext(', text)
        self.assertIn('pack(payload, recipient, OUTPUT_AAD)', text)
        self.assertIn('QWEN_TEXT_ONLY_NO_SRT:', text)
        self.assertIn('reference_status": "ai-unverified"', text)
        self.assertNotIn('print(text)', text)

    def test_reusable_job_routes_text_not_srt(self):
        yml = (ROOT / ".github/workflows/cloud-handshake.yml").read_text("utf-8")
        self.assertIn("qwen3-asr-1.7b", yml)
        self.assertIn('if: ${{ inputs.model == \'qwen3-asr-1.7b\' }}', yml)
        self.assertIn('if: ${{ inputs.model != \'qwen3-asr-1.7b\' }}', yml)
        self.assertIn("python -m tools.qwen_private_benchmark --model-size large", yml)
        self.assertIn('libopenblas-dev', yml)
        self.assertNotIn("secrets: inherit", yml)

    def test_private_model_code_no_hardcoded_media_path(self):
        text=(ROOT / "tools/qwen_private_benchmark.py").read_text("utf-8")
        self.assertNotIn("0301_O", text)
        self.assertNotIn("Google AI Studio", text)


if __name__ == "__main__":
    unittest.main()
