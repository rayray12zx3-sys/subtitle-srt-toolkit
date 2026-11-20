# Subtitle model evaluation — metadata-only evidence

Verified 2026-11-20 on **standard GitHub-hosted Ubuntu CPU runners** using static open-source weights; no paid or finite-free-tier AI inference service was used. **No personal audio, plaintext transcripts, SRT or private media fingerprints are stored here.** Aggregate measures are not word-error-rate ground truth.

## Actual private-audio test summary

| Engine | Product produced | Cue count | Model download | ASR/text generation | Execution | Evidence |
|---|---|---:|---:|---:|---|---|
| faster-whisper Small | SRT | 32 | not separately recorded | not separately recorded | PASS | [Run 44699772481](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44699772481) |
| faster-whisper Large-v3 Turbo | SRT | 31 | 7.28s | 40.21s | PASS | [Run 44727437501](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44727437501) |
| Qwen3-ASR 0.6B C/CPU | encrypted text **only** | not applicable | 8.23s | 25.30s | PASS | [Run 44729262014](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44729262014) |
| Qwen3-ASR 1.7B C/CPU | real audio not yet tested | not applicable | not measured on real audio | not measured | SYNTHETIC PASS ONLY | [Run 44729975533](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44729975533) |

**Synthetic feasibility test:** Qwen3 0.6B CPU 2.73s / 2,719,744 KiB peak RSS; Qwen3 1.7B CPU 5.19s / 6,792,800 KiB peak RSS; different synthetic run stages are comparable only as resource checks. Note: Qwen3 produces plain text, not genuine word-aligned SRT in these tests.

## Private comparative notes, without source content

- Compared with the previous AI Studio recognition reference (which is **not** a human-verified ground truth), Small has normalized text similarity ~98.65%, Large-v3 Turbo ~98.75%. Neither number is CER/WER or a verified accuracy score.
- Turbo corrects one apparent word recognition anomaly from Small, but omits a few short spoken particles compared to the reference; no unambiguous overall precision winner established.
- Qwen3-ASR 0.6B gives fluent mixed-language text and is faster in the isolated *text-generation* phase, but sometimes changes wording and outputs Simplified Chinese. It **does not provide validated subtitle timestamps in the current private benchmark**.
- Qwen3-ASR 1.7B fits in the standard runner for synthetic speech, but no real mixed-language quality evidence yet. Forced alignment is also unverified on this environment.

## Current provisional production combination

1. **Default SRT generator:** faster-whisper **Large-v3 Turbo** (real private-media SRT generation and structural validity verified), with **Small** retained as an explicitly selectable fallback.
2. **Optional private second-opinion engine:** Qwen3-ASR **0.6B** for detecting disagreement. Run `python -m tools.text_review RAW.srt QWEN.txt -o PRIVATE_REPORT.json` outside the public repository. The reviewer outputs candidate differences **without automatically changing words or timestamps**.
3. Do not enable Qwen3 1.7B or Qwen ForcedAligner in production until a real mixed-language benchmark and true timestamp validation show value that justifies CPU time and memory.
4. Actual word-for-word quality requires listening to real audio; cross-ASR agreement alone cannot establish accuracy.

## Acceptance gates for future upgrades

- Real-source SRT created, validated against its audio, privately delivered to chat — **not only a synthetic test**.
- Keep source audio and subtitles out of public repo/artifacts/logs; temporary ciphertext must be deleted after use.
- Document download, compute time, and memory if measured, plus differences from the prior successful baseline.
- Never consume finite free inference APIs or switch to self-hosted/Windows compute without new explicit authorization.

## 2026-11-20 — subsequent candidate verification: Breeze and FireRed

- **Breeze-ASR-25 synthetic GitHub-hosted CPU SRT: PASS** [run 44739937998](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44739937998): 6.236s synthetic Chinese/English source, 3 valid cues, download 10.27s, CPU inference and output 16.01s, max RSS 2,311,012 KiB; community CT2 conversion revision `70660216b01a6f6b7b8c5690767a4763df61755f`.
- **Breeze-ASR-25 REAL private-audio SRT: PASS** [run 44745387647](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44745387647): actual 58.191s mixed-language recording, 33 cues, model download 17.61s, inference/output 59.31s, authenticated AES-GCM encrypted return decrypted privately and validated against the original recording. The SRT resides ONLY in the owner's private Google Drive; not in GitHub.
- Compared against *non-human-verified* old Google AI recognition, Breeze normalized text similarity 98.97%, versus Turbo 98.75% and Small 98.65%. **These are AI-to-AI agreement indicators, NOT CER/WER or verified accuracy.** Breeze disagrees on a few short particles, and both models confuse at least one phrase; no proven accuracy winner. Breeze ran slower than Turbo (59.31s vs 40.21s in differently measured inference/output paths). No production switch.
- **FireRedASR2-AED synthetic CPU inference: PASS** [run 44740104063](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44740104063): two synthetic utterances (Mandarin, English), 13 timestamp items, official model revision `2304afed56eacfee6256dee5937ed22ffa0b64ec`, weight download 31.72s, model load 8.47s, ASR 11.18s, process peak RSS 9,537,780 KiB. **Real private-audio SRT and alignment not yet verified**. The official repo's requirements request CUDA-specific PyTorch; our synthetic test pinned CPU-only torch to avoid a GPU runner.
- First Breeze private dispatch failed because UI truncated a 392-character RSA output public key ([run 44744996031](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44744996031)); fixed by adding compact `rsa-n:` output-key support in cloud handshake, then real production run PASS. Failure occurred before reading audio. Note this UI fragility for future automation.
- Private historical comparisons and newly delivered Breeze SRT live in the **existing private Google Drive folder** `字幕模型評估｜subtitle-srt-toolkit`, with one fixed main report `00_模型測試結果_固定主檔.md` updated in-place; folder URL intentionally not committed to public repository.
- Keep production default Large-v3 Turbo, Small fallback, Qwen 0.6B as optional second-opinion; Breeze is an opt-in evaluated candidate using a third-party CTranslate2 conversion whose provenance/license needs additional verification before company use. FireRed is synthetic feasibility only. Do not claim either has established human-verified transcription accuracy.
