"""Privacy-preserving *human-attested* SRT reference review gate.

The repo contains only synthetic code. Private recording/transcript and audit
manifest must live OUTSIDE this public repository. This tool cannot listen to
audio, verify reviewer identity or independently prove audio accuracy.

prepare: scaffold all cues as UNREVIEWED, never auto-verified.
finalize: require audio/source hashes, explicit listening attestation and per-cue
          confirmations before creating gold text or cue-timestamp reference.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

from tools.asr_quality_benchmark import compare, read_private_text

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_SCHEMA = "subtitle-srt-human-review-v1"
ATTESTATION = ("I personally listened to the private source audio and verified "
               "the marked transcript and time boundaries.")
_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")
_ARROW = re.compile(
    r"^(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})$")
_MAX_CUES = 4000


def timestamp_ms(value: str) -> int:
    matched = _TS.fullmatch(value)
    if not matched:
        raise ValueError("Invalid SRT time format")
    hours, minutes, seconds, milliseconds = (int(n) for n in matched.groups())
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Invalid SRT time value")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def ms_timestamp(value: int) -> str:
    if type(value) is not int or value < 0:
        raise ValueError("Negative or non-integer SRT timing")
    h, rem = divmod(value, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_srt(content: str, *, duration_ms: int | None = None) -> list[dict]:
    blocks = re.split(r"\n[ \t]*\n", content.lstrip("\ufeff").replace("\r\n", "\n").strip())
    if not blocks or not blocks[0].strip():
        raise ValueError("Empty SRT")
    if len(blocks) > _MAX_CUES:
        raise ValueError("Excessive cue count")
    cues = []
    prev_end = 0
    for number, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if len(lines) < 3 or lines[0].strip() != str(number):
            raise ValueError("Noncontiguous cue numbers or empty cue")
        match = _ARROW.fullmatch(lines[1].strip())
        if match is None:
            raise ValueError("Malformed cue timing")
        start, end = (timestamp_ms(t) for t in match.groups())
        if start < prev_end or end <= start:
            raise ValueError("Overlapping or nonpositive cue time")
        if duration_ms is not None and end > duration_ms + 100:
            raise ValueError("Cue extends beyond actual source audio")
        text = "\n".join(lines[2:]).strip()
        if not text or len(text) > 5000 or any("\x00" in line for line in lines):
            raise ValueError("Empty or invalid recognized text")
        cues.append({"n": number, "start_ms": start, "end_ms": end, "text": text})
        prev_end = end
    return cues


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audio_duration_ms(path: Path) -> int:
    # Handles floating-point WAV; stdlib wave only handles integer PCM WAV.
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    seconds = float(result.stdout.strip())
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Unusable source audio duration")
    return round(seconds * 1000)


def _safe_private(path: Path, sources=()) -> Path:
    absolute = path.expanduser().resolve()
    if absolute == REPO_ROOT or absolute.is_relative_to(REPO_ROOT):
        raise ValueError("Private review content must not enter the public GitHub repo")
    if any(absolute == p.expanduser().resolve() for p in sources):
        raise ValueError("Output cannot overwrite private input")
    return absolute


def _atomic_private_write(path: Path, content: str, sources=()) -> None:
    dest = _safe_private(path, sources)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".human-review-", dir=dest.parent)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(content)
        os.replace(temporary, dest)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare_manifest(audio: Path, source_srt: Path) -> dict:
    duration = audio_duration_ms(audio)
    original = parse_srt(source_srt.read_text("utf-8-sig"), duration_ms=duration)
    return {
        "schema": REVIEW_SCHEMA,
        "status": "DRAFT_AWAITING_HUMAN_LISTENING",
        "audio": {"sha256": sha256(audio), "duration_ms": duration},
        "source_srt_sha256": sha256(source_srt),
        "reviewer_id": "",
        "review_completed_utc": "",
        "listening_attestation": "",
        "cues": [{
            "n": cue["n"],
            "draft_text": cue["text"],
            "draft_start_ms": cue["start_ms"],
            "draft_end_ms": cue["end_ms"],
            "corrected_text": cue["text"],
            "corrected_start_ms": cue["start_ms"],
            "corrected_end_ms": cue["end_ms"],
            "text_listened": False,
            "time_listened": False,
            "notes": "",
        } for cue in original],
    }


def _iso_utc(value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing human review completion date")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid human review date") from exc
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError("Human review completion date must include UTC timezone")


def review_status(manifest: dict, audio: Path, source_srt: Path) -> dict:
    """Validate provenance; NEVER infer that a human actually listened."""
    if manifest.get("schema") != REVIEW_SCHEMA:
        raise ValueError("Unsupported review manifest schema")
    actual_audio_hash = sha256(audio)
    actual_srt_hash = sha256(source_srt)
    if manifest.get("audio", {}).get("sha256") != actual_audio_hash:
        raise ValueError("Review does not match source recording")
    if manifest.get("source_srt_sha256") != actual_srt_hash:
        raise ValueError("Review does not match source SRT")
    duration = audio_duration_ms(audio)
    if abs(manifest.get("audio", {}).get("duration_ms", -10000) - duration) > 1:
        raise ValueError("Review does not match source duration")
    original = parse_srt(source_srt.read_text("utf-8-sig"), duration_ms=duration)
    entries = manifest.get("cues")
    if not isinstance(entries, list) or len(entries) != len(original):
        raise ValueError("Review cue count differs from source")
    text_flags = 0
    time_flags = 0
    corrected = []
    prev_end = 0
    for source, entry in zip(original, entries):
        if (type(entry) is not dict or entry.get("n") != source["n"]
                or entry.get("draft_text") != source["text"]
                or entry.get("draft_start_ms") != source["start_ms"]
                or entry.get("draft_end_ms") != source["end_ms"]):
            raise ValueError("Review source cue metadata changed")
        text = entry.get("corrected_text")
        start, end = entry.get("corrected_start_ms"), entry.get("corrected_end_ms")
        if (not isinstance(text, str) or not text.strip() or len(text) > 5000
                or "\x00" in text or "\n\n" in text):
            raise ValueError("Invalid corrected text")
        if type(start) is not int or type(end) is not int:
            raise ValueError("Timing must be an integer number of milliseconds")
        if start < prev_end or end <= start or end > duration + 100:
            raise ValueError("Invalid edited cue timing or overlap")
        if type(entry.get("text_listened")) is not bool or type(entry.get("time_listened")) is not bool:
            raise ValueError("Review flags must be explicit booleans")
        text_flags += int(entry["text_listened"])
        time_flags += int(entry["time_listened"])
        corrected.append({"n": source["n"], "text": text.strip(),
                          "start_ms": start, "end_ms": end})
        prev_end = end
    return {
        "status": "DRAFT_AWAITING_HUMAN_LISTENING",
        "count": len(original),
        "text_confirmed": text_flags,
        "timing_confirmed": time_flags,
        "text_ready": text_flags == len(original),
        "timing_ready": time_flags == len(original),
        "corrected": corrected,
    }


def _check_human_attestation(manifest: dict) -> None:
    reviewer = manifest.get("reviewer_id")
    if not isinstance(reviewer, str) or len(reviewer.strip()) < 2:
        raise ValueError("Human reviewer name or pseudonym required")
    _iso_utc(manifest.get("review_completed_utc"))
    if manifest.get("listening_attestation") != ATTESTATION:
        raise ValueError("Reviewer must explicitly attest to listening to original audio")


def finalize(manifest: dict, audio: Path, source_srt: Path, *,
             text_only: bool = False) -> tuple[str, dict]:
    status = review_status(manifest, audio, source_srt)
    if not status["text_ready"]:
        raise ValueError("Human transcript is not fully listened to and confirmed")
    if not text_only and not status["timing_ready"]:
        raise ValueError("Human cue timing is not fully listened to and confirmed")
    _check_human_attestation(manifest)
    edited = status["corrected"]
    if text_only:
        result = " ".join(cue["text"].replace("\n", " ") for cue in edited) + "\n"
    else:
        result = "\n\n".join(
            f'{cue["n"]}\n{ms_timestamp(cue["start_ms"])} --> '
            f'{ms_timestamp(cue["end_ms"])}\n{cue["text"]}'
            for cue in edited
        ) + "\n"
    report = {
        "schema": REVIEW_SCHEMA,
        "status": ("HUMAN_SELF_ATTESTED_TEXT_AND_CUE_TIMING"
                   if not text_only else "HUMAN_SELF_ATTESTED_TEXT_ONLY"),
        "claim": "Self-attested source listening, NOT independently verified by software",
        "audio_sha256": sha256(audio),
        "source_srt_sha256": sha256(source_srt),
        "reviewer_id": manifest["reviewer_id"].strip(),
        "review_completed_utc": manifest["review_completed_utc"],
        "cues": len(edited),
        "text_reviewed": status["text_confirmed"],
        "time_reviewed": status["timing_confirmed"],
        "word_timestamp_accuracy": "NOT_MEASURED",
    }
    return result, report


def cue_time_disagreement(gold_srt: str, candidate_srt: str) -> dict:
    """Cue boundary disagreement, ONLY if segmentation and lexical text match.

    If a candidate uses 22 vs 24 cues, no honest one-to-one cue timing score
    exists. Reject the measurement rather than match cues by row index.
    """
    reference = parse_srt(gold_srt)
    candidate = parse_srt(candidate_srt)
    if len(reference) != len(candidate):
        return {"status": "NOT_COMPARABLE_SEGMENTATION",
                "reference_cues": len(reference), "candidate_cues": len(candidate)}
    for ref, cand in zip(reference, candidate):
        a = re.sub(r"\W+", "", ref["text"], flags=re.UNICODE).casefold()
        b = re.sub(r"\W+", "", cand["text"], flags=re.UNICODE).casefold()
        if a != b:
            return {"status": "NOT_COMPARABLE_TRANSCRIPT_OR_SEGMENTATION",
                    "reference_cues": len(reference), "candidate_cues": len(candidate)}
    values = [abs(ref[endpoint] - cand[endpoint])
              for ref, cand in zip(reference, candidate)
              for endpoint in ("start_ms", "end_ms")]
    ordered = sorted(values)
    return {"status": "CUE_BOUNDARY_DISAGREEMENT_ONLY",
            "samples": len(values),
            "median_ms": statistics.median(ordered),
            "p95_ms": ordered[max(0, math.ceil(.95 * len(ordered)) - 1)],
            "max_ms": ordered[-1],
            "note": "Human-corrected cue boundaries, not word-level alignment accuracy"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline private human listening review")
    sub = parser.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("prepare", help="Create an entirely UNREVIEWED private manifest")
    check = sub.add_parser("check", help="Report progress without inventing human reference")
    finish = sub.add_parser("finalize", help="Export only after all required review flags")
    for p in (prepare, check, finish):
        p.add_argument("--audio", required=True, type=Path)
        p.add_argument("--source-srt", required=True, type=Path)
    prepare.add_argument("--out", required=True, type=Path)
    for p in (check, finish):
        p.add_argument("--review", required=True, type=Path)
    finish.add_argument("--out", required=True, type=Path)
    finish.add_argument("--audit-out", required=True, type=Path)
    finish.add_argument("--text-only", action="store_true")
    args = parser.parse_args()
    paths = (args.audio, args.source_srt)
    if args.action == "prepare":
        manifest = prepare_manifest(*paths)
        _atomic_private_write(args.out, json.dumps(manifest, ensure_ascii=False, indent=2), paths)
        print(f"REVIEW_DRAFT_CREATED: cues={len(manifest['cues'])}; verified=0; "
              "human gold CER/WER=NOT_AVAILABLE")
        return
    review = json.loads(args.review.read_text("utf-8-sig"))
    if args.action == "check":
        x = review_status(review, *paths)
        print(f"REVIEW_PENDING: total={x['count']}; text_checked={x['text_confirmed']}; "
              f"timing_checked={x['timing_confirmed']}; "
              "human listening not independently established")
        return
    raw, audit = finalize(review, *paths, text_only=args.text_only)
    if args.out == args.audit_out:
        raise ValueError("Audit and reference files must be different")
    _atomic_private_write(args.out, raw, [*paths, args.review, args.audit_out])
    _atomic_private_write(args.audit_out, json.dumps(audit, ensure_ascii=False, indent=2),
                          [*paths, args.review, args.out])
    print(f"PRIVATE_SELF_ATTESTED_REFERENCE_WRITTEN: cues={audit['cues']}; "
          "reference private; word-level time accuracy NOT measured")


if __name__ == "__main__":
    main()
