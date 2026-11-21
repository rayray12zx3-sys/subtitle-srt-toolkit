"""No real media or API calls: synthetic public-key transport and handoff tests."""
import base64
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
import wave

from tools.secure_exchange import (
    INPUT_AAD, OUTPUT_AAD, LOG_CHUNK_CHARS,
    compact_public_key, emit_encrypted_srt, finish_srt,
    make_envelope, make_return_key, open_envelope,
    output_envelope_from_logs, parse_public_key, runner_public_from_logs
)
from cryptography.hazmat.primitives.asymmetric import rsa


class SecureExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_compact_key_and_original_der_interoperate(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        compact = compact_public_key(key)
        self.assertEqual(len(compact), 348)
        pub = parse_public_key(compact)
        blob = make_envelope(b"speech-only-synthetic", pub, INPUT_AAD)
        self.assertEqual(open_envelope(blob, key, INPUT_AAD), b"speech-only-synthetic")
        with self.assertRaises(Exception):
            open_envelope(blob, key, OUTPUT_AAD)

    def test_key_saved_without_overwriting(self):
        path = self.root / "caller.pem"
        pub = make_return_key(path)
        self.assertEqual(parse_public_key(pub).key_size, 2048)
        self.assertTrue(path.exists())
        with self.assertRaises(FileExistsError):
            make_return_key(path)
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_parse_runner_public_key_in_timestamped_logs(self):
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        der = priv.public_key().public_bytes(
            encoding=__import__("cryptography").hazmat.primitives.serialization.Encoding.DER,
            format=__import__("cryptography").hazmat.primitives.serialization.PublicFormat.SubjectPublicKeyInfo
        )
        log = "2026-11-21T00:00:00Z SRT_INPUT_PUBLIC_KEY_B64=" + base64.b64encode(der).decode()
        self.assertEqual(runner_public_from_logs(log).public_numbers(), priv.public_key().public_numbers())

    def test_large_encrypted_srt_chunks_roundtrip(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        original = b"pretend-encrypted-private-srt:" + os.urandom(25000)
        cipher = make_envelope(original, key.public_key(), OUTPUT_AAD)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            emit_encrypted_srt(cipher)
        log = output.getvalue()
        self.assertIn("SRT_OUTPUT_CIPHER_PARTS=", log)
        self.assertIn("SRT_OUTPUT_CIPHER_READY=1", log)
        self.assertEqual(open_envelope(output_envelope_from_logs(log), key, OUTPUT_AAD), original)
        truncated = "\n".join(x for x in log.splitlines() if "PART_0001=" not in x)
        with self.assertRaises(ValueError):
            output_envelope_from_logs(truncated)

    def test_short_legacy_output(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cipher = make_envelope(b"test", key.public_key(), OUTPUT_AAD)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            emit_encrypted_srt(cipher)
        self.assertIn("SRT_OUTPUT_CIPHER_B64=", output.getvalue())
        self.assertEqual(open_envelope(output_envelope_from_logs(output.getvalue()),
                                       key, OUTPUT_AAD), b"test")

    def test_finish_validates_and_preserves_old_srt_on_failure(self):
        private_path = self.root / "caller.pem"
        pub = parse_public_key(make_return_key(private_path))
        audio = self.root / "audio.wav"
        with wave.open(str(audio), "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2)
            wav.setframerate(8000); wav.writeframes(b"\x00\x00" * 8000)
        out = self.root / "result.srt"
        out.write_text("original content", encoding="utf-8")
        bad_blob = make_envelope(b"not an SRT", pub, OUTPUT_AAD)
        with self.assertRaises(Exception):
            finish_srt("SRT_OUTPUT_CIPHER_B64=" + base64.b64encode(bad_blob).decode(),
                       private_path, audio, out)
        self.assertEqual(out.read_text("utf-8"), "original content")
        srt = b"1\n00:00:00,100 --> 00:00:00,800\nhello\n"
        cipher = make_envelope(srt, pub, OUTPUT_AAD)
        report = finish_srt("SRT_OUTPUT_CIPHER_B64=" + base64.b64encode(cipher).decode(),
                            private_path, audio, out)
        self.assertEqual(report["cues"], 1)
        self.assertEqual(out.read_text("utf-8-sig").strip().splitlines()[-1], "hello")


if __name__ == "__main__":
    unittest.main()
