"""Actual bundled PyAV codec regression; synthetic tones only."""
from fractions import Fraction
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from tools.runner_audio import AudioNormalizationError, normalize_opus_bytes


def synthetic_opus(rate, channels, seconds=2):
    import av
    import numpy as np

    sink = io.BytesIO()
    layout = "mono" if channels == 1 else "stereo"
    with av.open(sink, mode="w", format="ogg") as container:
        stream = container.add_stream("libopus", rate=rate)
        stream.layout = layout
        total = rate * seconds
        step = rate // 50
        for pos in range(0, total, step):
            count = min(step, total - pos)
            t = np.arange(pos, pos + count, dtype=np.float64) / rate
            tone = (np.sin(2 * np.pi * 440 * t) * 9000).astype(np.int16)
            data = np.tile(tone, (channels, 1))
            frame = av.AudioFrame.from_ndarray(data, format="s16p", layout=layout)
            frame.sample_rate = rate
            frame.time_base = Fraction(1, rate)
            frame.pts = pos
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return sink.getvalue()


class RunnerAudioTests(unittest.TestCase):
    def test_actual_opus_decode_without_external_executables(self):
        for rate, channels in ((16000, 1), (48000, 2)):
            with self.subTest(rate=rate, channels=channels), tempfile.TemporaryDirectory() as d:
                payload = synthetic_opus(rate, channels)
                target = Path(d) / "output.wav"
                with patch.dict(os.environ, {"PATH": ""}), patch(
                    "subprocess.run", side_effect=AssertionError("External command forbidden")
                ), patch("subprocess.Popen", side_effect=AssertionError("External command forbidden")):
                    samples = normalize_opus_bytes(payload, target)
                with wave.open(str(target), "rb") as wav:
                    self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()),
                                     (1, 2, 16000))
                    self.assertEqual(wav.getnframes(), samples)
                    self.assertLessEqual(abs(samples - 32000), 16)
                    self.assertTrue(any(wav.readframes(samples)))
                self.assertEqual(list(Path(d).iterdir()), [target])

    def test_malformed_packet_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "output.wav"
            for payload in (b"", b"not audio", b"OggS" + b"\x00" * 100):
                with self.assertRaises(AudioNormalizationError):
                    normalize_opus_bytes(payload, target)
                self.assertFalse(target.exists())
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "output.wav"
            target.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                normalize_opus_bytes(b"invalid", target)
            self.assertEqual(target.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
