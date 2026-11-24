"""Synthetic long WAV segmentation, global timecode merging and language options."""
import contextlib
import io
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from tools.chunking import split_pcm_wav, ChunkingError
from transcribe import main


class LongAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audio = self.root / "in.wav"
        self.model = self.root / "model"
        self.model.mkdir()
        (self.model / "model.bin").write_bytes(b"test-model")
        (self.model / "config.json").write_text("{}", encoding="utf-8")
        self.dest = self.root / "result.srt"
        # Exactly 13 seconds of mono PCM16 source with two quiet interstitial breaks.
        rate = 8000
        import array
        samples = array.array("h")
        for second in range(13):
            for idx in range(rate):
                samples.append(0 if second in (4, 9) else 1800)
        with wave.open(str(self.audio), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(rate)
            stream.writeframes(samples.tobytes())

    def test_sample_exact_nonoverlap_and_offsets(self):
        parts = split_pcm_wav(self.audio, self.root / "parts", 5)
        self.assertGreaterEqual(len(parts), 3)
        offsets = [round(offset, 4) for _,offset,_ in parts]
        self.assertEqual(offsets[0], 0)
        self.assertTrue(all(b>a for a,b in zip(offsets,offsets[1:])))
        original = b""
        with wave.open(str(self.audio),"rb") as w:
            original = w.readframes(w.getnframes())
        joined = b""
        total = 0.
        for path,offset,seconds in parts:
            with wave.open(str(path),"rb") as w:
                data=w.readframes(w.getnframes())
            joined += data
            self.assertAlmostEqual(offset,total,places=3)
            total += seconds
        self.assertEqual(joined,original)
        self.assertAlmostEqual(total,13.,places=3)

    def test_autolanguage_on_each_chunk_and_global_timecodes(self):
        calls = []
        class FakeWhisper:
            def __init__(self,*args,**kwargs): pass
            def transcribe(self,path,**kw):
                if len(list(Path(path).parent.glob("*.wav"))) != 1:
                    raise AssertionError("A production transcriber should stage one PCM chunk at a time")
                with wave.open(path,"rb") as f:
                    dur=f.getnframes()/f.getframerate()
                calls.append((path,dur,kw["language"]))
                word=SimpleNamespace(word="測試",start=0.1,end=min(0.8,dur))
                return [SimpleNamespace(words=[word])],SimpleNamespace(language="zh")
        fake = ModuleType("faster_whisper")
        fake.WhisperModel = FakeWhisper
        argv=["transcribe.py",str(self.audio),"--model-dir",str(self.model),
              "--output",str(self.dest),"--language","auto","--chunk-seconds","5"]
        with patch.dict(sys.modules,{"faster_whisper":fake}),patch.object(sys,"argv",argv),contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertGreaterEqual(len(calls),3)
        self.assertTrue(all(call[2] is None for call in calls))
        source=self.dest.read_text("utf-8-sig")
        starts=[]
        for line in source.splitlines():
            if " --> " in line:
                h,m,s=line.split(" --> ")[0].split(":")
                starts.append(int(h)*3600+int(m)*60+float(s.replace(",", ".")))
        self.assertEqual(len(starts),len(calls))
        self.assertTrue(all(b>a for a,b in zip(starts,starts[1:])))
        self.assertGreater(starts[-1],8.)
        self.assertLess(starts[-1],13.)

    def test_forced_chinese_language_still_available(self):
        calls=[]
        class FakeWhisper:
            def __init__(self,*args,**kwargs):pass
            def transcribe(self,path,**kw):
                calls.append(kw["language"])
                return [SimpleNamespace(words=[SimpleNamespace(word="ok",start=.1,end=.5)])],SimpleNamespace(language="zh")
        fake=ModuleType("faster_whisper");fake.WhisperModel=FakeWhisper
        argv=["transcribe.py",str(self.audio),"--model-dir",str(self.model),
              "--output",str(self.dest),"--language","zh","--chunk-seconds","5"]
        with patch.dict(sys.modules,{"faster_whisper":fake}),patch.object(sys,"argv",argv),contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertTrue(calls and all(lang=="zh" for lang in calls))

    def test_invalid_chunk_settings_fail_closed(self):
        with self.assertRaises(ChunkingError):
            split_pcm_wav(self.audio,self.root / "bad",1)
        with self.assertRaises(ChunkingError):
            split_pcm_wav(self.audio,self.root / "bad2",3601)

    def test_invalid_audio_pcm_format_refused(self):
        stereo = self.root / "stereo.wav"
        with wave.open(str(stereo),"wb") as wav:
            wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(8000)
            wav.writeframes(b"\x00\x00"*8000*2)
        with self.assertRaises(ChunkingError):
            split_pcm_wav(stereo,self.root / "stereo_parts",5)

if __name__=="__main__":
    unittest.main()
