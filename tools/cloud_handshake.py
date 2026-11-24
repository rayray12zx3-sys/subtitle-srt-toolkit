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
from tools.alignment_log_metrics import parse_alignment_metrics
from tools.runner_audio import normalize_opus_bytes


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
                blob=resp.read(64 * 1024 * 1024 + 513)
                if len(blob) > 64 * 1024 * 1024 + 512:
                    raise ValueError('Encrypted audio exceeds maximum allowed size')
            if blob.startswith(MAGIC):
                return blob
        except Exception:
            pass
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--drive-id', default='')
    p.add_argument('--transport', choices=['drive', 'signed-url'], default='drive')
    p.add_argument('--output-pub',required=True)
    p.add_argument('--model',choices=list(MODEL_REPOS),default='large-v3-turbo')
    p.add_argument('--alignment',choices=['off','qwen'],default='off')
    p.add_argument('--language',choices=['auto','zh','en'],default='auto')
    p.add_argument('--chunk-seconds',type=int,default=600)
    p.add_argument('--max-wait',type=int,default=1800)
    a=p.parse_args()
    if a.transport == 'drive' and not a.drive_id:
        p.error('--drive-id is required for drive transport')
    if a.transport == 'signed-url':
        if a.drive_id:
            p.error('--drive-id is not allowed with signed-url transport')
        if not (os.environ.get('GITHUB_TOKEN') and os.environ.get('GITHUB_RUN_ID')):
            p.error('GitHub Actions token and run ID are required')
        from tools.signed_cipher_transport import (find_packet_urls,
                                                      fetch_signed_ciphertext,
                                                      publish_runner_public_key)
        run_id = int(os.environ['GITHUB_RUN_ID'])
        issue_token = os.environ['GITHUB_TOKEN']
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
    encoded_public_key = base64.b64encode(pub).decode('ascii')
    print('SRT_INPUT_PUBLIC_KEY_B64='+encoded_public_key,flush=True)
    if a.transport == 'signed-url':
        publish_runner_public_key(run_id, encoded_public_key, issue_token)
        print('SRT_PUBLIC_KEY_PUBLISHED_TO_CONTROL_ISSUE', flush=True)
    print('WAITING_FOR_ENCRYPTED_INPUT',flush=True)
    source_bytes=None
    began=time.monotonic()
    while time.monotonic()-began < a.max_wait:
        if a.transport == 'signed-url':
            try:
                candidates = [fetch_signed_ciphertext(url)
                              for url in find_packet_urls(run_id, issue_token)]
            except Exception:
                # Transient GitHub/short-lived link errors must not expose tokens.
                candidates = []
        else:
            candidates = [fetch_public_drive_blob(a.drive_id)]
        for blob in candidates:
            if not blob:
                continue
            try:
                source_bytes=unpack(blob,in_priv,INPUT_AAD)
                break
            except Exception:
                # Authenticity failure: never use invalid packets.
                continue
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
        aligner_dir=None
        if a.alignment=='qwen':
            aligner_dir=root/'qwen3-aligner'
            snapshot_download(repo_id='Qwen/Qwen3-ForcedAligner-0.6B-hf',
                              local_dir=str(aligner_dir))
        download_sec = time.monotonic() - model_start
        asr_start = time.monotonic()
        env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'}
        from delivery_gate import validate_delivery
        from tools.subtitle_quality import analyze_srt
        completed=[]
        cues=0
        qa_fast=0
        qa_short=0
        qa_layout_warnings=0
        alignment_reports=[]
        for clip_name,opus_bytes in inputs:
            folder=root/clip_name
            folder.mkdir()
            audio=folder/'audio.wav';srt=folder/'output.srt'
            normalize_opus_bytes(opus_bytes, audio)
            print('SRT_AUDIO_NORMALIZER=pyav', flush=True)
            command=[sys.executable,str(Path(__file__).resolve().parents[1]/'transcribe.py'),
                     str(audio),'--model-dir',str(actual_model_dir),'--device','cpu',
                     '--compute-type','int8','--language',a.language,
                     '--chunk-seconds',str(a.chunk_seconds),
                     '--traditional','--output',str(srt)]
            if aligner_dir is not None:
                command.extend(['--aligner-dir',str(aligner_dir)])
            # Capture only aggregate counters. transcribe.py stdout includes a
            # private temporary output path; never stream it into public logs.
            outcome=subprocess.run(command,env=env,check=True,
                                   stdout=subprocess.PIPE,text=True)
            if aligner_dir is not None:
                alignment_reports.append(parse_alignment_metrics(outcome.stdout))
            report=validate_delivery(audio,srt)
            if report['status']!='OUTPUT_VALIDATED_NOT_YET_DELIVERED':
                raise SystemExit('BLOCKED: Invalid SRT in batch')
            metrics=analyze_srt(srt)
            qa_fast+=metrics['reading_too_fast']
            qa_short+=metrics['too_brief']
            qa_layout_warnings+=int(not metrics['layout_ok'])
            cues+=report['cues']
            completed.append((clip_name,srt.read_bytes()))
        asr_sec = time.monotonic() - asr_start
        payload=encode_bundle("output",completed) if batch else completed[0][1]
        emit_encrypted_srt(pack(payload,output_pub,OUTPUT_AAD))
        print('SRT_VALIDATED_CUES='+str(cues),flush=True)
        print('SRT_BATCH_ITEMS='+str(len(completed)),flush=True)
        print('SRT_AUTO_QA_FAST_CUES='+str(qa_fast),flush=True)
        print('SRT_AUTO_QA_SHORT_CUES='+str(qa_short),flush=True)
        print('SRT_AUTO_QA_LAYOUT_WARNINGS='+str(qa_layout_warnings),flush=True)
        print('SRT_MODEL_ID='+a.model,flush=True)
        print('SRT_ALIGNMENT_MODE='+a.alignment,flush=True)
        if a.alignment=='qwen':
            print('SRT_QWEN_ATTEMPTED_CHUNKS='+str(
                  int(sum(x["attempted"] for x in alignment_reports))),flush=True)
            print('SRT_QWEN_SUCCEEDED_CHUNKS='+str(
                  int(sum(x["succeeded"] for x in alignment_reports))),flush=True)
            print('SRT_QWEN_FALLBACK_CHUNKS='+str(
                  int(sum(x["fallback"] for x in alignment_reports))),flush=True)
            print('SRT_QWEN_BOUNDARY_COMPARISON_SAMPLES='+str(
                  int(sum(x["samples"] for x in alignment_reports))),flush=True)
            # Median/P95 below are per-clip, NOT pooled statistics for batches.
            for name in ("median","p95","max"):
                vals=[x[name] for x in alignment_reports if name in x]
                if vals:
                    print("SRT_QWEN_PER_CLIP_"+name.upper()+"_ABS_SHIFT_SECONDS="+
                          ",".join(f"{v:.3f}" for v in vals),flush=True)
            if not any(x["succeeded"] for x in alignment_reports):
                print("SRT_QWEN_NO_VALID_ALIGNMENT_USED_WHISPER_FALLBACK",flush=True)
        print(f'SRT_MODEL_DOWNLOAD_SECONDS={download_sec:.2f}',flush=True)
        print(f'SRT_ASR_GENERATION_SECONDS={asr_sec:.2f}',flush=True)
        print('OUTPUT_VALIDATED_NOT_YET_DELIVERED',flush=True)

if __name__ == '__main__':
    main()