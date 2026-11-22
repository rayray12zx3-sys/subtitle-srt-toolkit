"""Synthetic faithful Qwen alignment mapping tests; no model download."""
import unittest
from types import SimpleNamespace
from tools.qwen_forced_alignment import norm,map_aligned_words,alignment_boundary_shifts

class ForcedAlignmentMapTests(unittest.TestCase):
    def test_chinese_char_timestamps_without_changing_punctuation(self):
        words=[SimpleNamespace(word="今天",start=0,end=.7),
               SimpleNamespace(word="我們。",start=.7,end=1.4)]
        aligned=[
            {"text":"今","start_time":.1,"end_time":.28},
            {"text":"天","start_time":.28,"end_time":.55},
            {"text":"我","start_time":.7,"end_time":.97},
            {"text":"們","start_time":.97,"end_time":1.2},
        ]
        result=map_aligned_words(words,aligned,1.5)
        self.assertEqual("".join(x.word for x in result),"今天我們。")
        self.assertEqual([x.word for x in result],["今","天","我","們。"])
        self.assertEqual([x.start for x in result],[.1,.28,.7,.97])

    def test_english_word_alignment_preserves_spaces(self):
        words=[SimpleNamespace(word="Hello ",start=0,end=.4),
               SimpleNamespace(word="world!",start=.4,end=1.1)]
        items=[{"text":"Hello","start_time":.1,"end_time":.38},
               {"text":"world","start_time":.43,"end_time":.99}]
        out=map_aligned_words(words,items,2.)
        self.assertEqual("".join(x.word for x in out),"Hello world!")
        self.assertEqual([x.word for x in out],["Hello ","world!"])

    def test_mismatched_asr_text_fails_closed(self):
        words=[SimpleNamespace(word="你好",start=0,end=.5)]
        with self.assertRaises(ValueError):
            map_aligned_words(words,[{"text":"再見","start_time":0.1,"end_time":.5}],1.)

    def test_wrong_and_overlapping_alignment_rejected(self):
        words=[SimpleNamespace(word="A B",start=0,end=1)]
        items=[{"text":"A","start_time":.6,"end_time":.8},
               {"text":"B","start_time":.0,"end_time":.2}]
        with self.assertRaises(ValueError):
            map_aligned_words(words,items,1.2)

    def test_boundary_shift_uses_same_original_text_and_character_mapping(self):
        words=[SimpleNamespace(word="今天",start=0,end=.7),
               SimpleNamespace(word="我們。",start=.7,end=1.4)]
        items=[
            {"text":"今","start_time":.1,"end_time":.28},
            {"text":"天","start_time":.28,"end_time":.55},
            {"text":"我","start_time":.7,"end_time":.97},
            {"text":"們","start_time":.97,"end_time":1.2},
        ]
        aligned=map_aligned_words(words,items,1.5)
        shifts=alignment_boundary_shifts(words,aligned)
        self.assertEqual(len(shifts),4)
        self.assertAlmostEqual(shifts[0],.1)
        self.assertAlmostEqual(shifts[1],.15)
        self.assertAlmostEqual(shifts[2],0)
        self.assertAlmostEqual(shifts[3],.2)
        self.assertEqual("".join(w.word for w in words),
                         "".join(w.word for w in aligned))

    def test_boundary_shift_rejects_changed_text(self):
        original=[SimpleNamespace(word="hello",start=.1,end=.6)]
        altered=[SimpleNamespace(word="hullo",start=.1,end=.6)]
        with self.assertRaisesRegex(ValueError,"altered text"):
            alignment_boundary_shifts(original,altered)

    def test_normalization_excludes_punctuation(self):
        self.assertEqual(norm("Hello, 世界！"),norm("hello世界"))
if __name__=="__main__":unittest.main()
