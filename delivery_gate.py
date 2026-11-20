"""Strict offline SRT artifact gate; a valid file is NOT proof of chat delivery."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import wave

TIME = re.compile(r"^(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})$")
CUE = re.compile(r"^(\d+)\n([^\n]+) --> ([^\n]+)\n(.+)$", re.DOTALL)

class DeliveryBlocked(ValueError):
    """No acceptable SRT artifact was generated."""

def audio_duration(path: Path) -> float:
    if not path.is_file() or path.stat().st_size == 0:
        raise DeliveryBlocked("Audio is missing or empty")
    try:
        import soundfile as sf
        duration = sf.info(str(path)).duration
        if duration > 0:
            return float(duration)
    except (ImportError, RuntimeError, ValueError, OSError):
        pass
    try:
        with wave.open(str(path), "rb") as recording:
            seconds = recording.getnframes() / recording.getframerate()
            if seconds > 0:
                return seconds
    except (wave.Error, EOFError, OSError, ZeroDivisionError):
        pass
    try:
        command = ["ffprobe", "-v", "error", "-show_entries",
                   "format=duration", "-of",
                   "default=noprint_wrappers=1:nokey=1", str(path)]
        result = subprocess.run(command, capture_output=True,
                                text=True, check=True, timeout=15)
        seconds = float(result.stdout.strip())
        if seconds > 0:
            return seconds
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    raise DeliveryBlocked("Unable to determine audio duration locally")

def timestamp_ms(raw: str) -> int:
    match = TIME.fullmatch(raw)
    if not match:
        raise DeliveryBlocked(f"Invalid SRT timestamp: {raw!r}")
    hours, minutes, seconds, milliseconds = map(int, match.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as data:
        for chunk in iter(lambda: data.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def validate_delivery(audio: Path, srt: Path) -> dict:
    """Fail closed: missing/empty/malformed/out-of-range SRT never passes."""
    audio, srt = Path(audio).resolve(), Path(srt).resolve()
    if audio == srt or srt.suffix.lower() != ".srt":
        raise DeliveryBlocked("A separate .srt output file is required")
    duration = audio_duration(audio)
    if not srt.is_file() or srt.stat().st_size == 0:
        raise DeliveryBlocked("No nonempty SRT file was produced")
    try:
        source = srt.read_text("utf-8-sig").replace("\r\n", "\n").strip()
    except (OSError, UnicodeError) as exc:
        raise DeliveryBlocked("SRT must be readable UTF-8") from exc
    if not source:
        raise DeliveryBlocked("SRT has no subtitle cues")
    blocks = re.split(r"\n\s*\n", source)
    previous_end = -1
    last_end = 0
    for expected, block in enumerate(blocks, 1):
        match = CUE.fullmatch(block)
        if not match or int(match.group(1)) != expected:
            raise DeliveryBlocked(f"Malformed or unnumbered SRT cue {expected}")
        start, end = timestamp_ms(match.group(2)), timestamp_ms(match.group(3))
        if not match.group(4).strip() or start >= end or start < previous_end:
            raise DeliveryBlocked(f"Blank, inverted or overlapping SRT cue {expected}")
        if end > round(duration * 1000) + 100:
            raise DeliveryBlocked(f"Cue {expected} exceeds audio duration")
        previous_end = end
        last_end = end
    return {
        "status": "OUTPUT_VALIDATED_NOT_YET_DELIVERED",
        "cues": len(blocks),
        "audio_seconds": round(duration, 3),
        "last_cue_seconds": last_end / 1000,
        "audio_sha256": sha256_file(audio),
        "srt_sha256": sha256_file(srt),
        "output": str(srt),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Strict SRT artifact acceptance gate")
    parser.add_argument("audio", type=Path)
    parser.add_argument("srt", type=Path)
    args = parser.parse_args()
    try:
        report = validate_delivery(args.audio, args.srt)
    except DeliveryBlocked as exc:
        print(f"BLOCKED: {exc}")
        return 1
    print(f"OUTPUT_VALIDATED_NOT_YET_DELIVERED: {report['cues']} cues; "
          f"audio={report['audio_seconds']:.3f}s; "
          f"last_end={report['last_cue_seconds']:.3f}s")
    print("Not COMPLETE until the real SRT has been delivered to the user.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
