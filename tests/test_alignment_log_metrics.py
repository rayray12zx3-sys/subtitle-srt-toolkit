"""The real Runner printed attempted and succeeded on ONE line, so parse both."""
import unittest
from tools.cloud_handshake import parse_alignment_metrics

class AlignmentLogMetricsTests(unittest.TestCase):
    def test_real_cli_compact_status_line_parses_all_fields(self):
        cli=("AUTO_QA_CUES=24 AUTO_QA_FAST=0\n"
             "OUTPUT_VALIDATED_NOT_YET_DELIVERED: /tmp/private/audio.srt; 24 cues\n"
             "ALIGNER_ATTEMPTED_CHUNKS=5 ALIGNER_SUCCEEDED_CHUNKS=3\n"
             "ALIGNER_FALLBACK_CHUNKS=2\n"
             "ALIGNER_BOUNDARY_COMPARISON_SAMPLES=110\n"
             "ALIGNER_BOUNDARY_MEDIAN_ABS_SHIFT_SECONDS=0.130\n"
             "ALIGNER_BOUNDARY_P95_ABS_SHIFT_SECONDS=0.400\n"
             "ALIGNER_BOUNDARY_MAX_ABS_SHIFT_SECONDS=0.620\n")
        out=parse_alignment_metrics(cli)
        self.assertEqual(out["attempted"],5)
        self.assertEqual(out["succeeded"],3)
        self.assertEqual(out["fallback"],2)
        self.assertEqual(out["samples"],110)
        self.assertEqual(out["median"],0.13)
        self.assertEqual(out["p95"],0.4)
        self.assertEqual(out["max"],0.62)
        self.assertNotIn("private", str(out))

    def test_all_fallback_without_timing_is_explicit(self):
        out=parse_alignment_metrics(
            "ALIGNER_ATTEMPTED_CHUNKS=5 ALIGNER_SUCCEEDED_CHUNKS=0\n"
            "ALIGNER_FALLBACK_CHUNKS=5\n"
            "ALIGNER_BOUNDARY_COMPARISON_SAMPLES=0\n")
        self.assertEqual(out["samples"],0)
        self.assertNotIn("median",out)

    def test_missing_or_inconsistent_counts_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError,"missing"):
            parse_alignment_metrics("ALIGNER_ATTEMPTED_CHUNKS=2")
        with self.assertRaisesRegex(RuntimeError,"Inconsistent"):
            parse_alignment_metrics(
                "ALIGNER_ATTEMPTED_CHUNKS=4 ALIGNER_SUCCEEDED_CHUNKS=1\n"
                "ALIGNER_FALLBACK_CHUNKS=1 ALIGNER_BOUNDARY_COMPARISON_SAMPLES=10")

    def test_duplicate_keys_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"Duplicate"):
            parse_alignment_metrics(
                "ALIGNER_ATTEMPTED_CHUNKS=3 ALIGNER_SUCCEEDED_CHUNKS=2\n"
                "ALIGNER_FALLBACK_CHUNKS=1 ALIGNER_BOUNDARY_COMPARISON_SAMPLES=3\n"
                "ALIGNER_ATTEMPTED_CHUNKS=999")

if __name__=="__main__":unittest.main()
