#!/usr/bin/env python3
"""Generate a local, offline UTF-8 SRT using pre-downloaded faster-whisper weights.

No account, paid API, free-tier inference quota, or network model fallback is used.
"""
import argparse
import os
import re
from pathlib import Path
from delivery_gate import DeliveryBlocked, validate_delivery

TERMINAL_PUNCT = "，。！？；：、,.!?;:"


def clean_text(text: str, minimal_punctuation: bool = True) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if minimal_punctuation:
        text = text.strip(TERMINAL_PUNCT + " ")
    return text


def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remaining = divmod(milliseconds, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    secs, ms = divmod(remaining, 1_000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def require_local_model(folder: Path) -> Path:
    """Fail closed: never interpret model names as online model identifiers."""
    path = folder.expanduser().resolve()
    essential = (path / "model.bin", path / "config.json")
    if not path.is_dir() or any(not f.is_file() or f.stat().st_size == 0 for f in essential):
        raise ValueError(
            f"Missing local CTranslate2 Whisper model at {path}. "
            "Supply --model-dir with downloaded model.bin and config.json; "
            "automatic model downloads and cloud fallback are disabled."
        )
    return path


def enable_offline_mode() -> None:
    """Disable Hugging Face network fallback before importing model libraries."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def group_words(words, max_chars: int, max_duration: float, gap: float):
    """Preserve all recognized words in order; split at length, time and pauses."""
    groups, current = [], []
    for item in words:
        token = item.word
        if not token.strip():
            continue
        if current:
            prev = current[-1]
            size = len("".join(w.word for w in current) + token)
            if (size > max_chars
                    or item.end - current[0].start > max_duration
                    or item.start - prev.end > gap):
                groups.append(current)
                current = []
        current.append(item)
    if current:
        groups.append(current)
    return groups


def write_srt(groups, output: Path, minimal_punctuation: bool, converter=None):
    """Write subtitle text only on the local filesystem."""
    parts = []
    for group in groups:
        content = clean_text("".join(x.word for x in group), minimal_punctuation)
        if converter is not None:
            content = converter(content)
        if content:
            parts.append(
                f"{len(parts) + 1}\n"
                f"{srt_time(group[0].start)} --> {srt_time(group[-1].end)}\n"
                f"{content}\n"
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts) + ("\n" if parts else ""),
                      encoding="utf-8-sig")
    return len(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Fully offline audio -> SRT using a pre-downloaded local Whisper model"
    )
    parser.add_argument("audio", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--model-dir", "--model", dest="model_dir", type=Path, required=True,
        help="Path to an existing local CTranslate2 faster-whisper model (not a model ID)"
    )
    parser.add_argument("--language", default=None)
    parser.add_argument("--traditional", action="store_true",
                        help="Convert Chinese text offline using OpenCC s2t")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--compute-type", default="default")
    parser.add_argument("--max-chars", type=int, default=22)
    parser.add_argument("--max-seconds", type=float, default=4.0)
    parser.add_argument("--max-gap", type=float, default=0.45)
    parser.add_argument("--keep-punctuation", action="store_true")
    args = parser.parse_args()

    if not args.audio.is_file():
        parser.error(f"Audio file not found: {args.audio}")
    try:
        model_dir = require_local_model(args.model_dir)
    except ValueError as exc:
        parser.error(str(exc))
    if args.max_chars < 1 or args.max_seconds <= 0 or args.max_gap < 0:
        parser.error("Invalid subtitle size/timing limits")

    enable_offline_mode()
    from faster_whisper import WhisperModel

    converter = None
    if args.traditional:
        from opencc import OpenCC
        converter = OpenCC("s2t").convert

    model = WhisperModel(
        str(model_dir), device=args.device, compute_type=args.compute_type
    )
    segments, info = model.transcribe(
        str(args.audio), language=args.language, word_timestamps=True,
        vad_filter=True, beam_size=5, condition_on_previous_text=True
    )
    words = [word for seg in segments for word in (seg.words or [])]
    if not words:
        raise SystemExit("No recognized speech; SRT not written")

    grouped = group_words(words, args.max_chars, args.max_seconds, args.max_gap)
    target = args.output or args.audio.with_suffix(".srt")
    if target.suffix.lower() != ".srt":
        parser.error("Output must have the .srt extension")
    pending = target.with_name(target.stem + ".pending.srt")
    try:
        count = write_srt(
            grouped, pending, not args.keep_punctuation, converter=converter
        )
        report = validate_delivery(args.audio, pending)
        if report["cues"] != count:
            raise DeliveryBlocked("Subtitle count mismatch")
        pending.replace(target)
        report = validate_delivery(args.audio, target)
    except Exception as exc:
        pending.unlink(missing_ok=True)
        raise SystemExit(f"BLOCKED: no validated new SRT deliverable: {exc}") from exc
    print(f"OUTPUT_VALIDATED_NOT_YET_DELIVERED: {target}; "
          f"{report['cues']} cues; detected={info.language}")
    print("OFFLINE: no inference service/API quota was used.")
    print("Task remains INCOMPLETE until the SRT is actually delivered to the user.")
    print("Manual word-for-word accuracy review is not established by this check.")


if __name__ == "__main__":
    main()
