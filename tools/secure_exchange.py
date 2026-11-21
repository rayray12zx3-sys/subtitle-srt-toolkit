"""Ephemeral chat-session helper for GitHub-hosted private subtitle delivery.

This helper runs only in an authorized assistant cloud workspace, NOT the user's
Windows/PC. Transcription stays on the GitHub-hosted Actions runner.

No personal audio/transcript/private keys are uploaded to GitHub code/metadata.
Only a short-lived, AES-GCM encrypted audio blob is sent to a temporary
public-readable file. Caller RSA private key never leaves this workspace.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from delivery_gate import validate_delivery
from tools.batch_bundle import MAX_CLIPS, clip_id, encode_bundle, decode_bundle

MAGIC = b"SRT2"
INPUT_AAD = b"subtitle-srt-toolkit/input2"
OUTPUT_AAD = b"subtitle-srt-toolkit/output2"
MAX_INPUT_BYTES = 64 * 1024 * 1024
LOG_CHUNK_CHARS = 3000
_PART = re.compile(r"SRT_OUTPUT_CIPHER_PART_(\d{4})=([A-Za-z0-9+/=]+)")
_CIPHER = re.compile(r"SRT_OUTPUT_CIPHER_B64=([A-Za-z0-9+/=]{300,})")
_RUNNER = re.compile(r"SRT_INPUT_PUBLIC_KEY_B64=([A-Za-z0-9+/=]{380,500})")


def _base64_decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def parse_public_key(value: str) -> rsa.RSAPublicKey:
    """Accept the compact browser-safe modulus or the original DER base64."""
    if value.startswith("rsa-n:"):
        encoded = value[6:]
        if not re.fullmatch(r"[A-Za-z0-9_-]{342}", encoded):
            raise ValueError("Invalid compact public RSA modulus")
        modulus = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if len(modulus) != 256:
            raise ValueError("Invalid RSA modulus byte length")
        public = rsa.RSAPublicNumbers(65537, int.from_bytes(modulus, "big")).public_key()
    else:
        public = serialization.load_der_public_key(_base64_decode(value))
    if not isinstance(public, rsa.RSAPublicKey) or public.key_size != 2048:
        raise ValueError("Expected an RSA-2048 public key")
    if public.public_numbers().e != 65537:
        raise ValueError("Unexpected public exponent")
    return public


def compact_public_key(private: rsa.RSAPrivateKey) -> str:
    n = private.public_key().public_numbers().n.to_bytes(256, "big")
    return "rsa-n:" + base64.urlsafe_b64encode(n).decode("ascii").rstrip("=")


def make_envelope(content: bytes, public: rsa.RSAPublicKey, aad: bytes) -> bytes:
    if not content or len(content) > MAX_INPUT_BYTES:
        raise ValueError("Empty or oversized payload")
    session_key = os.urandom(32)
    wrapped = public.encrypt(
        session_key,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    nonce = os.urandom(12)
    return MAGIC + len(wrapped).to_bytes(2, "big") + wrapped + nonce + AESGCM(session_key).encrypt(
        nonce, content, aad
    )


def open_envelope(blob: bytes, private: rsa.RSAPrivateKey, aad: bytes) -> bytes:
    if not blob.startswith(MAGIC) or len(blob) < 6 + 256 + 12 + 16:
        raise ValueError("Invalid encrypted envelope")
    count = int.from_bytes(blob[4:6], "big")
    if count != 256 or len(blob) <= 18 + count:
        raise ValueError("Unexpected RSA envelope size")
    key = private.decrypt(
        blob[6:6 + count],
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return AESGCM(key).decrypt(blob[6 + count:18 + count], blob[18 + count:], aad)


def _save_private_pem(path: Path, private: rsa.RSAPrivateKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Fail closed if this key path already exists; never overwrite a private key.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ))


def make_return_key(path: Path) -> str:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _save_private_pem(path, private)
    return compact_public_key(private)


def runner_public_from_logs(log: str) -> rsa.RSAPublicKey:
    candidates = _RUNNER.findall(log)
    if not candidates:
        raise ValueError("No complete runner input PUBLIC key in the job log")
    return parse_public_key(candidates[-1])


def prepare_encrypted_input(audio: Path, runner_public: rsa.RSAPublicKey,
                            output: Path, ffmpeg: str = "ffmpeg") -> int:
    if not audio.is_file() or not audio.stat().st_size:
        raise ValueError("Missing or empty original audio")
    with tempfile.TemporaryDirectory(prefix="chat_audio_cipher_") as temp:
        opus = Path(temp) / "source.opus"
        # Speech-quality mono Opus shrinks large WAV input for the encrypted Drive exchange.
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-i", str(audio), "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "libopus", "-b:a", "48k", str(opus)],
            check=True, timeout=180, capture_output=True
        )
        payload = opus.read_bytes()
        packet = make_envelope(payload, runner_public, INPUT_AAD)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as target:
        target.write(packet)
    return len(packet)


def emit_encrypted_srt(blob: bytes) -> None:
    """Write *ciphertext only* to GitHub job logs, safely split for long SRTs."""
    encoded = base64.b64encode(blob).decode("ascii")
    if len(encoded) <= LOG_CHUNK_CHARS:
        print("SRT_OUTPUT_CIPHER_B64=" + encoded, flush=True)
        return
    pieces = [encoded[i:i + LOG_CHUNK_CHARS]
              for i in range(0, len(encoded), LOG_CHUNK_CHARS)]
    if len(pieces) > 9999:
        raise ValueError("Too many ciphertext chunks")
    print("SRT_OUTPUT_CIPHER_PARTS=" + str(len(pieces)), flush=True)
    for i, part in enumerate(pieces):
        print(f"SRT_OUTPUT_CIPHER_PART_{i:04d}=" + part, flush=True)
    print("SRT_OUTPUT_CIPHER_READY=1", flush=True)


def output_envelope_from_logs(log: str) -> bytes:
    """Only accept a whole output. Reject truncated/incomplete/duplicate chunks."""
    count_fields = re.findall(r"SRT_OUTPUT_CIPHER_PARTS=(\d{1,4})", log)
    if count_fields:
        count = int(count_fields[-1])
        if count < 2 or count > 9999:
            raise ValueError("Invalid output chunk count")
        if "SRT_OUTPUT_CIPHER_READY=1" not in log:
            raise ValueError("Encrypted output is incomplete")
        found: dict[int, str] = {}
        for index, part in _PART.findall(log):
            pos = int(index)
            if pos in found or pos >= count:
                raise ValueError("Duplicate or unexpected encrypted output chunk")
            found[pos] = part
        if len(found) != count or set(found) != set(range(count)):
            raise ValueError("Missing encrypted output chunk")
        return _base64_decode("".join(found[i] for i in range(count)))
    legacy = _CIPHER.findall(log)
    if len(legacy) != 1:
        raise ValueError("Missing or ambiguous complete encrypted SRT output")
    return _base64_decode(legacy[0])


def finish_srt(log: str, private_key: Path, original_audio: Path, output: Path) -> dict:
    key = serialization.load_pem_private_key(private_key.read_bytes(), password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 2048:
        raise ValueError("Invalid return private key")
    plain = open_envelope(output_envelope_from_logs(log), key, OUTPUT_AAD)
    if not output.name.lower().endswith(".srt"):
        raise ValueError("Output must be an SRT file")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Keep a pre-existing SRT unchanged until the *new* result passes validation.
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".srt",
                                     prefix=".srt-pending-", delete=False) as pending:
        temporary = Path(pending.name)
        pending.write(plain)
    try:
        report = validate_delivery(original_audio, temporary)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return report



def prepare_batch_input(audios: list[Path], public: rsa.RSAPublicKey,
                        output: Path, ffmpeg: str = "ffmpeg") -> int:
    if not 1<=len(audios)<=MAX_CLIPS: raise ValueError("Expected 1..8 audio files")
    items=[]
    with tempfile.TemporaryDirectory(prefix="private_batch_") as d:
        for i,audio in enumerate(audios,1):
            if not audio.is_file() or not audio.stat().st_size:
                raise ValueError("Missing/empty batch audio")
            opus=Path(d)/f"{clip_id(i)}.opus"
            subprocess.run([ffmpeg,"-hide_banner","-loglevel","error","-nostdin","-y",
                            "-i",str(audio),"-vn","-ac","1","-ar","16000",
                            "-c:a","libopus","-b:a","48k",str(opus)],
                           check=True,timeout=180,capture_output=True)
            items.append((clip_id(i),opus.read_bytes()))
        ciphertext=make_envelope(encode_bundle("input",items),public,INPUT_AAD)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("xb") as f:f.write(ciphertext)
    return len(ciphertext)


def finish_batch_srt(log: str, private_key: Path, audios: list[Path],
                     output_dir: Path) -> list[dict]:
    """Fail closed: nothing is exposed until *all* SRT/audio pairs pass."""
    import shutil
    if output_dir.exists() or not 1<=len(audios)<=MAX_CLIPS:
        raise ValueError("New output directory and 1..8 originals required")
    private=serialization.load_pem_private_key(private_key.read_bytes(),password=None)
    if not isinstance(private,rsa.RSAPrivateKey) or private.key_size!=2048:
        raise ValueError("Invalid private return key")
    result=decode_bundle(open_envelope(output_envelope_from_logs(log),private,OUTPUT_AAD),
                         "output")
    if len(result)!=len(audios): raise ValueError("Batch count mismatch")
    output_dir.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".pending-srt-batch-",dir=output_dir.parent))
    reports=[]
    try:
        for i,((name,raw),audio) in enumerate(zip(result,audios),1):
            if name!=clip_id(i): raise ValueError("Wrong clip ordering")
            path=staging/f"{name}.srt"
            path.write_bytes(raw)
            reports.append(validate_delivery(audio,path))
        if output_dir.exists(): raise FileExistsError("Output directory exists")
        os.rename(staging,output_dir)
        return reports
    finally:
        if staging.exists(): shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description="Private ChatGPT cloud-side SRT transfer helper")
    commands = parser.add_subparsers(dest="action", required=True)
    key = commands.add_parser("new-return-key", help="Create a private key in the assistant's ephemeral workspace")
    key.add_argument("--private-key", required=True, type=Path)
    encrypt = commands.add_parser("encrypt-input")
    encrypt.add_argument("--audio", required=True, type=Path)
    encrypt.add_argument("--runner-log", required=True, type=Path)
    encrypt.add_argument("--cipher-out", required=True, type=Path)
    batch = commands.add_parser("encrypt-batch")
    batch.add_argument("--audio", action="append", type=Path, required=True)
    batch.add_argument("--runner-log", type=Path, required=True)
    batch.add_argument("--cipher-out", type=Path, required=True)
    final_batch = commands.add_parser("finish-batch")
    final_batch.add_argument("--private-key", type=Path, required=True)
    final_batch.add_argument("--job-log", type=Path, required=True)
    final_batch.add_argument("--audio", action="append", type=Path, required=True)
    final_batch.add_argument("--output-dir", type=Path, required=True)
    decrypt = commands.add_parser("finish")
    decrypt.add_argument("--private-key", required=True, type=Path)
    decrypt.add_argument("--job-log", required=True, type=Path)
    decrypt.add_argument("--original-audio", required=True, type=Path)
    decrypt.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.action == "new-return-key":
        print("PUBLIC_KEY_ONLY=" + make_return_key(args.private_key))
        print("KEEP_PRIVATE_KEY_IN_EPHEMERAL_ASSISTANT_WORKSPACE")
    elif args.action == "encrypt-input":
        public = runner_public_from_logs(args.runner_log.read_text("utf-8"))
        size = prepare_encrypted_input(args.audio, public, args.cipher_out)
        print("ENCRYPTED_INPUT_READY: ciphertext bytes=" + str(size))
        print("Only upload this ciphertext. Never upload the original recording.")
    elif args.action == "encrypt-batch":
        key = runner_public_from_logs(args.runner_log.read_text("utf-8"))
        size = prepare_batch_input(args.audio, key, args.cipher_out)
        print("ENCRYPTED_BATCH_INPUT_READY: items=" + str(len(args.audio)) +
              ", ciphertext_bytes=" + str(size))
    elif args.action == "finish-batch":
        reports = finish_batch_srt(args.job_log.read_text("utf-8"), args.private_key,
                                   args.audio, args.output_dir)
        print("BATCH_VALIDATED_NOT_YET_DELIVERED: items=" + str(len(reports)) +
              ", cues=" + str(sum(x["cues"] for x in reports)))
    else:
        report = finish_srt(args.job_log.read_text("utf-8"),
                            args.private_key, args.original_audio, args.output)
        print("SRT_VALIDATED_NOT_YET_DELIVERED: cues=" + str(report["cues"]))
        print("The caller must actually attach the resulting .srt in chat.")


if __name__ == "__main__":
    main()
