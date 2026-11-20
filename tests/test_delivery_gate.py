import tempfile
import unittest
import wave
from pathlib import Path
from delivery_gate import validate_delivery, DeliveryBlocked

class DeliveryGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.audio = root / "audio.wav"
        self.srt = root / "output.srt"
        with wave.open(str(self.audio), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(8000)
            wav.writeframes(b"\0\0" * 8000)

    def put(self, content):
        self.srt.write_text(content, encoding="utf-8-sig")

    def test_valid_real_file(self):
        self.put("1\n00:00:00,050 --> 00:00:00,900\n你好\n")
        result = validate_delivery(self.audio, self.srt)
        self.assertEqual(result["cues"], 1)
        self.assertEqual(result["status"], "OUTPUT_VALIDATED_NOT_YET_DELIVERED")

    def test_missing_output_is_blocked(self):
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(self.audio, self.srt)

    def test_empty_output_is_blocked(self):
        self.put("")
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(self.audio, self.srt)

    def test_non_srt_or_missing_audio_is_blocked(self):
        self.put("1\n00:00:00,050 --> 00:00:00,900\n你好\n")
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(Path(self.tmp.name) / "missing.wav", self.srt)
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(self.audio, Path(self.tmp.name) / "bad.txt")

    def test_overlap_is_blocked(self):
        self.put("1\n00:00:00,100 --> 00:00:00,700\n你好\n\n"
                 "2\n00:00:00,600 --> 00:00:00,950\n世界\n")
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(self.audio, self.srt)

    def test_out_of_range_is_blocked(self):
        self.put("1\n00:00:00,100 --> 00:00:02,000\n你好\n")
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(self.audio, self.srt)

    def test_bad_numbering_is_blocked(self):
        self.put("2\n00:00:00,100 --> 00:00:00,800\n你好\n")
        with self.assertRaises(DeliveryBlocked):
            validate_delivery(self.audio, self.srt)

if __name__ == "__main__":
    unittest.main()
