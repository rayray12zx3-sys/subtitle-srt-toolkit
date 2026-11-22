"""Synthetic private human-listening reference workflow regressions.

No source recording, transcript or timestamps from a real user in this repo.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.gold_reference_review import (
    ATTESTATION, _atomic_private_write, cue_time_disagreement, finalize,
    ms_timestamp, parse_srt, prepare_manifest, review_status, sha256,
    timestamp_ms,
)

SRT = (
    "1\n00:00:00,100 --> 00:00:01,000\nHello there\n\n"
    "2\n00:00:01,200 --> 00:00:02,200\n今天很好\n"
)


class HumanReviewGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audio = self.root / "synthetic.wav"
        self.audio.write_bytes(b"private-synthetic-audio-fixture")
        self.srt = self.root / "synthetic.srt"
        self.srt.write_text(SRT, encoding="utf-8")
        patcher = patch("tools.gold_reference_review.audio_duration_ms", return_value=3000)
        patcher.start()
        self.addCleanup(patcher.stop)

    def draft(self):
        return prepare_manifest(self.audio, self.srt)

    def reviewed(self):
        m = self.draft()
        for c in m["cues"]:
            c["text_listened"] = True
            c["time_listened"] = True
        m["reviewer_id"] = "Private reviewer"
        m["review_completed_utc"] = "2026-11-22T14:00:00+00:00"
        m["listening_attestation"] = ATTESTATION
        return m

    def test_preparation_never_auto_marks_any_cue_verified(self):
        m = self.draft()
        self.assertEqual(m["status"], "DRAFT_AWAITING_HUMAN_LISTENING")
        self.assertEqual(len(m["cues"]), 2)
        self.assertEqual(m["audio"]["sha256"], sha256(self.audio))
        self.assertEqual(m["source_srt_sha256"], sha256(self.srt))
        self.assertFalse(any(c["text_listened"] or c["time_listened"] for c in m["cues"]))

    def test_no_unreviewed_draft_can_become_reference(self):
        with self.assertRaisesRegex(ValueError, "not fully listened"):
            finalize(self.draft(), self.audio, self.srt)
        state = review_status(self.draft(), self.audio, self.srt)
        self.assertFalse(state["text_ready"])
        self.assertFalse(state["timing_ready"])

    def test_text_only_requires_complete_listening_not_timing(self):
        m = self.reviewed()
        m["cues"][0]["time_listened"] = False
        gold, audit = finalize(m, self.audio, self.srt, text_only=True)
        self.assertEqual(gold, "Hello there 今天很好\n")
        self.assertEqual(audit["status"], "HUMAN_SELF_ATTESTED_TEXT_ONLY")
        self.assertEqual(audit["time_reviewed"], 1)
        self.assertEqual(audit["word_timestamp_accuracy"], "NOT_MEASURED")
        with self.assertRaisesRegex(ValueError, "timing"):
            finalize(m, self.audio, self.srt)

    def test_complete_self_attestation_creates_private_gold_srt(self):
        m = self.reviewed()
        m["cues"][0]["corrected_text"] = "Hello, there"
        m["cues"][0]["corrected_start_ms"] = 120
        result, audit = finalize(m, self.audio, self.srt)
        self.assertIn("00:00:00,120 --> 00:00:01,000", result)
        self.assertIn("Hello, there", result)
        self.assertEqual(audit["status"], "HUMAN_SELF_ATTESTED_TEXT_AND_CUE_TIMING")
        import hashlib
        self.assertEqual(audit["gold_sha256"],
                         hashlib.sha256(result.encode("utf-8")).hexdigest())
        self.assertIn("NOT independently", audit["claim"])
        self.assertEqual(len(parse_srt(result)), 2)

    def test_self_attestation_cannot_be_automatically_assumed(self):
        m = self.reviewed()
        m["listening_attestation"] = "I used another AI model"
        with self.assertRaisesRegex(ValueError, "attest"):
            finalize(m, self.audio, self.srt)
        m["listening_attestation"] = ATTESTATION
        m["reviewer_id"] = ""
        with self.assertRaisesRegex(ValueError, "reviewer"):
            finalize(m, self.audio, self.srt)
        m["reviewer_id"] = "Human"
        m["review_completed_utc"] = "2026-11-22T22:00:00"
        with self.assertRaisesRegex(ValueError, "UTC"):
            finalize(m, self.audio, self.srt)

    def test_source_audio_sha_mismatch_is_fatal(self):
        m = self.reviewed()
        self.audio.write_bytes(b"changed-recording")
        with self.assertRaisesRegex(ValueError, "source recording"):
            finalize(m, self.audio, self.srt)

    def test_source_srt_sha_mismatch_is_fatal(self):
        m = self.reviewed()
        self.srt.write_text(SRT.replace("Hello there", "Hello world"), "utf-8")
        with self.assertRaisesRegex(ValueError, "source SRT"):
            finalize(m, self.audio, self.srt)

    def test_review_draft_metadata_cannot_be_manipulated(self):
        m = self.reviewed()
        m["cues"][0]["draft_text"] = "Forged source"
        with self.assertRaisesRegex(ValueError, "source cue metadata"):
            finalize(m, self.audio, self.srt)

    def test_timing_overlap_and_overshoot_rejected(self):
        m = self.reviewed()
        m["cues"][1]["corrected_start_ms"] = 800
        with self.assertRaisesRegex(ValueError, "Invalid edited cue"):
            finalize(m, self.audio, self.srt)
        m["cues"][1]["corrected_start_ms"] = 2000
        m["cues"][1]["corrected_end_ms"] = 4000
        with self.assertRaisesRegex(ValueError, "Invalid edited cue"):
            finalize(m, self.audio, self.srt)

    def test_cue_index_and_timestamp_validation(self):
        self.assertEqual(timestamp_ms("00:01:02,003"), 62003)
        self.assertEqual(ms_timestamp(62003), "00:01:02,003")
        for invalid in ("00:60:00,000", "invalid", "00:00:60,000"):
            with self.assertRaises(ValueError):
                timestamp_ms(invalid)
        with self.assertRaises(ValueError):
            parse_srt(SRT.replace("\n2\n", "\n3\n"))
        with self.assertRaises(ValueError):
            parse_srt(SRT.replace("00:00:01,200 -->", "00:00:00,500 -->"))
        with self.assertRaises(ValueError):
            parse_srt(SRT, duration_ms=1000)

    def test_cue_shift_refuses_different_segmentation(self):
        shorter = "1\n00:00:00,100 --> 00:00:02,200\nHello there 今天很好\n"
        result = cue_time_disagreement(SRT, shorter)
        self.assertEqual(result["status"], "NOT_COMPARABLE_SEGMENTATION")
        other = SRT.replace("Hello there", "Goodbye")
        result2 = cue_time_disagreement(SRT, other)
        self.assertEqual(result2["status"], "NOT_COMPARABLE_TRANSCRIPT_OR_SEGMENTATION")

    def test_same_text_time_disagreement_measured_not_accuracy(self):
        different = SRT.replace("00:00:00,100", "00:00:00,150")
        data = cue_time_disagreement(SRT, different)
        self.assertEqual(data["samples"], 4)
        self.assertEqual(data["max_ms"], 50)
        self.assertEqual(data["status"], "CUE_BOUNDARY_DISAGREEMENT_ONLY")

    def test_private_write_refuses_repository_and_overwrite(self):
        with patch("tools.gold_reference_review.REPO_ROOT", self.root / "public_repo"):
            with self.assertRaisesRegex(ValueError, "public GitHub"):
                _atomic_private_write(self.root / "public_repo" / "gold.json", "{}")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            _atomic_private_write(self.audio, "bad", [self.audio])
        target = self.root / "gold.json"
        _atomic_private_write(target, json.dumps({"status": "DRAFT"}), [self.audio])
        self.assertEqual(json.loads(target.read_text())["status"], "DRAFT")


if __name__ == "__main__":
    unittest.main()
