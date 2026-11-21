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
from model_catalog import MODEL_REPOS, get_model_repo
from tools.secure_exchange import emit_encrypted_srt
from tools.batch_bundle import is_batch_blob,decode_bundle,encode_bundle


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
                blob=resp.read(64 * 1024 * 1024 + 1)
                if len(blob) > 64 * 1024 * 1024:
                    raise ValueError('Encrypted audio exceeds maximum allowed size')
            if blob.startswith(MAGIC):
                return blob
        except Exception:
            pass
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--drive-id',required=True)
    p.add_argument('--output-pub',required=True)
    p.add_argument('--model',choices=list(MODEL_REPOS),default='large-v3-turbo')
    p.add_argument('--language',choices=['auto','zh','en'],default='auto')
    p.add_argument('--chunk-seconds',type=int,default=600)
    p.add_argument('--max-wait',type=int,default=1800)
    a=p.parse_args()
    if a.output_pub.startswith('rsa-n:'):
        encoded = a.output_pub[6:]
        modulus_bytes = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
        if len(modulus_bytes) != 256:
            raise ValueError("Invalid compact RSA modulus length")
        output_pub = rsa.RSAPublicNumbers(65537, int.from_bytes(modulus_bytes, 'big')).public_key()
    else:
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
        model=root/'model'
        batch=is_batch_blob(source_bytes)
        inputs=decode_bundle(source_bytes,"input") if batch else [("clip_0001",source_bytes)]
        del source_bytes
        model_start = time.monotonic()
        if a.model == 'breeze-asr-25':
            snapshot_download(repo_id=get_model_repo(a.model),
                              revision='70660216b01a6f6b7b8c5690767a4763df61755f',
                              allow_patterns=['int8/*'],local_dir=str(model))
            actual_model_dir = model / 'int8'
        else:
            snapshot_download(repo_id=get_model_repo(a.model),local_dir=str(model))
            actual_model_dir = model
        download_sec = time.monotonic() - model_start
        asr_start = time.monotonic()
        env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'}
        from delivery_gate import validate_delivery
        completed=[]
        cues=0
        for clip_name,opus_bytes in inputs:
            folder=root/clip_name
            folder.mkdir()
            source=folder/'source.opus';audio=folder/'audio.wav';srt=folder/'output.srt'
            source.write_bytes(opus_bytes)
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
                            '-i',str(source),'-ar','16000','-ac','1','-c:a','pcm_s16le',
                            str(audio)],check=True,stdout=subprocess.DEVNULL)
            source.unlink(missing_ok=True)
            subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'transcribe.py'),
                            str(audio),'--model-dir',str(actual_model_dir),'--device','cpu',
                            '--compute-type','int8','--language',a.language,
                            '--chunk-seconds',str(a.chunk_seconds),
                            '--traditional','--output',str(srt)],
                           env=env,check=True,stdout=subprocess.DEVNULL)
            report=validate_delivery(audio,srt)
            if report['status']!='OUTPUT_VALIDATED_NOT_YET_DELIVERED':
                raise SystemExit('BLOCKED: Invalid SRT in batch')
            cues+=report['cues']
            completed.append((clip_name,srt.read_bytes()))
        asr_sec = time.monotonic() - asr_start
        payload=encode_bundle("output",completed) if batch else completed[0][1]
        emit_encrypted_srt(pack(payload,output_pub,OUTPUT_AAD))
        print('SRT_VALIDATED_CUES='+str(cues),flush=True)
        print('SRT_BATCH_ITEMS='+str(len(completed)),flush=True)
        print('SRT_MODEL_ID='+a.model,flush=True)
        print(f'SRT_MODEL_DOWNLOAD_SECONDS={download_sec:.2f}',flush=True)
        print(f'SRT_ASR_GENERATION_SECONDS={asr_sec:.2f}',flush=True)
        print('OUTPUT_VALIDATED_NOT_YET_DELIVERED',flush=True)

if __name__ == '__main__':
    main()