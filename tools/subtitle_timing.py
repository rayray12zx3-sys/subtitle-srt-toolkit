"""Non-destructive display-timing adjustments only inside recognized speech gaps.

The original recognition time remains the source of truth; no invented word
timestamp or shifting of a spoken word's onset is performed.
"""
from __future__ import annotations
import math


def cue_windows(groups, audio_end=None, min_hold=.85, tail_limit=.28):
    if not 0.0 <= tail_limit <= .5 or not 0.0 < min_hold <= 3.0:
        raise ValueError("Invalid cue timing settings")
    if audio_end is not None and (not math.isfinite(audio_end) or audio_end <= 0):
        raise ValueError("Invalid audio duration")
    windows=[]
    for i, group in enumerate(groups):
        if not group:
            raise ValueError("Empty subtitle group")
        start=float(group[0].start)
        end=float(group[-1].end)
        if not all(math.isfinite(x) for x in (start,end)) or start<0 or end<=start:
            raise ValueError("Invalid source word alignment")
        if windows and start < windows[-1][1] - 1e-3:
            raise ValueError("Overlapping subtitle groups")
        next_start=float(groups[i+1][0].start) if i+1<len(groups) else audio_end
        limit=next_start if next_start is not None else end
        if audio_end is not None:
            limit=min(limit,audio_end)
        # Extend only into observed silence after speech. Never take time from
        # the next utterance, and never move the subtitle start earlier.
        free=max(0.0,limit-end)
        needed=max(0.0,min_hold-(end-start))
        tail=min(tail_limit,free,needed)
        windows.append((start,end+tail))
    return windows
