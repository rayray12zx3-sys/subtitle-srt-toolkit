"""Synthetic-only regression tests for Premiere's direct edited-SRT audit.

Never include any user's original recording, transcript or media hash here.
"""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from tools.premiere_reference import (
    PENDING, check_edited_srt, attest_edited_srt,
)
from tools.gold_reference_review import _atomic_private_write, sha256
from tools.asr_quality_benchmark import validate_human_audit

SOURCE = (
    "1\n00:00:00,100 --> 00:00:01,000\nHello there\n\n"
    "2\n00:00:01,200 --> 00:00:02,200\n今天很好\n"
)
EDITED = (
    "1\n00:00:00,100 --> 00:00:00,480\nHello\n\n"
    "2\n00:00:00,480 --> 00:00:01,000\nthere\n\n"
    "3\n00:00:01,200 --> 00:00:02,200\n今天很好\n"
)


class DirectPremiereAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audio = self.root / "synthetic.wav"
        self.audio.write_bytes(b"synthetic-voice-test-only")
        self.source = self.root / "synthetic-original.srt"
        self.source.write_text(SOURCE, encoding="utf-8")
        self.edited = self.root / "synthetic-edited.srt"
        self.edited.write_text(EDITED, encoding="utf-8")
        timing = patch("tools.premiere_reference.audio_duration_ms",
                       return_value=3000)
        timing.start()
        self.addCleanup(timing.stop)

    def test_check_accepts_resegmentation_without_claiming_gold(self):
        status = check_edited_srt(self.audio, self.source, self.edited)
        self.assertEqual(status["status"], PENDING)
        self.assertEqual(status["source_cues"], 2)
        self.assertEqual(status["edited_cues"], 3)
        self.assertEqual(status["last_end_ms"], 2200)
        self.assertEqual(status["transcript_human_listening"], "NOT_ATTESTED")
        self.assertEqual(status["cue_time_human_listening"], "NOT_ATTESTED")
        self.assertFalse(any(p.name.endswith(".json")
                             for p in self.root.iterdir()))

    def test_check_allows_text_correction_not_just_display_reflow(self):
        self.edited.write_text(EDITED.replace("there", "their"),
                               encoding="utf-8")
        status = check_edited_srt(self.audio, self.source, self.edited)
        self.assertEqual(status["edited_cues"], 3)
        self.assertEqual(status["status"], PENDING)

    def test_missing_attestation_is_never_silently_promoted(self):
        with self.assertRaisesRegex(ValueError, "attestation"):
            attest_edited_srt(
                self.audio, self.source, self.edited,
                reviewer_id="Editor", completed_utc="2026-11-23T02:00:00Z",
                confirm_full_listening=False)

    def test_attested_edited_srt_matches_existing_benchmark_audit_gate(self):
        audit = attest_edited_srt(
            self.audio, self.source, self.edited,
            reviewer_id="Private editor", completed_utc="2026-11-23T02:00:00Z",
            confirm_full_listening=True)
        self.assertEqual(audit["status"],
                         "HUMAN_SELF_ATTESTED_TEXT_AND_CUE_TIMING")
        self.assertEqual(audit["review_method"],
                         "PREMIERE_PRO_EXPORTED_SRT_FULL_LISTENING_ATTESTATION")
        self.assertEqual(audit["gold_sha256"], sha256(self.edited))
        self.assertEqual(audit["source_srt_sha256"], sha256(self.source))
        self.assertEqual(audit["cues"], 3)
        self.assertEqual(audit["text_reviewed"], 3)
        self.assertEqual(audit["time_reviewed"], 3)
        audit_out = self.root / "human_audit.json"
        _atomic_private_write(audit_out, json.dumps(audit),
                              [self.audio, self.source, self.edited])
        result = validate_human_audit(audit_out, self.edited)
        self.assertEqual(result["reviewed_cues"], 3)
        self.assertEqual(result["kind"],
                         "HUMAN_SELF_ATTESTED_TEXT_AND_CUE_TIMING")

    def test_reject_invalid_reviewer_and_completion_time(self):
        with self.assertRaisesRegex(ValueError, "Reviewer"):
            attest_edited_srt(
                self.audio, self.source, self.edited,
                reviewer_id="", completed_utc="2026-11-23T02:00:00Z",
                confirm_full_listening=True)
        with self.assertRaisesRegex(ValueError, "UTC timezone"):
            attest_edited_srt(
                self.audio, self.source, self.edited,
                reviewer_id="Editor", completed_utc="2026-11-23T02:00:00",
                confirm_full_listening=True)

    def test_reject_overlapping_or_out_of_audio_edited_cues(self):
        self.edited.write_text(EDITED.replace(
            "00:00:00,480 --> 00:00:01,000",
            "00:00:00,450 --> 00:00:01,000"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            check_edited_srt(self.audio, self.source, self.edited)
        self.edited.write_text(EDITED.replace(
            "00:00:01,200 --> 00:00:02,200",
            "00:00:01,200 --> 00:00:03,400"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "beyond"):
            check_edited_srt(self.audio, self.source, self.edited)

    def test_private_path_gate_and_input_identity(self):
        with self.assertRaisesRegex(ValueError, "separate"):
            check_edited_srt(self.audio, self.source, self.source)
        with patch("tools.gold_reference_review.REPO_ROOT", self.root):
            with self.assertRaisesRegex(ValueError, "public GitHub"):
                check_edited_srt(self.audio, self.source, self.edited)

    def test_audit_never_overwrites_edited_srt(self):
        audit = attest_edited_srt(
            self.audio, self.source, self.edited,
            reviewer_id="Editor", completed_utc="2026-11-23T02:00:00Z",
            confirm_full_listening=True)
        previous = self.edited.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            _atomic_private_write(self.edited, json.dumps(audit),
                                  [self.audio, self.source, self.edited])
        self.assertEqual(self.edited.read_bytes(), previous)


if __name__ == "__main__":
    unittest.main()
