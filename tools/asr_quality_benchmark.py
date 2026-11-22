"""Private, reproducible mixed-language ASR benchmark.

Accepts private SRT or UTF-8 TXT on the assistant's private filesystem.
Only synthetic code/tests belong in this PUBLIC GitHub repository.

The AI-reference mode intentionally NEVER labels model agreement CER/WER or
a "winner". Human-verified mode requires caller-supplied explicit provenance;
the script cannot itself certify that a human listened to the audio.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from tools.text_review import read_srt_text

_HAN = re.compile(r"[\u3400-\u9fff]")
_LATIN = re.compile(r"[a-z]+(?:'[a-z]+)*|\d+")
_MIXED = re.compile(r"[\u3400-\u9fff]|[a-z]+(?:'[a-z]+)*|\d+")
_REPO_ROOT = Path(__file__).resolve().parents[1]
_MAX_TOKENS = 8000


def normalize(text: str, convert=None) -> str:
    if not isinstance(text, str):
        raise TypeError("Expected transcript text")
    normalized = unicodedata.normalize("NFKC", text)
    if convert is not None:
        normalized = convert(normalized)
    return normalized.replace("\u2019", "'").casefold()


def units(text: str, convert=None) -> dict[str, list[str]]:
    value = normalize(text, convert)
    result = {
        "han": _HAN.findall(value),
        "english": _LATIN.findall(value),
        "mixed": _MIXED.findall(value),
    }
    if any(len(items) > _MAX_TOKENS for items in result.values()):
        raise ValueError("Transcript too long for one exact benchmark; split into verified segments")
    return result


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    """Exact Levenshtein distance; no difflib ratio or model truth assumption."""
    if len(reference) > _MAX_TOKENS or len(hypothesis) > _MAX_TOKENS:
        raise ValueError("Too many transcript units")
    if len(hypothesis) > len(reference):
        reference, hypothesis = hypothesis, reference  # distance is symmetric
    prev = list(range(len(hypothesis) + 1))
    for i, token in enumerate(reference, 1):
        row = [i]
        for j, item in enumerate(hypothesis, 1):
            row.append(min(
                row[j - 1] + 1,       # insertion
                prev[j] + 1,          # deletion
                prev[j - 1] + (token != item),  # substitution
            ))
        prev = row
    return prev[-1]


def measure(reference: list[str], hypothesis: list[str]) -> dict:
    dist = edit_distance(reference, hypothesis)
    return {
        "reference_units": len(reference),
        "candidate_units": len(hypothesis),
        "edit_distance": dist,
        "difference_rate": round(dist / len(reference), 6) if reference else None,
    }


def compare(reference_text: str, candidate_text: str, *,
            reference_status: str, normalizer=None,
            max_disagreements: int = 15) -> dict:
    if reference_status not in ("ai-unverified", "human-verified"):
        raise ValueError("Reference status must be explicit")
    if not 0 <= max_disagreements <= 100:
        raise ValueError("Invalid maximum disagreement count")
    ref = units(reference_text, normalizer)
    hyp = units(candidate_text, normalizer)
    if not ref["mixed"] or not hyp["mixed"]:
        raise ValueError("Reference and candidate must contain recognized text")
    scores = {key: measure(ref[key], hyp[key])
              for key in ("han", "english", "mixed")}
    matching = difflib.SequenceMatcher(None, ref["mixed"], hyp["mixed"], autojunk=False)
    disagreements = []
    total_regions = 0
    for kind, a, b, c, d in matching.get_opcodes():
        if kind == "equal":
            continue
        total_regions += 1
        if len(disagreements) < max_disagreements:
            # These private content snippets are NEVER printed to GitHub logs.
            disagreements.append({
                "kind": kind,
                "reference_offset": a,
                "candidate_offset": c,
                "reference_units": ref["mixed"][a:b],
                "candidate_units": hyp["mixed"][c:d],
            })
    result = {
        "reference_status": reference_status,
        "status": ("HUMAN_REFERENCE_COMPARISON" if reference_status == "human-verified"
                   else "AI_REFERENCE_DISAGREEMENT_ONLY"),
        "normalization": "NFKC, Unicode apostrophes, casefold, ignore punctuation/spacing",
        "scores": scores,
        "disagreement_regions": total_regions,
        "review_items": disagreements,
        "review_items_truncated": total_regions > max_disagreements,
    }
    if reference_status == "human-verified":
        # Human-origin declaration must be checked out-of-band, not guessed.
        result["human_reference_rates"] = {
            "han_cer": scores["han"]["difference_rate"],
            "english_wer": scores["english"]["difference_rate"],
            "mixed_unit_error_rate": scores["mixed"]["difference_rate"],
        }
        result["notice"] = ("Rates reflect this declared human-verified reference only; "
                            "they do not prove audio listening or timestamp accuracy.")
    else:
        result["notice"] = (
            "These are exact edit-distance DISAGREEMENT RATES against an unverified "
            "AI reference, not CER/WER or evidence that either transcript is correct. "
            "Do not rank models as most accurate from this output."
        )
    return result


def read_private_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in (".txt", ".srt"):
        raise ValueError("Only private .srt or .txt references are supported")
    raw = path.read_text("utf-8-sig")
    # Some Google Drive connectors export actual .srt content with a .srt.txt
    # filename. Detect the numbered timecode header to avoid accidentally
    # including all timestamps/indices as "words" in the benchmark.
    is_srt = bool(re.match(
        r"\s*\d+\r?\n\d{2}:\d{2}:\d{2},\d{3} --> ", raw))
    if suffix == ".srt" or is_srt:
        return read_srt_text(path)
    return raw


def write_private_json(path: Path, result: dict, source_paths: list[Path]) -> None:
    dest = path.resolve()
    if dest == _REPO_ROOT or dest.is_relative_to(_REPO_ROOT):
        raise ValueError("Refusing to write private report under public repository")
    if dest in (p.resolve() for p in source_paths):
        raise ValueError("Refusing to overwrite input")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement, restrictive permissions even if reusing a report path.
    fd, pending = tempfile.mkstemp(prefix=".private-benchmark-", suffix=".json",
                                   dir=path.parent)
    try:
        os.chmod(pending, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
        os.replace(pending, path)
    finally:
        if os.path.exists(pending):
            os.unlink(pending)


def main() -> None:
    parser = argparse.ArgumentParser(description="Private mixed Chinese/English ASR comparison")
    parser.add_argument("--reference", type=Path, required=True,
                        help="Private human or AI reference in .srt/.txt; NEVER public")
    parser.add_argument("--reference-status", choices=("ai-unverified", "human-verified"),
                        required=True)
    parser.add_argument("--reference-origin", required=True,
                        help="Explicit provenance; do not imply human listening for AI reference")
    parser.add_argument("--candidate", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-disagreements", type=int, default=15)
    parser.add_argument("--han-conversion", choices=("opencc", "none"), default="opencc",
                        help="OpenCC s2t offline by default; 'none' explicitly skips "
                             "Chinese script conversion and may overstate mismatches")
    args = parser.parse_args()
    if not args.reference_origin.strip():
        parser.error("Reference provenance required")
    if args.han_conversion == "opencc":
        try:
            from opencc import OpenCC
        except ImportError:
            parser.error("Offline OpenCC package required: install requirements.txt "
                         "or explicitly use --han-conversion none")
        convert = OpenCC("s2t").convert
        conversion_label = "offline OpenCC s2t + Unicode NFKC, apostrophes, casefold"
    else:
        convert = None
        conversion_label = ("Unicode NFKC, apostrophes, casefold; NO Chinese script "
                            "conversion: Simplified/Traditional false differences possible")
    source_paths = [args.reference, *args.candidate]
    ref_text = read_private_text(args.reference)
    results = {}
    for candidate in args.candidate:
        if candidate == args.reference:
            raise ValueError("Candidate and reference must be different files")
        if candidate.name in results:
            raise ValueError("Duplicate candidate name")
        results[candidate.name] = compare(
            ref_text, read_private_text(candidate),
            reference_status=args.reference_status,
            normalizer=convert,
            max_disagreements=args.max_disagreements,
        )
    report = {
        "schema_version": 1,
        "status": ("HUMAN_REFERENCE_BENCHMARK" if args.reference_status == "human-verified"
                   else "AI_REFERENCE_DISAGREEMENT_ONLY"),
        "reference_status": args.reference_status,
        "reference_origin": args.reference_origin,
        "normalization": conversion_label + " + punctuation/whitespace ignored",
        "candidate_results": results,
        "privacy": "Private report, must never be committed to public GitHub",
    }
    write_private_json(args.output, report, source_paths)
    print("PRIVATE_ASR_BENCHMARK_WRITTEN: candidate_count=" + str(len(results)) +
          ", reference_status=" + args.reference_status +
          ", no transcript or discrepancies printed, no hosted inference")


if __name__ == "__main__":
    main()
