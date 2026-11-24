"""Synthetic-only tests for private bilingual ASR benchmarking."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.asr_quality_benchmark import (
    compare, edit_distance, measure, normalize, read_private_text,
    units, write_private_json, validate_human_audit,
)


class QualityBenchmarkTests(unittest.TestCase):
    def test_levenshtein_exact_insertion_deletion_substitution(self):
        self.assertEqual(edit_distance(["你", "好"], ["你", "好"]), 0)
        self.assertEqual(edit_distance(["a", "b"], ["a"]), 1)
        self.assertEqual(edit_distance(["a"], ["a", "b"]), 1)
        self.assertEqual(edit_distance(["a", "b"], ["a", "c"]), 1)
        self.assertEqual(edit_distance([], ["a", "b"]), 2)
        self.assertEqual(edit_distance(["a", "b"], []), 2)

    def test_reference_denominator_not_candidate_denominator(self):
        score = measure(["a", "b"], ["a", "b", "c"])
        self.assertEqual(score["reference_units"], 2)
        self.assertEqual(score["candidate_units"], 3)
        self.assertEqual(score["edit_distance"], 1)
        self.assertEqual(score["difference_rate"], 0.5)
        self.assertIsNone(measure([], ["extra"])["difference_rate"])

    def test_english_word_level_not_character_error(self):
        report = compare("We love learning.", "We love!", reference_status="human-verified")
        self.assertEqual(report["scores"]["english"]["reference_units"], 3)
        self.assertAlmostEqual(report["human_reference_rates"]["english_wer"], 1 / 3, places=6)
        self.assertIsNone(report["human_reference_rates"]["han_cer"])

    def test_chinese_character_level_not_space_word_split(self):
        report = compare("今天心情很好", "今天心情好", reference_status="human-verified")
        self.assertEqual(report["scores"]["han"]["edit_distance"], 1)
        self.assertEqual(report["human_reference_rates"]["han_cer"], round(1 / 6, 6))

    def test_mixed_language_and_punctuation(self):
        a = units("你好，AI's World！ 2026")
        b = units("你好 AI's world 2026")
        self.assertEqual(a["mixed"], b["mixed"])
        self.assertEqual(a["han"], ["你", "好"])
        self.assertEqual(a["english"], ["ai's", "world", "2026"])

    def test_apostrophe_case_width_normalization(self):
        self.assertEqual(normalize("ＷＥ’ＲＥ！"), "we're!")
        result = compare("She's right.", "she’s RIGHT！", reference_status="ai-unverified")
        self.assertEqual(result["scores"]["english"]["edit_distance"], 0)

    def test_explicit_converter_can_reduce_simplified_difference(self):
        plain = compare("今天說話", "今天说话", reference_status="ai-unverified")
        converted = compare(
            "今天說話", "今天说话", reference_status="ai-unverified",
            normalizer=lambda s: s.replace("说", "說").replace("话", "話"),
        )
        self.assertGreater(plain["scores"]["han"]["edit_distance"], 0)
        self.assertEqual(converted["scores"]["han"]["edit_distance"], 0)

    def test_unverified_ai_reference_never_emits_cer_wer_or_winner(self):
        result = compare("你 look good", "你 look great", reference_status="ai-unverified")
        self.assertEqual(result["status"], "AI_REFERENCE_DISAGREEMENT_ONLY")
        self.assertNotIn("human_reference_rates", result)
        self.assertEqual(result["scores"]["english"]["edit_distance"], 1)
        self.assertIn("not CER/WER", result["notice"])
        self.assertTrue(result["review_items"])

    def test_explicit_human_status_only_uses_human_labels(self):
        result = compare("我 like it", "我 like this", reference_status="human-verified")
        self.assertEqual(result["status"], "HUMAN_REFERENCE_COMPARISON")
        self.assertEqual(result["human_reference_rates"]["english_wer"], 0.5)
        self.assertEqual(result["human_reference_rates"]["han_cer"], 0.0)

    def test_diff_items_bounded_without_changing_full_distance(self):
        result = compare("one two three four", "a b c d", reference_status="ai-unverified",
                         max_disagreements=0)
        self.assertGreater(result["scores"]["mixed"]["edit_distance"], 0)
        self.assertEqual(result["review_items"], [])
        self.assertTrue(result["review_items_truncated"])

    def test_empty_invalid_and_oversized_reference_rejected(self):
        with self.assertRaises(ValueError):
            compare("!!!", "hello", reference_status="ai-unverified")
        with self.assertRaises(ValueError):
            compare("hello", "hi", reference_status="not-proven")
        with self.assertRaises(ValueError):
            compare("a " * 9000, "hello", reference_status="ai-unverified")

    def test_private_srt_and_text_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            srt = Path(temp) / "example.srt"
            srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n你好!\n", "utf-8")
            self.assertEqual(read_private_text(srt), "你好!")
            txt = Path(temp) / "example.txt"
            txt.write_text("今天", "utf-8")
            self.assertEqual(read_private_text(txt), "今天")
            with self.assertRaises(ValueError):
                read_private_text(Path(temp) / "example.mp3")

    def test_drive_srt_txt_is_parsed_as_srt_not_timestamps(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "from_drive.srt.txt"
            path.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n"
                "2\n00:00:01,000 --> 00:00:02,000\n你好\n", "utf-8"
            )
            self.assertEqual(read_private_text(path), "Hello world 你好")
            self.assertEqual(units(read_private_text(path))["english"], ["hello", "world"])
            self.assertEqual(units(read_private_text(path))["han"], ["你", "好"])

    def test_real_offline_opencc_if_installed(self):
        try:
            from opencc import OpenCC
        except ImportError:
            self.skipTest("Optional offline OpenCC package not in local environment")
        result = compare("今天說話", "今天说话", reference_status="ai-unverified",
                         normalizer=OpenCC("s2t").convert)
        self.assertEqual(result["scores"]["han"]["difference_rate"], 0.0)

    def test_human_audit_must_match_gold_sha_and_reviewed_cues(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder) / "gold.txt"
            src.write_text("Hello 世界\n", encoding="utf-8")
            audit = {
                "schema": "subtitle-srt-human-review-v1",
                "status": "HUMAN_SELF_ATTESTED_TEXT_ONLY",
                "cues": 2,
                "text_reviewed": 2,
                "time_reviewed": 0,
                "reviewer_id": "Review pseudonym",
                "review_completed_utc": "2026-11-22T12:00:00Z",
                "gold_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
            }
            path = Path(folder) / "audit.json"
            path.write_text(json.dumps(audit), encoding="utf-8")
            verified = validate_human_audit(path, src)
            self.assertEqual(verified["reviewed_cues"], 2)
            self.assertIn("Self-attested", verified["note"])
            audit["text_reviewed"] = 1
            path.write_text(json.dumps(audit), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not complete"):
                validate_human_audit(path, src)
            audit["text_reviewed"] = 2
            audit["gold_sha256"] = "0" * 64
            path.write_text(json.dumps(audit), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                validate_human_audit(path, src)

    def test_ai_reference_cannot_be_upgraded_without_human_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder) / "ai.srt"
            src.write_text("1\n00:00:00,100 --> 00:00:01,000\nHello\n",
                           encoding="utf-8")
            bogus = Path(folder) / "empty_audit.json"
            bogus.write_text(json.dumps({"status": "DRAFT_AWAITING_HUMAN_LISTENING"}))
            with self.assertRaisesRegex(ValueError, "provenance"):
                validate_human_audit(bogus, src)

    def test_private_report_is_atomic_and_restricted(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "sub" / "report.json"
            write_private_json(dest, {"candidate_results": {"A": 1}}, [])
            self.assertEqual(json.loads(dest.read_text("utf-8"))["candidate_results"], {"A": 1})
            if os.name == "posix":
                self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            write_private_json(dest, {"candidate_results": {"A": 2}}, [])
            self.assertEqual(json.loads(dest.read_text("utf-8"))["candidate_results"], {"A": 2})
            with self.assertRaises(ValueError):
                write_private_json(dest, {}, [dest])

    def test_refuse_public_repo_output_even_without_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch("tools.asr_quality_benchmark._REPO_ROOT", root):
                with self.assertRaisesRegex(ValueError, "public repository"):
                    write_private_json(root / "private" / "report.json", {}, [])


if __name__ == "__main__":
    unittest.main()
