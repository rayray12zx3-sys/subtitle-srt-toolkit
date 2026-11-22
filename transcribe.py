#!/usr/bin/env python3
"""Generate a local, offline UTF-8 SRT using pre-downloaded faster-whisper weights.

No account, paid API, free-tier inference quota, or network model fallback is used.
"""
import argparse
import os
import re
import statistics
import tempfile
from pathlib import Path
from types import SimpleNamespace
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


def write_srt(groups, output: Path, minimal_punctuation: bool, converter=None,
              line_chars=None, max_lines=2, optimize_timing=False):
    """Write subtitle text only on the local filesystem."""
    parts = []
    if optimize_timing:
        from tools.subtitle_timing import cue_windows
        windows = cue_windows(groups)
    else:
        windows = [(g[0].start, g[-1].end) for g in groups]
    for group, (begin, end) in zip(groups, windows):
        if line_chars:
            from tools.smart_segmentation import break_lines
            lines = break_lines(group, line_chars, max_lines)
            content = "\n".join(clean_text(line, minimal_punctuation) for line in lines)
        else:
            content = clean_text("".join(x.word for x in group), minimal_punctuation)
        if converter is not None:
            content = converter(content)
        if content:
            parts.append(
                f"{len(parts) + 1}\n"
                f"{srt_time(begin)} --> {srt_time(end)}\n"
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
    parser.add_argument("--language", default=None,
                        help="BCP language code, or auto to detect language per chunk")
    parser.add_argument("--aligner-dir", type=Path, default=None,
                        help="Optional pre-downloaded official Qwen3 aligner; never auto-download")
    parser.add_argument("--chunk-seconds", type=int, default=0,
                        help="Split normalized mono 16-bit PCM WAV into bounded segments; 0 disables")
    parser.add_argument("--traditional", action="store_true",
                        help="Convert Chinese text offline using OpenCC s2t")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--compute-type", default="default")
    parser.add_argument("--max-chars", type=int, default=22)
    parser.add_argument("--segmentation", choices=["smart", "basic"], default="smart",
                        help="Fully automatic semantic + pause segmentation; basic for legacy")
    parser.add_argument("--line-chars", type=int, default=12,
                        help="Approximate Chinese characters per subtitle line")
    parser.add_argument("--max-lines", type=int, choices=[1, 2], default=2)
    parser.add_argument("--reading-rate", type=float, default=8.0,
                        help="Auto quality warning threshold in weighted reading units/second")
    parser.add_argument("--max-seconds", type=float, default=4.0)
    parser.add_argument("--max-gap", type=float, default=0.45)
    parser.add_argument("--keep-punctuation", action="store_true")
    args = parser.parse_args()

    if not args.audio.is_file():
        raise SystemExit(f"BLOCKED: Audio file not found: {args.audio}")
    try:
        model_dir = require_local_model(args.model_dir)
    except ValueError as exc:
        raise SystemExit(f"BLOCKED: {exc}") from exc
    if args.chunk_seconds < 0 or args.chunk_seconds == 1 or args.chunk_seconds > 3600:
        raise SystemExit("BLOCKED: --chunk-seconds must be 0 or between 2 and 3600")
    if args.reading_rate <= 0:
        raise SystemExit("BLOCKED: --reading-rate must be positive")
    if args.line_chars < 1:
        raise SystemExit("BLOCKED: --line-chars must be positive")
    if args.max_chars < 1 or args.max_seconds <= 0 or args.max_gap < 0:
        raise SystemExit("BLOCKED: Invalid subtitle size/timing limits")

    enable_offline_mode()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit("BLOCKED: Local faster-whisper package is not installed") from exc

    converter = None
    if args.traditional:
        from opencc import OpenCC
        converter = OpenCC("s2t").convert

    model = WhisperModel(
        str(model_dir), device=args.device, compute_type=args.compute_type
    )
    language = None if args.language in (None, "auto") else args.language
    aligner = None
    alignment_attempted=0
    alignment_succeeded=0
    alignment_boundary_deltas=[]
    if args.aligner_dir is not None:
        from tools.qwen_forced_alignment import QwenCPUAligner
        aligner=QwenCPUAligner(args.aligner_dir)
    words = []
    detected_languages = []
    # Qwen's documented 5-minute maximum requires at most 240-second
    # speech chunks; don't silently attempt a 600-second alignment.
    effective_chunk=min(args.chunk_seconds or 240,240) if aligner else args.chunk_seconds
    if effective_chunk:
        from tools.chunking import split_pcm_wav, ChunkingError
        with tempfile.TemporaryDirectory(prefix="asr_chunks_") as temp_dir:
            try:
                parts = split_pcm_wav(args.audio, Path(temp_dir), effective_chunk)
            except (ChunkingError, OSError, ValueError) as exc:
                raise SystemExit(f"BLOCKED: chunk preparation failed: {exc}") from exc
            for part, offset, duration in parts:
                segments, info = model.transcribe(
                    str(part), language=language, word_timestamps=True,
                    vad_filter=True, beam_size=5, condition_on_previous_text=True
                )
                detected_languages.append(info.language)
                local_words=[]
                for seg in segments:
                    for w in (seg.words or []):
                        start = max(0., min(duration, w.start))
                        end = max(start, min(duration, w.end))
                        if not w.word.strip() or end <= start:
                            continue
                        local_words.append(SimpleNamespace(
                            word=w.word, start=start, end=end))
                if aligner and local_words:
                    alignment_attempted+=1
                    try:
                        candidate=aligner.align(part,local_words,info.language,duration)
                        from tools.qwen_forced_alignment import alignment_boundary_shifts
                        delta=alignment_boundary_shifts(local_words,candidate)
                        alignment_boundary_deltas.extend(delta)
                        local_words=candidate
                        alignment_succeeded+=1
                    except (ValueError,RuntimeError,KeyError,IndexError,TypeError):
                        # ASR output and aligner must match exactly. Never
                        # silently rewrite text or inject invented timing.
                        pass
                for w in local_words:
                    words.append(SimpleNamespace(word=w.word,
                                  start=offset+w.start,end=offset+w.end))
    else:
        segments, info = model.transcribe(
            str(args.audio), language=language, word_timestamps=True,
            vad_filter=True, beam_size=5, condition_on_previous_text=True
        )
        words = [word for seg in segments for word in (seg.words or [])]
        detected_languages = [info.language]
    if not words:
        raise SystemExit("BLOCKED: No recognized speech; SRT not written")

    if args.segmentation == "smart":
        from tools.smart_segmentation import segment_words
        grouped = segment_words(words, args.max_chars, args.max_seconds, args.max_gap,
                                args.line_chars, args.max_lines)
    else:
        grouped = group_words(words, args.max_chars, args.max_seconds, args.max_gap)
    target = args.output or args.audio.with_suffix(".srt")
    if target.suffix.lower() != ".srt":
        raise SystemExit("BLOCKED: Output must have the .srt extension")
    pending = target.with_name(target.stem + ".pending.srt")
    try:
        count = write_srt(
            grouped, pending, not args.keep_punctuation, converter=converter,
            line_chars=args.line_chars if args.segmentation == "smart" else None,
            max_lines=args.max_lines,
            optimize_timing=args.segmentation == "smart"
        )
        report = validate_delivery(args.audio, pending)
        if report["cues"] != count:
            raise DeliveryBlocked("Subtitle count mismatch")
        pending.replace(target)
        report = validate_delivery(args.audio, target)
        if args.segmentation == "smart":
            from tools.subtitle_quality import analyze_srt
            quality=analyze_srt(target,args.line_chars,args.max_lines,args.reading_rate)
            if not quality["layout_ok"]:
                print("AUTO_LAYOUT_WARNING: unbreakable ASR token/layout exceeded capacity")
            print(f"AUTO_QA_CUES={quality['cues']} AUTO_QA_FAST={quality['reading_too_fast']} "
                  f"AUTO_QA_SHORT={quality['too_brief']} AUTO_QA_MAX_RATE={quality['high_rate']:.2f}")
    except Exception as exc:
        pending.unlink(missing_ok=True)
        raise SystemExit(f"BLOCKED: no validated new SRT deliverable: {exc}") from exc
    recognized = ",".join(detected_languages)
    print(f"OUTPUT_VALIDATED_NOT_YET_DELIVERED: {target}; "
          f"{report['cues']} cues; detected={recognized}")
    if aligner:
        print(f"ALIGNER_ATTEMPTED_CHUNKS={alignment_attempted} ALIGNER_SUCCEEDED_CHUNKS={alignment_succeeded}")
        print("ALIGNER_FALLBACK_CHUNKS="+str(alignment_attempted-alignment_succeeded))
        print("ALIGNER_BOUNDARY_COMPARISON_SAMPLES="+str(len(alignment_boundary_deltas)))
        if alignment_boundary_deltas:
            sorted_shifts=sorted(alignment_boundary_deltas)
            n=len(sorted_shifts)
            p95=sorted_shifts[max(0,(95*n+99)//100-1)]
            print("ALIGNER_BOUNDARY_MEDIAN_ABS_SHIFT_SECONDS=" +
                  f"{statistics.median(sorted_shifts):.3f}")
            print("ALIGNER_BOUNDARY_P95_ABS_SHIFT_SECONDS="+f"{p95:.3f}")
            print("ALIGNER_BOUNDARY_MAX_ABS_SHIFT_SECONDS="+f"{sorted_shifts[-1]:.3f}")
        else:
            print("ALIGNER_NO_ACCEPTED_ALIGNMENT: preserve Whisper times")
    print("OFFLINE: no inference service/API quota was used.")
    print("Task remains INCOMPLETE until the SRT is actually delivered to the user.")
    print("Manual word-for-word accuracy review is not established by this check.")


if __name__ == "__main__":
    main()
