import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from model_catalog import get_model_repo
from transcribe import (
    clean_text, enable_offline_mode, group_words, require_local_model,
    srt_time, write_srt,
)


class SRTTests(unittest.TestCase):
    def test_turbo_model_registry(self):
        self.assertEqual(get_model_repo("large-v3-turbo"),
                         "deepdml/faster-whisper-large-v3-turbo-ct2")
        with self.assertRaises(ValueError):
            get_model_repo("external-api")

    def test_timestamp(self):
        self.assertEqual(srt_time(61.234), "00:01:01,234")

    def test_clean(self):
        self.assertEqual(clean_text("你好，"), "你好")
        self.assertEqual(clean_text("A.I.,"), "A.I")

    def test_word_split(self):
        words = [
            SimpleNamespace(word="你好", start=0, end=0.5),
            SimpleNamespace(word="世界", start=1, end=1.5),
        ]
        self.assertEqual(len(group_words(words, 22, 4, .4)), 2)

    def test_write(self):
        words = [[SimpleNamespace(word="字幕。", start=0, end=1)]]
        with TemporaryDirectory() as folder:
            dest = Path(folder) / "out.srt"
            self.assertEqual(write_srt(words, dest, True), 1)
            self.assertIn(
                "00:00:00,000 --> 00:00:01,000",
                dest.read_text("utf-8-sig"),
            )

    def test_local_model_must_exist(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)
            with self.assertRaises(ValueError):
                require_local_model(path)
            (path / "config.json").write_text("{}", encoding="utf-8")
            (path / "model.bin").write_bytes(b"test")
            self.assertEqual(require_local_model(path), path.resolve())

    def test_offline_mode_forces_no_hub_access(self):
        with patch.dict(os.environ, {"HF_HUB_OFFLINE": "0"}, clear=False):
            enable_offline_mode()
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
            self.assertEqual(os.environ["HF_HUB_DISABLE_TELEMETRY"], "1")

    def test_traditional_converter_is_local_callable(self):
        words = [[SimpleNamespace(word="汉字。", start=0, end=1)]]
        with TemporaryDirectory() as folder:
            dest = Path(folder) / "converted.srt"
            write_srt(words, dest, True, converter=lambda s: s.replace("汉", "漢"))
            self.assertIn("漢字", dest.read_text("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
