import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from transcribe import clean_text, srt_time, group_words, write_srt

class SRTTests(unittest.TestCase):
    def test_timestamp(self):
        self.assertEqual(srt_time(61.234), '00:01:01,234')
    def test_clean(self):
        self.assertEqual(clean_text('你好，'), '你好')
        self.assertEqual(clean_text('A.I.,'), 'A.I')
    def test_word_split(self):
        ws=[SimpleNamespace(word='你好',start=0,end=0.5),SimpleNamespace(word='世界',start=1,end=1.5)]
        self.assertEqual(len(group_words(ws,22,4,.4)),2)
    def test_write(self):
        ws=[[SimpleNamespace(word='字幕。',start=0,end=1)]]
        with TemporaryDirectory() as d:
            p=Path(d)/'out.srt'
            self.assertEqual(write_srt(ws,p,True),1)
            self.assertIn('00:00:00,000 --> 00:00:01,000',p.read_text('utf-8-sig'))

if __name__=='__main__': unittest.main()
