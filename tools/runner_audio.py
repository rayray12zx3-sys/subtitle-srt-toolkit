"""Normalize authenticated Ogg Opus to mono PCM WAV without system FFmpeg.

PyAV's Linux binary wheel bundles the required libav libraries. Stream frames
to disk so long recordings do not require a full decoded array in memory.
Never print decoded media or exception payloads to public job logs.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import tempfile
import wave


class AudioNormalizationError(ValueError):
    pass


def normalize_opus_bytes(payload: bytes, output: Path) -> int:
    """Write a fresh mono 16-bit 16 kHz WAV, returning the exact sample count."""
    import av

    output = Path(output)
    if output.exists():
        raise FileExistsError("Refusing to replace existing normalized audio")
    if not payload.startswith(b"OggS"):
        raise AudioNormalizationError("Expected authenticated Ogg Opus input")
    fd, name = tempfile.mkstemp(prefix=".pcm-", suffix=".wav", dir=output.parent)
    os.close(fd)
    pending = Path(name)
    samples = 0
    try:
        with av.open(io.BytesIO(payload), mode="r", format="ogg") as source:
            if len(source.streams.audio) != 1:
                raise AudioNormalizationError("Expected one audio stream")
            stream = source.streams.audio[0]
            if stream.codec_context.name not in ("opus", "libopus"):
                raise AudioNormalizationError("Expected Opus audio codec")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            with wave.open(str(pending), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)

                def write_frames(frames):
                    nonlocal samples
                    for frame in frames:
                        raw = frame.to_ndarray().astype("<i2", copy=False).tobytes()
                        if len(raw) != frame.samples * 2:
                            raise AudioNormalizationError("Unexpected PCM frame shape")
                        wav.writeframesraw(raw)
                        samples += frame.samples

                for frame in source.decode(stream):
                    # Concatenate decoded samples; avoid resampler PTS restrictions.
                    frame.pts = None
                    write_frames(resampler.resample(frame))
                write_frames(resampler.resample(None))
        if samples <= 0:
            raise AudioNormalizationError("No decoded audio samples")
        with wave.open(str(pending), "rb") as check:
            if (check.getnchannels(), check.getsampwidth(), check.getframerate(),
                    check.getnframes(), check.getcomptype()) != (1, 2, 16000, samples, "NONE"):
                raise AudioNormalizationError("Normalized WAV validation failed")
        os.replace(pending, output)
        return samples
    except AudioNormalizationError:
        raise
    except Exception:
        raise AudioNormalizationError("Ogg Opus normalization failed") from None
    finally:
        pending.unlink(missing_ok=True)
