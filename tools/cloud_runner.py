#!/usr/bin/env python3
"""GitHub standard-runner-only speech-to-SRT with AES-GCM private transport.

GitHub repository stores code only. Source cipher bytes live at an HTTPS URL;
raw audio and subtitles never appear in workflow inputs, logs, or artifacts.
"""
from __future__ import annotations
import base64
import os
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

AAD_INPUT = b"subtitle-srt-toolkit/audio/v1"
AAD_OUTPUT = b"subtitle-srt-toolkit/srt/v1"
ALLOWED_MODELS = {"tiny", "base", "small", "medium", "large-v3"}
ROOT = Path(__file__).resolve().parents[1]


def _cipher():
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw_key = os.getenv("SRT_TRANSPORT_KEY", "")
    try:
        key = bytes.fromhex(raw_key)
    except ValueError as exc:
        raise RuntimeError("Invalid transport key configuration") from exc
    if len(key) != 32:
        raise RuntimeError("Missing 32-byte AES-GCM GitHub Actions secret")
    return AESGCM(key)


def decrypt_packet(packet: bytes, aad: bytes) -> bytes:
    if len(packet) < 29:
        raise RuntimeError("Encrypted payload too short")
    return _cipher().decrypt(packet[:12], packet[12:], aad)


def encrypt_packet(clear: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + _cipher().encrypt(nonce, clear, aad)


def download_ciphertext(url: str, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    # Explicit allowlisting avoids turning workflow_dispatch into a generic URL fetcher.
    if parsed.scheme != "https" or parsed.hostname != "drive.google.com":
        raise RuntimeError("Input must use the approved encrypted Google Drive transport")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=120) as response:
        final_host = urlsplit(response.geturl()).hostname or ""
        if not (final_host == "drive.google.com" or final_host.endswith(".googleusercontent.com")):
            raise RuntimeError("Input URL redirected outside approved storage")
        packet = response.read(max_bytes + 1)
    if len(packet) > max_bytes:
        raise RuntimeError("Encrypted audio exceeds temporary transport limit")
    return packet


def run_pipeline(url: str, model_name: str) -> dict:
    if model_name not in ALLOWED_MODELS:
        raise RuntimeError("Model is not in the public allowlist")
    packet = download_ciphertext(url)
    audio_content = decrypt_packet(packet, AAD_INPUT)
    # No media is written to the repository, artifacts or caches.
    with tempfile.TemporaryDirectory(prefix="private_srt_") as temp:
        tmp = Path(temp)
        original = tmp / "source.opus"
        wav = tmp / "source.wav"
        outfile = tmp / "new.srt"
        original.write_bytes(audio_content)
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(original), "-ac", "1", "-ar", "16000", str(wav)
        ], check=True)
        # Static model WEIGHTS from public OSS hosting; NOT an inference API.
        from huggingface_hub import snapshot_download
        model_dir = tmp / "model"
        snapshot_download(repo_id=f"Systran/faster-whisper-{model_name}",
                          local_dir=str(model_dir))
        cmd = [sys.executable, str(ROOT / "transcribe.py"), str(wav),
               "--model-dir", str(model_dir), "--language", "zh",
               "--device", "cpu", "--compute-type", "int8",
               "--traditional", "--output", str(outfile)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=sys.stderr)
        from delivery_gate import validate_delivery
        report = validate_delivery(wav, outfile)
        if report["status"] != "OUTPUT_VALIDATED_NOT_YET_DELIVERED":
            raise RuntimeError("Output failed SRT validation gate")
        compressed = zlib.compress(outfile.read_bytes(), level=9)
        output_packet = encrypt_packet(compressed, AAD_OUTPUT)
        token = base64.b64encode(output_packet).decode("ascii")
        return {"token": token, "cues": report["cues"], "audio_sec": report["audio_seconds"]}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--encrypted-url", required=True)
    parser.add_argument("--model", default="small", choices=sorted(ALLOWED_MODELS))
    args = parser.parse_args()
    result = run_pipeline(args.encrypted_url, args.model)
    print(f"SRT_VALIDATED: {result['cues']} cues, audio {result['audio_sec']} s")
    print("SRT_RESULT_ENCRYPTED_B64=" + result["token"], flush=True)
    print("SRT_VALIDATED_NOT_YET_DELIVERED: encrypted output must be returned to chat")


if __name__ == "__main__":
    main()