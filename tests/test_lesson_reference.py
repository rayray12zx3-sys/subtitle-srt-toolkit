"""Synthetic lesson cues, exercising conservative changes to authenticated subtitles."""
import codecs
import unittest

from tools.lesson_reference import apply_lesson_reference


class LessonReferenceTests(unittest.TestCase):
    def test_reference_preserves_crlf_timestamps_and_unrelated_words(self):
        source = codecs.BOM_UTF8 + (
            "1\r\n00:00:00,200 --> 00:00:01,600\r\nuse github and api\r\n\r\n"
            "2\r\n00:00:02,000 --> 00:00:03,700\r\nstudy mercury\r\n教室練習 blah\r\n"
        ).encode()
        updated, stats = apply_lesson_reference(source, "use GitHub and API\n"
                                                "study Mercury\n教室測試\nextra reference text")
        self.assertEqual(updated, source.replace(b"github", b"GitHub").replace(b"api", b"API")
                         .replace(b"mercury", b"Mercury"))
        self.assertEqual(stats, {"matched_english_words": 6, "matched_han_pairs": 1, "case_changes": 3})

    def test_conflicting_case_and_unanchored_title_case_remain_untouched(self):
        source = b"1\n00:00:00,200 --> 00:00:01,600\napi then mercury\n"
        updated, stats = apply_lesson_reference(source, "API and api. Mercury in orbit.")
        self.assertEqual(updated, source)
        self.assertEqual(stats["case_changes"], 0)
