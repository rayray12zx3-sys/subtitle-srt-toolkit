"""Pipeline integration: optional alignment success and automatic fallback without Torch."""
import contextlib
import io
from pathlib import Path
from types import ModuleType,SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

from transcribe import main
from delivery_gate import validate_delivery


class AlignmentFallbackTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.audio=self.root/"synthetic.wav"
        with wave.open(str(self.audio),"wb") as f:
            f.setnchannels(1);f.setframerate(8000);f.setsampwidth(2)
            f.writeframes(b"\x00\x00" * 8000 * 3)
        self.model=self.root/"whisper"
        self.model.mkdir()
        (self.model/"config.json").write_text("{}",encoding="utf-8")
        (self.model/"model.bin").write_bytes(b"fake weights")
        self.destination=self.root/"out.srt"
        self.aligner=self.root/"fake-qwen"
        self.aligner.mkdir()

    def _run(self,aligner):
        class FakeWhisper:
            def __init__(self,*a,**kw): pass
            def transcribe(self,audio,**kw):
                word=SimpleNamespace(word="今天",start=.2,end=.65)
                return [SimpleNamespace(words=[word])],SimpleNamespace(language="zh")
        fake_whisper=ModuleType("faster_whisper")
        fake_whisper.WhisperModel=FakeWhisper
        args=["transcribe.py",str(self.audio),"--model-dir",str(self.model),
              "--chunk-seconds","2","--language","zh","--aligner-dir",str(self.aligner),
              "--output",str(self.destination)]
        output=io.StringIO()
        with patch.dict(sys.modules,{"faster_whisper":fake_whisper}),\
             patch("tools.qwen_forced_alignment.QwenCPUAligner",return_value=aligner),\
             patch.object(sys,"argv",args),contextlib.redirect_stdout(output):
            main()
        result=validate_delivery(self.audio,self.destination)
        return output.getvalue(),result

    def test_failed_alignment_falls_back_to_original_words(self):
        class Broken:
            def align(self,*args,**kw):
                raise ValueError("Unreliable timestamps")
        stdout,report=self._run(Broken())
        self.assertIn("ALIGNER_SUCCEEDED_CHUNKS=0",stdout)
        self.assertIn("ALIGNER_FALLBACK_CHUNKS=2",stdout)
        self.assertGreaterEqual(report["cues"],1)
        self.assertIn("今天",self.destination.read_text("utf-8-sig"))

    def test_successful_alignment_can_supply_chinese_character_times(self):
        class Good:
            def align(self,part,words,language,duration):
                assert language=="zh"
                return [SimpleNamespace(word="今",start=.1,end=.29),
                        SimpleNamespace(word="天",start=.29,end=.54)]
        stdout,report=self._run(Good())
        self.assertIn("ALIGNER_SUCCEEDED_CHUNKS=2",stdout)
        self.assertEqual(report["cues"],2)
        self.assertIn("00:00:00,100",self.destination.read_text("utf-8-sig"))

if __name__=="__main__":
    unittest.main()
