"""Synthetic security/dispatch contract for pinned Fun-ASR-Nano CPU contender."""
import base64
from pathlib import Path
import unittest

from tools.issue_dispatch import validate_command

ROOT=Path(__file__).resolve().parents[1]
KEY="rsa-n:"+base64.urlsafe_b64encode(bytes([0x80])+bytes([0x11])*254+bytes([1])).decode().rstrip("=")

class FunASRPrivateCandidateTests(unittest.TestCase):
    def test_owner_model_is_whitelisted_without_changing_default(self):
        command='/srt-run {"transport":"signed-url","output_public_key":"'+KEY+'","model":"fun-asr-nano-2512"}'
        x=validate_command(command)
        self.assertEqual(x["model"],"fun-asr-nano-2512")
        self.assertEqual(x["alignment"],"off")
        self.assertEqual(x["language"],"auto")
        default=validate_command('/srt-run {"transport":"signed-url","output_public_key":"'+KEY+'"}')
        self.assertEqual(default["model"],"large-v3-turbo")

    def test_no_fake_word_alignment_or_forced_wrong_language(self):
        base='/srt-run {"transport":"signed-url","output_public_key":"'+KEY+'","model":"fun-asr-nano-2512",'
        with self.assertRaisesRegex(ValueError, "language=auto"):
            validate_command(base+'"alignment":"qwen"}')
        with self.assertRaisesRegex(ValueError, "language=auto"):
            validate_command(base+'"language":"en"}')

    def test_official_runtime_git_and_gguf_components_pinned(self):
        code=(ROOT/"tools/funasr_private_benchmark.py").read_text("utf-8")
        self.assertIn('FUNASR_PIN = "68aa96ddb96b6ec9b2f50923b9c55d223ef483af"', code)
        self.assertIn('MODEL_ID = "fun-asr-nano-2512"', code)
        for name in ("funasr-encoder-f16.gguf","qwen3-0.6b-q8_0.gguf","fsmn-vad.gguf"):
            self.assertIn(name,code)
        self.assertIn("download-funasr-model.sh",code)
        self.assertIn("publish_runner_public_key(",code)
        self.assertIn("fetch_signed_ciphertext(",code)
        self.assertIn("pack(payload, recipient, OUTPUT_AAD)",code)
        self.assertIn('timings',code)
        self.assertNotIn("print(transcript)",code)
        self.assertNotIn("0301_O",code)

    def test_wiring_avoids_running_whisper_or_qwen_on_same_input(self):
        yaml=(ROOT/".github/workflows/cloud-handshake.yml").read_text("utf-8")
        self.assertIn("inputs.model == 'fun-asr-nano-2512'",yaml)
        self.assertIn("python -m tools.funasr_private_benchmark",yaml)
        self.assertIn("inputs.model != 'qwen3-asr-1.7b' && inputs.model != 'fun-asr-nano-2512'",yaml)
        self.assertIn("inputs.model == 'qwen3-asr-1.7b'",yaml)
        self.assertNotIn("secrets: inherit",yaml)

    def test_caller_never_promotes_unverified_srt(self):
        code=(ROOT/"tools/funasr_private_benchmark.py").read_text("utf-8")
        self.assertIn("validate_delivery(wav, srt)",code)
        self.assertIn('mode = "none"',code)
        self.assertIn("FUNASR_TEXT_ENCRYPTED_NOT_AUTO_PROMOTED",code)


if __name__=="__main__":
    unittest.main()
