import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tools.text_review import compare, read_srt_text, tokens

class ReviewTests(unittest.TestCase):
    def test_mixed_language_tokens(self):
        self.assertEqual(tokens("你 Look upset today!"), ["你", "look", "upset", "today"])
    def test_disagreements_not_auto_corrected(self):
        result=compare("你好 ABC", "你好 ABD")
        self.assertEqual(result["status"], "REVIEW_REQUIRED_NOT_VERIFIED")
        self.assertGreater(result["candidate_disagreements"], 0)
        self.assertEqual(result["items"][0]["srt_tokens"], ["abc"])
    def test_read_private_srt(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"sample.srt"
            path.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好\n",encoding="utf-8")
            self.assertEqual(read_srt_text(path), "你好")
    def test_traditional_normalization_reduces_false_disagreements(self):
        raw = compare("剛剛來", "刚刚来")
        converted = compare("剛剛來", "刚刚来",
                            normalizer=lambda t: t.replace("刚","剛").replace("来","來"))
        self.assertGreater(raw["candidate_disagreements"], 0)
        self.assertEqual(converted["candidate_disagreements"], 0)

    def test_missing_srt_rejected(self):
        with TemporaryDirectory() as d:
            path=Path(d)/"empty.srt"
            path.write_text("",encoding="utf-8")
            with self.assertRaises(ValueError):
                read_srt_text(path)
