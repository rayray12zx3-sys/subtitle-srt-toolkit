"""Validate a private Premiere Pro SRT and optionally record human self-attestation.

Unlike the legacy 1:1 cue HTML reviewer, this accepts changed cue segmentation.
All real media, edited SRTs, reviewer identity and audit JSON stay OUTSIDE the
public GitHub repository. A valid SRT alone is never human accuracy evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.gold_reference_review import (
    REVIEW_SCHEMA, _atomic_private_write, _iso_utc, _safe_private,
    audio_duration_ms, parse_srt, sha256,
)

PENDING = "PREMIERE_EDITED_REFERENCE_PENDING_LISTENING_ATTESTATION"


def check_edited_srt(audio: Path, source_srt: Path, edited_srt: Path) -> dict:
    """Check source/edited SRTs against real audio, without attesting to listening."""
    audio, source_srt, edited_srt = map(Path, (audio, source_srt, edited_srt))
    if edited_srt.resolve() == source_srt.resolve():
        raise ValueError("Edited SRT must be separate from the original source")
    for path in (audio, source_srt, edited_srt):
        _safe_private(path)
    duration_ms = audio_duration_ms(audio)
    source = parse_srt(source_srt.read_text("utf-8-sig"), duration_ms=duration_ms)
    edited = parse_srt(edited_srt.read_text("utf-8-sig"), duration_ms=duration_ms)
    return {
        "status": PENDING,
        "source_cues": len(source),
        "edited_cues": len(edited),
        "duration_ms": duration_ms,
        "last_end_ms": edited[-1]["end_ms"],
        "transcript_human_listening": "NOT_ATTESTED",
        "cue_time_human_listening": "NOT_ATTESTED",
        "word_timestamp_accuracy": "NOT_MEASURED",
    }


def attest_edited_srt(audio: Path, source_srt: Path, edited_srt: Path, *,
                      reviewer_id: str, completed_utc: str,
                      confirm_full_listening: bool) -> dict:
    """Bind the existing editor export to an explicit ALL-cue human attestation.

    The reviewer must personally affirm having listened to and checked ALL
    corrected words and ALL cue timing boundaries. This is a self-attestation,
    never independent proof of what a person heard.
    """
    status = check_edited_srt(audio, source_srt, edited_srt)
    if confirm_full_listening is not True:
        raise ValueError("Explicit full-recording listening attestation required")
    if not isinstance(reviewer_id, str) or len(reviewer_id.strip()) < 2:
        raise ValueError("Reviewer name or pseudonym must be at least two characters")
    _iso_utc(completed_utc)
    return {
        "schema": REVIEW_SCHEMA,
        "status": "HUMAN_SELF_ATTESTED_TEXT_AND_CUE_TIMING",
        "review_method": "PREMIERE_PRO_EXPORTED_SRT_FULL_LISTENING_ATTESTATION",
        "claim": ("Reviewer self-attests source listening and checking all "
                  "edited text/timing; software cannot independently verify hearing"),
        "audio_sha256": sha256(Path(audio)),
        "source_srt_sha256": sha256(Path(source_srt)),
        "gold_sha256": sha256(Path(edited_srt)),
        "reviewer_id": reviewer_id.strip(),
        "review_completed_utc": completed_utc,
        "cues": status["edited_cues"],
        "text_reviewed": status["edited_cues"],
        "time_reviewed": status["edited_cues"],
        "word_timestamp_accuracy": "NOT_MEASURED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Private Premiere SRT structural check / optional human audit")
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser("check", help="Validate only; NEVER promote to human gold")
    attest = sub.add_parser("attest", help="Record an editor's explicit all-cue listening")
    for cmd in (check, attest):
        cmd.add_argument("--audio", type=Path, required=True)
        cmd.add_argument("--source-srt", type=Path, required=True)
        cmd.add_argument("--edited-srt", type=Path, required=True)
    attest.add_argument("--reviewer", required=True,
                        help="Human reviewer name or pseudonym; remains private")
    attest.add_argument("--completed-utc", required=True,
                        help="UTC time with Z or +00:00 offset")
    attest.add_argument("--confirm-full-listening", action="store_true",
                        help="Human explicitly confirms ALL text and timing heard")
    attest.add_argument("--audit-out", type=Path, required=True,
                        help="Private JSON audit; never place in public GitHub")
    args = parser.parse_args()
    if args.action == "check":
        data = check_edited_srt(args.audio, args.source_srt, args.edited_srt)
        print("PREMIERE_EDITED_REFERENCE_PENDING_LISTENING_ATTESTATION: "
              f"source={data['source_cues']} cues; edited={data['edited_cues']} cues; "
              "SRT structure valid; no human listening inferred")
        return 0
    audit = attest_edited_srt(
        args.audio, args.source_srt, args.edited_srt,
        reviewer_id=args.reviewer, completed_utc=args.completed_utc,
        confirm_full_listening=args.confirm_full_listening,
    )
    _atomic_private_write(
        args.audit_out, json.dumps(audit, ensure_ascii=False, indent=2),
        [args.audio, args.source_srt, args.edited_srt],
    )
    print("PRIVATE_PREMIERE_SELF_ATTESTED_AUDIT_WRITTEN: "
          f"edited={audit['cues']} cues; all-cue self-attestation only; "
          "word-level timing NOT measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
