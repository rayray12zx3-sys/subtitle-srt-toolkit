"""Auto readability, natural speech-gap extensions and private aggregate QA."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace

from tools.smart_segmentation import reading_units,segment_words
from tools.subtitle_timing import cue_windows
from tools.subtitle_quality import analyze_srt
from transcribe import write_srt


def tok(word,start,end): return SimpleNamespace(word=word,start=start,end=end)


class AutoReadingTests(unittest.TestCase):
    def test_reading_load_english_not_per_letter(self):
        self.assertGreater(reading_units("今天我們"),reading_units("OK"))
        self.assertLess(reading_units("language"),len("language"))
        self.assertGreater(reading_units("中文 English"),reading_units("中文"))

    def test_pause_extension_only_within_silence(self):
        one=[tok("你好",0.15,0.55)]
        two=[tok("英文",1.10,1.65)]
        windows=cue_windows([one,two],audio_end=2.0)
        self.assertEqual(windows[0][0],.15)
        self.assertAlmostEqual(windows[0][1],.83,places=6)
        self.assertLess(windows[0][1],two[0].start)
        self.assertEqual(windows[1][0],1.10)
        self.assertEqual(windows[1][1],1.65)

    def test_back_to_back_speech_does_not_overstretch(self):
        groups=[[tok("A",0,.5)],[tok("B",.5,1)]]
        self.assertEqual(cue_windows(groups)[0],(0.,.5))

    def test_overlapping_input_fails_closed(self):
        with self.assertRaises(ValueError):
            cue_windows([[tok("一",0,.9)],[tok("二",.8,1.4)]])

    def test_fast_speech_report_is_aggregate(self):
        with tempfile.TemporaryDirectory() as d:
            srt=Path(d)/"test.srt"
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:00,350\n這是一個非常快速的中文句子\n\n"
                "2\n00:00:00,400 --> 00:00:01,400\nHello everyone\n",
                encoding="utf-8"
            )
            report=analyze_srt(srt,12,2,8.)
            self.assertEqual(report["cues"],2)
            self.assertGreaterEqual(report["reading_too_fast"],1)
            self.assertGreaterEqual(report["too_brief"],1)
            self.assertNotIn("transcript",report)
            self.assertTrue(report["layout_ok"])

    def test_no_hidden_word_rewriting(self):
        words=[tok("非常",0.,.35),tok("快速",.35,.68),tok("的",.7,.78),
               tok("測試。",.8,1.1),tok("接著",1.45,1.7),tok("看看",1.71,2.1)]
        groups=segment_words(words,max_duration=4,line_chars=12)
        self.assertEqual([id(w) for g in groups for w in g],[id(w) for w in words])
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/"out.srt"
            self.assertGreaterEqual(write_srt(groups,dest,True,
                    line_chars=12,max_lines=2,optimize_timing=True),1)
            self.assertTrue(dest.exists())


if __name__=="__main__":unittest.main()
