# Subtitle delivery acceptance gate

## Mandatory contract (confirmed 2026-11-20)

**NO VERIFIED SRT DELIVERED, NO COMPLETED SUBTITLE TASK.**

1. The requested audio must actually be processed through an authorized, local/offline transcription engine. A previous SRT cannot stand in for a new offline run.
2. The engine must produce a fresh, nonempty `.srt` file. `transcribe.py` writes a pending file and commits the final output only after the delivery gate passes.
3. `delivery_gate.py` checks the source recording exists, subtitle numbering, timestamp syntax, nonblank content, monotonic nonoverlapping timing, and end-times within the audio duration.
4. Validation results explicitly say `OUTPUT_VALIDATED_NOT_YET_DELIVERED`. They **do not** say `COMPLETED`.
5. The executor must deliver an actual accessible SRT attachment/link to the requester through this conversation or an explicitly authorized private channel. Only then can the subtitle task be marked `COMPLETED`.
6. If any item is missing, retain `BLOCKED` / `INCOMPLETE` status in HANDOFF. Never treat unit test success, model startup, code commits, a plain transcript, placeholders, prior subtitles or progress messages as satisfying delivery.
7. Avoid claiming word-for-word verification unless someone actually listened to and checked the recording. Structural SRT validation alone cannot certify transcription accuracy.

## Cost and privacy constraints

- No limited free-tier AI inference quota, paid inference, hosted transcription API, or Google AI Studio for subtitle generation.
- No automatic model downloads or cloud fallback during transcription.
- The public GitHub repository contains tools, docs and synthetic tests **only**. Never publish user audio, SRT, transcripts, hashes of real user media, or delivery receipts.
- GitHub Actions code-only CI **does not** count as completed audio-to-SRT processing.

## Manual validation

```bash
python delivery_gate.py "recording.wav" "recording.srt"
```

Exit code 1 and `BLOCKED` indicate an invalid or missing artifact. Exit code 0 indicates only that the SRT structure and timing are valid against the audio; delivery still must be verified.

## Important boundary

A hard delivery contract cannot make a missing offline model, an unavailable computer, or a broken transfer channel functional. Keep the specific task open/blocked, preserve its handoff pointer, and accurately report the prerequisite instead of falsely marking it completed.
