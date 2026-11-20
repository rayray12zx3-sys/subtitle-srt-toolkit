#!/usr/bin/env python3
"""Private Qwen3-ASR 0.6B benchmark on GitHub-hosted CPU; encrypted transcript only.

No SRT claim: forced alignment is NOT part of this benchmarking lane.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from tools.cloud_handshake import pack, unpack, fetch_public_drive_blob, INPUT_AAD, OUTPUT_AAD

PINNED_QWEN_C_COMMIT = "924694251d9e0f18e5d86bbd06aa3ab5f870002d"

def run_command(argv, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--drive-id", required=True)
    p.add_argument("--output-pub", required=True)
    p.add_argument("--max-wait", type=int, default=1800)
    args = p.parse_args()
    recipient = serialization.load_der_public_key(base64.b64decode(args.output_pub, validate=True))
    receiver = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = receiver.public_key().public_bytes(serialization.Encoding.DER,
                                             serialization.PublicFormat.SubjectPublicKeyInfo)
    print("QWEN_INPUT_PUBLIC_KEY_B64=" + base64.b64encode(pub).decode("ascii"), flush=True)
    print("WAITING_FOR_ENCRYPTED_INPUT", flush=True)

    source_bytes = None
    started = time.monotonic()
    while time.monotonic() - started < args.max_wait:
        blob = fetch_public_drive_blob(args.drive_id)
        if blob:
            try:
                source_bytes = unpack(blob, receiver, INPUT_AAD)
            except (ValueError, Exception):
                pass
        if source_bytes:
            break
        time.sleep(10)
    if not source_bytes:
        raise SystemExit("BLOCKED: compatible encrypted audio did not arrive")

    with tempfile.TemporaryDirectory(prefix="private_qwen_") as temp:
        root = Path(temp)
        source = root / "source.opus"
        wav = root / "audio.wav"
        engine = root / "qwen-c"
        model = root / "weights"
        source.write_bytes(source_bytes)
        run_command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                     "-i", str(source), "-ar", "16000", "-ac", "1",
                     "-c:a", "pcm_s16le", str(wav)], stdout=subprocess.DEVNULL)
        build_start = time.monotonic()
        run_command(["git", "clone", "--depth", "1", "https://github.com/antirez/qwen-asr.git", str(engine)],
                    stdout=subprocess.DEVNULL)
        # Fetch pinned upstream revision if shallow-clone head has advanced.
        run_command(["git", "-C", str(engine), "fetch", "--depth", "1", "origin", PINNED_QWEN_C_COMMIT],
                    stdout=subprocess.DEVNULL)
        run_command(["git", "-C", str(engine), "checkout", "--detach", PINNED_QWEN_C_COMMIT],
                    stdout=subprocess.DEVNULL)
        run_command(["make", "-C", str(engine), "blas", "-j", "2"], stdout=subprocess.DEVNULL)
        build_sec = time.monotonic() - build_start
        weights_start = time.monotonic()
        run_command([str(engine / "download_model.sh"), "--model", "small", "--dir", str(model)],
                    cwd=str(engine), stdout=subprocess.DEVNULL)
        download_sec = time.monotonic() - weights_start

        asr_start = time.monotonic()
        cmd = [str(engine / "qwen_asr"), "-d", str(model), "-i", str(wav), "--silent"]
        result = run_command(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        asr_sec = time.monotonic() - asr_start
        text = result.stdout.strip()
        if len(text) < 20:
            raise SystemExit("BLOCKED: Qwen produced insufficient transcript text")
        payload = json.dumps({"engine": "qwen3-asr-0.6b", "transcript": text},
                             ensure_ascii=False).encode("utf-8")
        print("QWEN_OUTPUT_CIPHER_B64=" + base64.b64encode(pack(payload, recipient, OUTPUT_AAD)).decode("ascii"),
              flush=True)
        print(f"QWEN_BUILD_SECONDS={build_sec:.2f}", flush=True)
        print(f"QWEN_MODEL_DOWNLOAD_SECONDS={download_sec:.2f}", flush=True)
        print(f"QWEN_ASR_SECONDS={asr_sec:.2f}", flush=True)
        print(f"QWEN_TRANSCRIPT_CHARS={len(text)}", flush=True)
        print("QWEN_TEXT_ONLY_NO_SRT: timestamps require a separate alignment stage", flush=True)

if __name__ == "__main__":
    main()
