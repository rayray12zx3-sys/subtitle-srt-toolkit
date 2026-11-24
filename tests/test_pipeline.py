"""Synthetic pipeline tests; NO model weights, audio inference or network usage."""
import contextlib
import io
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from transcribe import main

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.audio = root / "audio.wav"
        self.model_dir = root / "model"
        self.model_dir.mkdir()
        (self.model_dir / "model.bin").write_bytes(b"dummy")
        (self.model_dir / "config.json").write_text("{}", encoding="utf-8")
        self.output = root / "final.srt"
        with wave.open(str(self.audio), "wb") as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(8000)
            recording.writeframes(b"\0\0" * 16000)

    def run_pipeline(self, word_list):
        fake_module = ModuleType("faster_whisper")
        fake_segments = [SimpleNamespace(words=word_list)]
        fake_model = SimpleNamespace(
            transcribe=lambda *args, **kwargs:
                (fake_segments, SimpleNamespace(language="zh"))
        )
        fake_module.WhisperModel = lambda *args, **kwargs: fake_model
        args = ["transcribe.py", str(self.audio), "--model-dir",
                str(self.model_dir), "--output", str(self.output)]
        with patch.dict(sys.modules, {"faster_whisper": fake_module}), \
                patch.object(sys, "argv", args), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            main()
            return output.getvalue()

    def test_valid_pipeline_generates_srt_but_not_delivery_claim(self):
        words = [SimpleNamespace(word="測試", start=0.1, end=0.8)]
        status = self.run_pipeline(words)
        self.assertTrue(self.output.exists())
        self.assertIn("測試", self.output.read_text("utf-8-sig"))
        self.assertIn("OUTPUT_VALIDATED_NOT_YET_DELIVERED", status)
        self.assertNotIn("COMPLETED", status)
        self.assertFalse(self.output.with_name("final.pending.srt").exists())

    def test_empty_recognition_blocks_and_never_publishes(self):
        with self.assertRaisesRegex(SystemExit, "BLOCKED"):
            self.run_pipeline([])
        self.assertFalse(self.output.exists())

    def test_quality_failure_preserves_existing_srt_and_cleans_staging(self):
        self.output.write_text("old result", encoding="utf-8")
        with patch("tools.subtitle_quality.analyze_srt", side_effect=ValueError("test failure")):
            with self.assertRaisesRegex(SystemExit, "BLOCKED"):
                self.run_pipeline([SimpleNamespace(word="test", start=.1, end=.8)])
        self.assertEqual(self.output.read_text("utf-8"), "old result")
        self.assertEqual(list(self.output.parent.glob(".srt-pending-*.srt")), [])

    def test_missing_model_blocks_even_if_old_srt_exists(self):
        self.output.write_text("old result", encoding="utf-8")
        (self.model_dir / "model.bin").unlink()
        with patch.object(sys, "argv", ["transcribe.py", str(self.audio),
                                           "--model-dir", str(self.model_dir),
                                           "--output", str(self.output)]):
            with self.assertRaisesRegex(SystemExit, "BLOCKED"):
                main()
        self.assertEqual(self.output.read_text("utf-8"), "old result")

if __name__ == "__main__":
    unittest.main()
