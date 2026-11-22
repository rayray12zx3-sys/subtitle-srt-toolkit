"""Semantic SRT grouping and line layout without raw/private recordings."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.smart_segmentation import segment_words, break_lines, visual_width, _protected_boundaries, _text, repair_split_contraction_lines
from transcribe import write_srt


def make(items, dur=.28, gap=.04):
    output=[]
    current=0.
    for text in items:
        output.append(SimpleNamespace(word=text,start=current,end=current+dur))
        current+=dur+gap
    return output


class SmartSemanticTests(unittest.TestCase):
    def test_strong_chinese_sentence_end(self):
        words=make(["今天", "我們", "要學", "英文。", "接下來", "看看", "例句。"])
        segments=segment_words(words,max_chars=22,max_duration=4,line_chars=12)
        self.assertEqual(len(segments),2)
        self.assertEqual("".join(w.word for w in segments[0]),"今天我們要學英文。")
        self.assertEqual("".join(w.word for w in segments[1]),"接下來看看例句。")

    def test_clause_connectors_are_not_stranded(self):
        words=make(["因為", "今天", "下雨，", "所以", "我們", "留在", "家裡。"])
        parts=segment_words(words,max_chars=12,max_duration=4,line_chars=10)
        texts=["".join(w.word for w in group) for group in parts]
        self.assertFalse(any(text.endswith("因為") or text.endswith("所以") for text in texts[:-1]))
        self.assertEqual("".join(texts),"因為今天下雨，所以我們留在家裡。")

    def test_english_words_not_broken(self):
        words=make(["Hello ", "everyone. ", "Today ", "we ", "will ", "learn ", "English."])
        parts=segment_words(words,max_chars=22,max_duration=4,line_chars=12)
        flattened=[w for group in parts for w in group]
        self.assertEqual(flattened,words)
        self.assertTrue(any("everyone." in "".join(w.word for w in group) for group in parts))
        self.assertTrue(all(len(group)>0 for group in parts))

    def test_two_line_layout_respects_tokens(self):
        words=make(["今天", "我們", "一起", "學習", "自然", "英文", "口說", "表達"])
        line=break_lines(words,line_chars=8,max_lines=2)
        self.assertEqual("".join(line),"今天我們一起學習自然英文口說表達")
        self.assertLessEqual(len(line),2)
        self.assertTrue(all(visual_width(part)<=16 for part in line))

    def test_srt_auto_multiline_keeps_word_time(self):
        words=make(["今天", "我們", "一起", "學習", "自然", "英文", "口說", "表達"])
        with tempfile.TemporaryDirectory() as tmp:
            dst=Path(tmp)/"smart.srt"
            count=write_srt([words],dst,True,line_chars=8,max_lines=2)
            content=dst.read_text("utf-8-sig")
            self.assertEqual(count,1)
            self.assertIn("\n今天我們一起學習\n自然英文口說表達\n",content)
            self.assertIn("00:00:00,000 -->",content)

    def test_pause_triggers_natural_break(self):
        items=make(["我們", "先來", "聽聽", "例句", "稍後", "再", "練習"])
        for idx in range(4,len(items)):
            items[idx].start+=1.0;items[idx].end+=1.0
        seg=segment_words(items,max_chars=22,max_duration=4,line_chars=12)
        self.assertTrue(any(g[-1].word=="例句" for g in seg[:-1]))

    def test_oversized_single_token_remains_whole(self):
        words=[SimpleNamespace(word="這是一個非常非常非常長的中文字串",start=0,end=1.1)]
        seg=segment_words(words,max_chars=6,max_duration=4,line_chars=6)
        self.assertEqual(seg,[[words[0]]])
        self.assertEqual(break_lines(words,line_chars=6),[words[0].word])

    def test_no_punctuation_fallback_and_no_empty(self):
        words=make(["我們","可以","進行","不同","語言","的","字幕","處理"]*3)
        groups=segment_words(words,max_chars=8,max_duration=2.4,line_chars=8)
        self.assertTrue(all(len(g)>0 and g[0].start<g[-1].end for g in groups))
        self.assertEqual([x for group in groups for x in group],words)

    def test_lexical_guard_prevents_split_in_traditional_compounds(self):
        first = make(["你可以用其他的形", "容詞", "來形容", "心", "情不好"])
        guards = _protected_boundaries(first)
        self.assertIn(1, guards)  # 形|容詞
        self.assertIn(4, guards)  # 心|情
        self.assertEqual(_text(first), "你可以用其他的形容詞來形容心情不好")

    def test_english_punctuation_glue_gets_display_space(self):
        seq = make(["The worst part is, ", "she's right.Well", " maybe "])
        self.assertIn("right. Well", _text(seq))
        lines = break_lines(seq, line_chars=80, max_lines=2)
        self.assertEqual(lines, ["The worst part is, she's right. Well maybe"])

    def test_whisper_english_subword_fragments_are_never_broken(self):
        fragments = make(["L", "ala", " was", " here"])
        self.assertEqual(_text(fragments), "Lala was here")
        self.assertEqual(_text(make(["W", "ish", " me", " luck"])), "Wish me luck")
        self.assertEqual(_text(make(["right.", "Well", " maybe"])),
                         "right. Well maybe")

    def test_lexical_guard_applies_inside_two_line_layout(self):
        words = make(["今天", "我們", "學", "形", "容詞", "有趣", "也很", "實用"])
        result = break_lines(words, line_chars=7, max_lines=2)
        self.assertEqual(len(result), 2)
        self.assertFalse(result[0].endswith("形"))
        self.assertFalse(result[0].endswith("心"))
        self.assertIn("形容詞", "".join(result))

    def test_safe_display_only_reflow_of_existing_srt_contraction(self):
        original = ["The worst part is, she", "'s right. Well"]
        fixed = repair_split_contraction_lines(original, line_chars=12)
        self.assertEqual(fixed, ["The worst part is,", "she's right. Well"])
        self.assertEqual("".join(original), "".join(fixed))
        self.assertTrue(all(visual_width(line) <= 26 for line in fixed))
        self.assertEqual(repair_split_contraction_lines(["Hello", " everyone"], 12),
                         ["Hello", " everyone"])

    def test_english_contractions_do_not_split_across_lines(self):
        words=make(["The worst part is, ", "she", "'s", " right.", " Well"])
        protected=_protected_boundaries(words)
        self.assertIn(2, protected)  # she|'s is ONE English word
        lines=break_lines(words, line_chars=12, max_lines=2)
        self.assertNotIn("she\n's", "\n".join(lines))
        self.assertIn("she's", "".join(lines))

    def test_other_english_clitics_protected(self):
        seq=make(["I ", "do", "n't", " know", " where ", "we", "'re"])
        self.assertIn(2, _protected_boundaries(seq))
        self.assertIn(6, _protected_boundaries(seq))

    def test_invalid_limits_rejected(self):
        with self.assertRaises(ValueError):
            segment_words(make(["test"]),line_chars=0)
        with self.assertRaises(ValueError):
            segment_words(make(["test"]),max_lines=3)


if __name__=="__main__":
    unittest.main()
