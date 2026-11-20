#!/usr/bin/env python3
"""Runner-side ephemeral RSA/AES-GCM encrypted audio exchange; no shared secret."""
import argparse
import base64
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from huggingface_hub import snapshot_download

MAGIC = b'SRT2'
INPUT_AAD = b'subtitle-srt-toolkit/input2'
OUTPUT_AAD = b'subtitle-srt-toolkit/output2'

def pack(data, pub, aad):
    key = os.urandom(32)
    encrypted_key = pub.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    nonce = os.urandom(12)
    return MAGIC+len(encrypted_key).to_bytes(2,'big')+encrypted_key+nonce+AESGCM(key).encrypt(nonce,data,aad)

def unpack(blob, priv, aad):
    if not blob.startswith(MAGIC) or len(blob) < 60:
        raise ValueError('Not encrypted input')
    size = int.from_bytes(blob[4:6],'big')
    if size not in (256,384,512):
        raise ValueError('Invalid envelope length')
    key = priv.decrypt(blob[6:6+size],padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    nonce = blob[6+size:18+size]
    return AESGCM(key).decrypt(nonce,blob[18+size:],aad)

def fetch_public_drive_blob(file_id):
    if not re.fullmatch('[A-Za-z0-9_-]{15,100}',file_id):
        raise ValueError('Invalid Drive file ID')
    for url in (f'https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t',
                f'https://drive.google.com/uc?export=download&id={file_id}'):
        try:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as resp:
                host = urlsplit(resp.geturl()).hostname or ''
                if not (host.endswith('.googleusercontent.com') or host.endswith('.google.com')):
                    continue
                blob=resp.read(1_000_000)
            if blob.startswith(MAGIC):
                return blob
        except Exception:
            pass
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--drive-id',required=True)
    p.add_argument('--output-pub',required=True)
    p.add_argument('--model',choices=['tiny','base','small','medium','large-v3'],default='small')
    p.add_argument('--max-wait',type=int,default=1800)
    a=p.parse_args()
    output_pub=serialization.load_der_public_key(base64.b64decode(a.output_pub,validate=True))
    in_priv=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pub=in_priv.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    print('SRT_INPUT_PUBLIC_KEY_B64='+base64.b64encode(pub).decode('ascii'),flush=True)
    print('WAITING_FOR_ENCRYPTED_INPUT',flush=True)
    source_bytes=None
    began=time.monotonic()
    while time.monotonic()-began < a.max_wait:
        blob=fetch_public_drive_blob(a.drive_id)
        if blob:
            try:
                source_bytes=unpack(blob,in_priv,INPUT_AAD)
            except (ValueError,Exception):
                pass
        if source_bytes:
            break
        time.sleep(10)
    if not source_bytes:
        raise SystemExit('BLOCKED: Timed out waiting for compatible encrypted media')
    with tempfile.TemporaryDirectory(prefix='whisper_private_') as tmp:
        root=Path(tmp)
        source=root/'source.opus'; audio=root/'audio.wav'; srt=root/'output.srt'; model=root/'model'
        source.write_bytes(source_bytes)
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-ar','16000','-ac','1',str(audio)],check=True)
        snapshot_download(repo_id=f'Systran/faster-whisper-{a.model}',local_dir=str(model))
        env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'}
        subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'transcribe.py'),str(audio),'--model-dir',str(model),'--device','cpu','--compute-type','int8','--language','zh','--traditional','--output',str(srt)],env=env,check=True,stdout=subprocess.DEVNULL)
        from delivery_gate import validate_delivery
        report=validate_delivery(audio,srt)
        if report['status'] != 'OUTPUT_VALIDATED_NOT_YET_DELIVERED':
            raise SystemExit('BLOCKED: Invalid SRT')
        print('SRT_OUTPUT_CIPHER_B64='+base64.b64encode(pack(srt.read_bytes(),output_pub,OUTPUT_AAD)).decode('ascii'),flush=True)
        print('SRT_VALIDATED_CUES='+str(report['cues']),flush=True)
        print('OUTPUT_VALIDATED_NOT_YET_DELIVERED',flush=True)

if __name__ == '__main__':
    main()