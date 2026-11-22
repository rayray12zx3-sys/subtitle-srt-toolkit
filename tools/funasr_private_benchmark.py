"""Private Fun-ASR-Nano-2512 GGUF CPU benchmark (VAD-level SRT or text only).

Designed for the existing signed ciphertext-only owner Issue transport.
Never prints audio, recognized text, raw URLs or plaintext SRT to GitHub logs.
The official runtime is pinned; model GGUF files are downloaded only on the
ephemeral standard GitHub Ubuntu runner, without a hosted AI inference API.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from tools.cloud_handshake import (
    pack, unpack, fetch_public_drive_blob, INPUT_AAD, OUTPUT_AAD,
)
from tools.signed_cipher_transport import (
    find_packet_urls, fetch_signed_ciphertext, publish_runner_public_key,
)

FUNASR_REPO = "https://github.com/modelscope/FunASR.git"
FUNASR_PIN = "68aa96ddb96b6ec9b2f50923b9c55d223ef483af"
MODEL_ID = "fun-asr-nano-2512"
_ALLOWED_CIPHERTEXT_SIZE = 64 * 1024 * 1024 + 512


def parse_return_key(raw: str):
    if raw.startswith("rsa-n:"):
        encoded = raw[6:]
        modulus = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if len(modulus) != 256 or not modulus[0] & 128 or not modulus[-1] & 1:
            raise ValueError("Invalid 2048-bit RSA public key")
        return rsa.RSAPublicNumbers(65537, int.from_bytes(modulus, "big")).public_key()
    return serialization.load_der_public_key(base64.b64decode(raw, validate=True))


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, **kwargs)


def get_encrypted_source(args, private):
    started = time.monotonic()
    while time.monotonic() - started < args.max_wait:
        if args.transport == "signed-url":
            try:
                links = find_packet_urls(int(os.environ["GITHUB_RUN_ID"]), os.environ["GITHUB_TOKEN"])
                packets = [fetch_signed_ciphertext(link) for link in links[:3]]
            except Exception:
                packets = []
        else:
            packets = [fetch_public_drive_blob(args.drive_id)]
        for packet in packets:
            if not packet or len(packet) > _ALLOWED_CIPHERTEXT_SIZE:
                continue
            try:
                plain = unpack(packet, private, INPUT_AAD)
                if not plain or len(plain) > _ALLOWED_CIPHERTEXT_SIZE:
                    continue
                return plain
            except Exception:
                continue
        time.sleep(10)
    raise RuntimeError("BLOCKED: No compatible encrypted audio before timeout")


def run_funasr_cpu(root: Path, wav: Path):
    engine = root / "funasr-src"
    build = root / "build"
    weights = root / "gguf"
    start = time.monotonic()
    run(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
         FUNASR_REPO, str(engine)], stdout=subprocess.DEVNULL)
    run(["git", "-C", str(engine), "fetch", "--depth", "1", "origin", FUNASR_PIN],
        stdout=subprocess.DEVNULL)
    run(["git", "-C", str(engine), "checkout", "--detach", FUNASR_PIN],
        stdout=subprocess.DEVNULL)
    runtime = engine / "runtime" / "llama.cpp"
    run(["cmake", "-S", str(runtime), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
        stdout=subprocess.DEVNULL)
    run(["cmake", "--build", str(build), "--target", "llama-funasr-cli", "-j", "2"],
        stdout=subprocess.DEVNULL)
    build_sec = time.monotonic() - start
    dl_start = time.monotonic()
    run(["bash", str(runtime / "download-funasr-model.sh"),
         "nano", str(weights), "q8_0"], stdout=subprocess.DEVNULL)
    download_sec = time.monotonic() - dl_start
    binary = build / "bin" / "llama-funasr-cli"
    names = ["funasr-encoder-f16.gguf", "qwen3-0.6b-q8_0.gguf", "fsmn-vad.gguf"]
    for name in names:
        if not (weights / name).is_file():
            raise RuntimeError("Missing pinned GGUF component: " + name)
    start = time.monotonic()
    base = [str(binary), "--enc", str(weights / names[0]),
            "-m", str(weights / names[1]), "--vad", str(weights / names[2]),
            "-a", str(wav)]
    result = run([*base, "--srt"], stdout=subprocess.PIPE,
                 stderr=subprocess.DEVNULL, text=True)
    native_srt = result.stdout.strip()
    mode = "none"
    cues = 0
    srt_payload = None
    transcript = ""
    if re.search(r"(?m)^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3} --> ", native_srt):
        from delivery_gate import validate_delivery
        srt = root / "funasr_candidate.srt"
        srt.write_text(native_srt + "\n", encoding="utf-8")
        try:
            verdict = validate_delivery(wav, srt)
        except (ValueError, AssertionError):
            verdict = {}
        if verdict.get("status") == "OUTPUT_VALIDATED_NOT_YET_DELIVERED":
            srt_payload = native_srt + "\n"
            cues = verdict["cues"]
            mode = "vad_segment_timestamps_not_word_aligned"
            chunks = re.split(r"\n\s*\n", native_srt)
            lines = []
            for chunk in chunks:
                part = chunk.splitlines()
                if len(part) >= 3 and "-->" in part[1]:
                    lines.append(" ".join(part[2:]))
            transcript = " ".join(lines).strip()
    if not transcript:
        # Native SRT is not always a reliable delivery artifact; use text-only
        # fallback without claiming timestamps, preserving the successful ASR.
        result = run(base, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        transcript = result.stdout.strip()
        mode = "none"
        cues = 0
        srt_payload = None
    seconds = time.monotonic() - start
    if len(transcript) < 20:
        raise RuntimeError("BLOCKED: Fun-ASR-Nano produced no usable transcription")
    return {
        "engine": MODEL_ID,
        "transcript": transcript,
        "timings": mode,
        "srt": srt_payload,
        "candidate_cues": cues,
        "reference_status": "ai-unverified",
    }, (build_sec, download_sec, seconds)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--transport", choices=["signed-url", "drive"], default="signed-url")
    p.add_argument("--drive-id", default="")
    p.add_argument("--output-pub", required=True)
    p.add_argument("--max-wait", type=int, default=1800)
    args = p.parse_args()
    if args.transport == "drive" and not args.drive_id:
        p.error("Drive transport requires encrypted file id")
    if args.transport == "signed-url":
        if args.drive_id:
            p.error("Drive id cannot accompany signed-url")
        if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GITHUB_RUN_ID"):
            p.error("GitHub owner Issue token/run required")
    recipient = parse_return_key(args.output_pub)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_der = private.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_b64 = base64.b64encode(public_der).decode("ascii")
    print("FUNASR_INPUT_PUBLIC_KEY_B64=" + public_b64, flush=True)
    if args.transport == "signed-url":
        publish_runner_public_key(int(os.environ["GITHUB_RUN_ID"]),
                                  public_b64, os.environ["GITHUB_TOKEN"])
        print("FUNASR_PUBLIC_KEY_PUBLISHED_TO_CONTROL_ISSUE", flush=True)
    print("WAITING_FOR_ENCRYPTED_INPUT", flush=True)
    source_bytes = get_encrypted_source(args, private)
    with tempfile.TemporaryDirectory(prefix="private_funasr_") as t:
        root = Path(t)
        opus = root / "source.opus"
        wav = root / "audio.wav"
        opus.write_bytes(source_bytes)
        del source_bytes
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-i", str(opus), "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", str(wav)], stdout=subprocess.DEVNULL)
        opus.unlink(missing_ok=True)
        result, (build_sec, download_sec, asr_sec) = run_funasr_cpu(root, wav)
        payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        ciphertext = base64.b64encode(pack(payload, recipient, OUTPUT_AAD)).decode("ascii")
        print("FUNASR_OUTPUT_CIPHER_B64=" + ciphertext, flush=True)
        print(f"FUNASR_BUILD_SECONDS={build_sec:.2f}", flush=True)
        print(f"FUNASR_MODEL_DOWNLOAD_SECONDS={download_sec:.2f}", flush=True)
        print(f"FUNASR_ASR_SECONDS={asr_sec:.2f}", flush=True)
        print("FUNASR_TRANSCRIPT_CHARS=" + str(len(result["transcript"])), flush=True)
        print("FUNASR_CANDIDATE_CUES=" + str(result["candidate_cues"]), flush=True)
        print("FUNASR_TIMINGS_MODE=" + result["timings"], flush=True)
        print("FUNASR_TEXT_ENCRYPTED_NOT_AUTO_PROMOTED", flush=True)


if __name__ == "__main__":
    main()
