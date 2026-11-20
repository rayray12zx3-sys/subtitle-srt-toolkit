#!/usr/bin/env python3
"""Private token-level ASR comparison. Never uploads or automatically replaces subtitles.

Run outside public GitHub against private SRT and private Qwen transcript.
Differences are review candidates, NOT a verified error rate.
"""
import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path

TOKEN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*|[0-9]+|[\u3400-\u9fff]")
CUE = re.compile(r"^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n(.+)$", re.S)

def tokens(text):
    normalized = unicodedata.normalize("NFKC", text).replace("’", "'").casefold()
    return TOKEN.findall(normalized)

def read_srt_text(path):
    chunks = re.split(r"\n\s*\n", Path(path).read_text("utf-8-sig").replace("\r\n", "\n").strip())
    result = []
    for i, item in enumerate(chunks, 1):
        match = CUE.fullmatch(item)
        if not match:
            raise ValueError(f"Malformed SRT cue {i}")
        result.append(match.group(1).replace("\n", " "))
    if not result:
        raise ValueError("Empty SRT")
    return " ".join(result)

def compare(srt_text, second_text, max_items=100, normalizer=None):
    if normalizer is not None:
        srt_text = normalizer(srt_text)
        second_text = normalizer(second_text)
    first = tokens(srt_text)
    second = tokens(second_text)
    diff = []
    matcher = difflib.SequenceMatcher(None, first, second, autojunk=False)
    for op, i0, i1, j0, j1 in matcher.get_opcodes():
        if op != "equal":
            diff.append({
                "type": op,
                "srt_tokens": first[i0:i1],
                "second_tokens": second[j0:j1],
                "srt_token_offset": i0,
                "second_token_offset": j0,
            })
    return {
        "status": "REVIEW_REQUIRED_NOT_VERIFIED",
        "srt_tokens": len(first),
        "second_tokens": len(second),
        "candidate_disagreements": len(diff),
        "items": diff[:max_items],
        "truncated": len(diff) > max_items,
        "notice": "Differences are not truth labels. Simplified/Traditional conversion may create false mismatches."
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("srt", type=Path)
    p.add_argument("second_transcript", type=Path)
    p.add_argument("-o", "--output", required=True, type=Path)
    args = p.parse_args()
    try:
        from opencc import OpenCC
    except ImportError:
        converter = None
    else:
        converter = OpenCC("s2t").convert
    output = compare(read_srt_text(args.srt),
                     args.second_transcript.read_text("utf-8"),
                     normalizer=converter)
    output["hanzi_normalization"] = "OpenCC s2t" if converter else "unavailable: install requirements.txt"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PRIVATE_COMPARISON_WRITTEN: differences not auto-applied, no hosted AI inference")

if __name__ == "__main__":
    main()
