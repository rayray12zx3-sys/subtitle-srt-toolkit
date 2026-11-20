#!/usr/bin/env python3
"""Transcribe audio to UTF-8 SRT using faster-whisper, without uploading audio."""
import argparse
import re
from pathlib import Path

TERMINAL_PUNCT = '，。！？；：、,.!?;:'

def clean_text(text: str, minimal_punctuation: bool = True) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    if minimal_punctuation:
        text = text.strip(TERMINAL_PUNCT + ' ')
    return text

def srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remaining = divmod(milliseconds, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    secs, ms = divmod(remaining, 1_000)
    return f'{hours:02}:{minutes:02}:{secs:02},{ms:03}'

def group_words(words, max_chars: int, max_duration: float, gap: float):
    """Build subtitles while preserving every recognized word in order."""
    groups, current = [], []
    for item in words:
        token = item.word
        if not token.strip():
            continue
        if current:
            prev = current[-1]
            size = len(''.join(w.word for w in current) + token)
            if (size > max_chars or item.end - current[0].start > max_duration
                    or item.start - prev.end > gap):
                groups.append(current)
                current = []
        current.append(item)
    if current:
        groups.append(current)
    return groups

def write_srt(groups, output: Path, minimal_punctuation: bool):
    parts = []
    for group in groups:
        content = clean_text(''.join(x.word for x in group), minimal_punctuation)
        if content:
            parts.append(f'{len(parts)+1}\n{srt_time(group[0].start)} --> {srt_time(group[-1].end)}\n{content}\n')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(parts) + ('\n' if parts else ''), encoding='utf-8-sig')
    return len(parts)

def main():
    parser = argparse.ArgumentParser(description='Audio -> word-aligned SRT using faster-whisper')
    parser.add_argument('audio', type=Path)
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--model', default='large-v3')
    parser.add_argument('--language', default=None)
    parser.add_argument('--device', default='auto', choices=['auto','cpu','cuda'])
    parser.add_argument('--compute-type', default='default')
    parser.add_argument('--max-chars', type=int, default=22)
    parser.add_argument('--max-seconds', type=float, default=4.0)
    parser.add_argument('--max-gap', type=float, default=0.45)
    parser.add_argument('--keep-punctuation', action='store_true')
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error(f'File not found: {args.audio}')
    from faster_whisper import WhisperModel
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    segments, info = model.transcribe(str(args.audio), language=args.language,
                                      word_timestamps=True, vad_filter=True,
                                      beam_size=5, condition_on_previous_text=True)
    word_list = [word for segment in segments for word in (segment.words or [])]
    if not word_list:
        raise SystemExit('No recognized speech; no SRT was written')
    groups = group_words(word_list, args.max_chars, args.max_seconds, args.max_gap)
    path = args.output or args.audio.with_suffix('.srt')
    count = write_srt(groups, path, not args.keep_punctuation)
    print(f'Created {path} ({count} subtitles, detected language={info.language})')
    print('NOTE: Automatic recognition cannot guarantee character-level accuracy; manual audio verification is required.')

if __name__ == '__main__':
    main()
