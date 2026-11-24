"""Bounded-memory, silence-seeking PCM-WAV splits for GitHub-hosted ASR.

This module does NOT run audio inference or write personal content to public logs.
A non-overlapping split guarantees exactly one copy of each source sample.
At a hard cut without silence, speech may be interrupted: not human QA.
"""
from __future__ import annotations

import array
import math
from pathlib import Path
import sys
import wave
from collections.abc import Iterator


class ChunkingError(ValueError):
    pass


def _quiet_cut(
    source: wave.Wave_read, desired: int, start: int, total: int, rate: int,
    search_seconds: float
) -> int:
    """Prefer lowest short-window RMS near intended boundary, or hard cut."""
    search = min(int(search_seconds * rate), int(rate * 3))
    low = max(start + rate, desired - search)
    high = min(total - rate, desired + search)
    if high <= low:
        return desired
    frame = max(1, int(rate * .08))
    hop = max(1, int(rate * .05))
    best = None
    for pos in range(low, high, hop):
        source.setpos(pos)
        raw = source.readframes(frame)
        values = array.array("h")
        values.frombytes(raw)
        if sys.byteorder != "little":
            values.byteswap()
        if not values:
            continue
        mean_square = sum(x * x for x in values) / len(values)
        score = math.sqrt(mean_square)
        if best is None or score < best[0]:
            best = (score, pos)
    # Silence threshold is only a hint; speech without silence uses hard cut.
    return best[1] if best and best[0] < 750 else desired


def split_pcm_wav(audio: Path, destination: Path, chunk_seconds: int,
                  search_seconds: float = 2.0) -> list[tuple[Path, float, float]]:
    return list(iter_pcm_chunks(audio, destination, chunk_seconds, search_seconds))


def iter_pcm_chunks(audio: Path, destination: Path, chunk_seconds: int,
                    search_seconds: float = 2.0) -> Iterator[tuple[Path, float, float]]:
    if chunk_seconds < 2 or chunk_seconds > 3600:
        raise ChunkingError("Chunk length must be between 2 and 3600 seconds")
    destination.mkdir(parents=True, exist_ok=True)
    with wave.open(str(audio), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        total = source.getnframes()
        if channels != 1 or width != 2 or not rate or total == 0 or source.getcomptype() != "NONE":
            raise ChunkingError("Chunking requires nonempty mono 16-bit PCM WAV")
        chunk_frames = chunk_seconds * rate
        start = 0
        index = 0
        while start < total:
            desired = min(start + chunk_frames, total)
            end = desired if desired == total else _quiet_cut(
                source, desired, start, total, rate, search_seconds
            )
            if not start < end <= total:
                raise ChunkingError("Invalid segmentation boundary")
            path = destination / f"chunk_{index:04d}.wav"
            source.setpos(start)
            with wave.open(str(path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(rate)
                frames_remaining = end - start
                while frames_remaining:
                    n = min(32000, frames_remaining)
                    raw = source.readframes(n)
                    if len(raw) != n * 2:
                        raise ChunkingError("Incomplete PCM source")
                    target.writeframesraw(raw)
                    frames_remaining -= n
            yield path, start / rate, (end - start) / rate
            index += 1
            start = end
