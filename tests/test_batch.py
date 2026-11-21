"""Synthetic-only batch envelope and private delivery tests."""
import base64,contextlib,io,json,tempfile,unittest,wave,zipfile
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from tools.batch_bundle import (MAGIC,MAX_CLIPS,clip_id,encode_bundle,decode_bundle)
from tools.secure_exchange import (OUTPUT_AAD,emit_encrypted_srt,finish_batch_srt,
                                   make_return_key,parse_public_key,make_envelope)

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_bundle_roundtrip_exact_order(self):
        x=[(clip_id(1),b"synthetic_opus1"),(clip_id(2),b"synthetic_opus2")]
        b=encode_bundle("input",x)
        self.assertEqual(decode_bundle(b,"input"),x)
        with self.assertRaises(ValueError): decode_bundle(b,"output")
        self.assertNotIn(b"original-secret-filename",b)

    def test_reject_unexpected_zip_paths(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,"w") as z:
            z.writestr("manifest.json",json.dumps({"v":1,"kind":"input","ids":["clip_0001"]}))
            z.writestr("clips/clip_0001.opus",b"synthetic")
            z.writestr("../bad",b"x")
        with self.assertRaises(ValueError):decode_bundle(MAGIC+b.getvalue(),"input")

    def test_bad_counts_or_missing_files(self):
        for x in ([],[(clip_id(1),b"x")]*2):
            with self.assertRaises(ValueError):encode_bundle("input",x)
        with self.assertRaises(ValueError):decode_bundle(MAGIC+b"broken","input")

    def _wav(self,n):
        p=self.root/f"{n}.wav"
        with wave.open(str(p),"wb") as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000)
            w.writeframes(b"\x00\x00"*16000)
        return p

    def _cipherlog(self,keyfile,items):
        private=serialization.load_pem_private_key(keyfile.read_bytes(),password=None)
        pub=private.public_key()
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            emit_encrypted_srt(make_envelope(encode_bundle("output",items),pub,OUTPUT_AAD))
        return out.getvalue()

    def test_multi_srt_atomic_delivery(self):
        audios=[self._wav(1),self._wav(2)]
        key=self.root/"return.pem";make_return_key(key)
        cue=b"1\n00:00:00,100 --> 00:00:00,800\nsynthetic\n"
        log=self._cipherlog(key,[(clip_id(1),cue),(clip_id(2),cue)])
        target=self.root/"verified"
        reports=finish_batch_srt(log,key,audios,target)
        self.assertEqual([r["cues"] for r in reports],[1,1])
        self.assertEqual(len(list(target.glob("*.srt"))),2)
        with self.assertRaises(ValueError):finish_batch_srt(log,key,audios,target)

    def test_invalid_second_srt_blocks_all(self):
        audios=[self._wav(1),self._wav(2)]
        key=self.root/"return.pem";make_return_key(key)
        x=[(clip_id(1),b"1\n00:00:00,100 --> 00:00:00,800\nok\n"),
           (clip_id(2),b"1\n00:00:00,100 --> 00:00:12,000\ninvalid\n")]
        target=self.root/"never"
        with self.assertRaises(ValueError):
            finish_batch_srt(self._cipherlog(key,x),key,audios,target)
        self.assertFalse(target.exists())

if __name__=="__main__":unittest.main()
