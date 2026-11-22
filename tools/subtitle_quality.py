"""Automatic aggregate subtitle quality diagnostics (no plaintext log output).

Structural validation lives in delivery_gate.py. These are probabilistic
readability/format checks, not human-ground-truth WER or exact sync scores.
"""
from __future__ import annotations
import re
from pathlib import Path
from delivery_gate import timestamp_ms
from tools.smart_segmentation import visual_width, reading_units, suspicious_english_glue


def analyze_srt(path: Path, line_chars=12, max_lines=2, rate_limit=8.0):
    if line_chars<1 or max_lines not in (1,2) or rate_limit<=0:
        raise ValueError("Invalid quality limits")
    raw=Path(path).read_text("utf-8-sig").replace("\r\n","\n").strip()
    blocks=re.split(r"\n\s*\n",raw) if raw else []
    counts={"cues":0,"multi_line":0,"too_many_lines":0,"too_wide":0,
            "too_brief":0,"reading_too_fast":0,"high_rate":0.,
            "split_contractions":0,"glued_english_sentences":0,
            "joined_english_words":0,
            "max_width":0,"max_lines":max_lines}
    for block in blocks:
        bits=block.splitlines()
        if len(bits)<3:raise ValueError("Malformed SRT in quality analysis")
        start,end=bits[1].split(" --> ")
        dur=(timestamp_ms(end)-timestamp_ms(start))/1000.
        if dur<=0:raise ValueError("Invalid SRT cue duration")
        lines=bits[2:]
        display_text="\n".join(lines)
        counts["split_contractions"]+=int(bool(re.search(
            r"[A-Za-z]\n['’](?:s|re|ve|ll|d|m|t)\b", display_text,
            flags=re.IGNORECASE)))
        counts["glued_english_sentences"]+=int(bool(re.search(
            r"(?<=[A-Za-z][.!?])(?=[A-Za-z])", display_text)))
        counts["joined_english_words"]+=int(bool(suspicious_english_glue(display_text)))
        counts["cues"]+=1
        counts["multi_line"]+=int(len(lines)>1)
        counts["too_many_lines"]+=int(len(lines)>max_lines)
        widths=[visual_width(line) for line in lines]
        counts["max_width"]=max(counts["max_width"],max(widths))
        counts["too_wide"]+=int(any(w>2*line_chars+2 for w in widths))
        counts["too_brief"]+=int(dur<.70)
        rate=reading_units(" ".join(lines))/dur
        counts["high_rate"]=round(max(counts["high_rate"],rate),2)
        counts["reading_too_fast"]+=int(rate>rate_limit)
    counts["layout_ok"]=(counts["too_many_lines"]==0 and counts["too_wide"]==0
                         and counts["split_contractions"]==0
                         and counts["glued_english_sentences"]==0
                         and counts["joined_english_words"]==0)
    # Overspeed/short cues can be caused by genuinely fast speech; warn,
    # don't silently delete, rewrite or assert a proven accuracy outcome.
    return counts
