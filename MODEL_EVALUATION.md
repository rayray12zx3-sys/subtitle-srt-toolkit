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

## 2026-11-20 — FireRedASR2-AED real private audio evaluation COMPLETE

- **Full actual-source SRT PASS:** [GitHub-hosted standard CPU run 44752794627](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44752794627) processed the existing 58.191s private Mandarin/English audio in five chunks and generated **24 SRT cues**. GitHub's `delivery_gate` passed. The encrypted result was decrypted in the chat execution workspace, validated independently for ordered, nonoverlapping, in-range SRT timestamps, and delivered privately; **not committed or uploaded as public artifacts/log content**. Last cue ends at 58.165s.
- Resource metrics from the actual run: 17.27s static weights download, 9.11s model load, 141.74s five-segment inference, runner process wall 297.31s (includes temporary audio/key transfer waiting); peak resident memory 9,626,000 KiB (~9.18 GiB). CPU inference is slower than the existing Turbo 40.21s model stage, but different pipeline choices restrict direct speed conclusions.
- Private text comparison against previous *unverified AI Studio AI transcript*, after punctuation/case and partial Traditional/Simplified normalization, yielded **FireRed 96.80%**, Small 98.65%, Turbo 98.75%, Breeze 98.97%. **This is NOT word error rate or verified accuracy.** FireRed shows duplicated phrases and awkward subtitle segmentation; no demonstrated quality improvement. No human listening-based word-for-word correction is claimed.
- First real-media test [run 44751494953](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44751494953) performed real inference but failed at SRT assembly due to summing timestamp lists rather than chunk durations. The bug was fixed in [commit 687fc66a](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/commit/687fc66aee35e1e171b54c641863ee49862fccce); **second run passed and actually produced an SRT**. Failed attempt is recorded, not hidden.
- The private resulting `07_FireRedASR2-AED.srt` is stored in the existing owner-only Google Drive subtitle-evaluation folder alongside the fixed report, updated **in place** (same Drive ID). The ephemeral public-readable ciphertext files were deleted; no secrets, original recording, or transcript are in GitHub.
- **Selection for this round: keep Large-v3 Turbo as production default**, Qwen3-ASR 0.6B as optional private second-opinion text engine, Small as fallback; retain Breeze and FireRed as research candidates only. FireRed did not outperform on this one test. More representative recordings and verified human reference transcriptions are required for any confident CER/WER or best-overall-model selection.

**This requested comparison milestone is COMPLETE**: all four SRT-capable models (Small, Turbo, Breeze, FireRed) have now been tested on the same real private recording, with real SRT artifacts and aggregate logs. Qwen3-ASR 1.7B has subsequently passed one real PRIVATE AUDIO **text-only** GitHub CPU benchmark (run 45014350294); Qwen ForcedAligner has not passed real-source alignment. No claim of full word-timed Qwen SRT.

## 2026-11-22 — reproducible private mixed-language evaluation, without false accuracy claims

- New [offline bilingual benchmark](tools/asr_quality_benchmark.py) and synthetic
  tests distinguish **AI reference agreement** from **human-reference error
  measurements**. The public repo contains only evaluation code, not the private
  audio/transcripts/individual mismatch report.
- It first applies Unicode NFKC, apostrophe/case normalization, then the bundled
  offline OpenCC `s2t` script converter (when invoked via the fully installed
  private environment). Chinese error units are individual Han characters,
  English units are English words or numbers, and a mixed-language diagnostic
  combines Han characters with intact English words. These are **not** the same
  as unqualified overall ASR WER.
- All error counts use **exact Levenshtein edit distance relative to one
  explicitly supplied reference**. Missing words, extra words and substitutions
  all contribute; no SequenceMatcher "percentage agreement" is substituted for
  edit-distance statistics. The output also includes bounded diff regions for
  private error inspection, never the original recording.
- When the reference is the older **Google AI-generated SRT or the unlistened
  AI-assisted correction**, the benchmark status is
  `AI_REFERENCE_DISAGREEMENT_ONLY`, and the numeric results are labeled
  **difference rates**, explicitly **not CER/WER, quality grades or rankings**.
  Matching two ASR engines may mean the engines make the same mistake.
- **Human-verified CER/WER remains NOT VERIFIED**. A real gold reference must
  be manually confirmed from the audio before permitting
  `reference-status=human-verified`; the tool cannot listen to the source or
  guarantee truth merely by a flag. Word-level timestamp accuracy is an
  independent and currently unproven metric.
- Private reports must be written outside this public repository with
  restrictive filesystem permissions. The script prints no transcripts or
  mismatch snippets to public logs. Do not upload generated JSON to GitHub.
- The latest true-source Turbo+Smart2 and prior candidate results remain valid
  functional acceptance, not evidence of human-word-accuracy superiority.


## 2026-11-22 — current model shortlist, official license and CPU constraints

| Candidate | Official source | Model weights license | GitHub CPU path | Result scope |
| --- | --- | --- | --- | --- |
| **Qwen3-ASR 1.7B** | https://huggingface.co/Qwen/Qwen3-ASR-1.7B | Apache-2.0 (model card) | **Existing pinned C engine** `antirez/qwen-asr@924694251d9e0f18e5d86bbd06aa3ab5f870002d`, OpenBLAS, `large` weights; same owner Issue #1 short-lived AES-GCM/RSA transfer | **Real private audio CPU PASS:** run 45014350294; 626 text chars, build 4.32s, weights 170.06s, ASR 43.67s, encrypted return. **TEXT ONLY**, no SRT or human WER. |
| **Fun-ASR-Nano-2512** | https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512 | Apache-2.0 (model card) | Official GitHub Ubuntu CPU GGUF runtime pinned to FunASR commit `68aa96ddb96b6ec9b2f50923b9c55d223ef483af`, compiled locally and downloaded F16 encoder/Q8 decoder/FSMN VAD weights | **Real private audio CPU PASS:** run 45015631110; 603 text chars; build 138.22s, download 10.71s, ASR 7.76s; only **2 VAD-segment SRT cues** spanning 0–30s and 30–58.17s. Valid SRT structure but inadequate fine-grained subtitles. No human WER. |
| **Whisper Large-v3 (full)** | https://huggingface.co/openai/whisper-large-v3 | MIT (model card) | Already supported by `transcribe.py`, but larger CPU decode cost than Turbo | Structurally supported; user private source has not been rerun on full large-v3. |
| **Whisper Large-v3 Turbo + Smart2** | Existing `main` and recorded private Runner evidence | MIT (Whisper weights) | Standard CPU runner + signed private roundtrip | **Production baseline**, no human-confirmed CER/WER. |

**Evaluation design:** Do not choose the largest model by model-card WER on a different corpus. Compare on private mixed Mandarin/English recording(s) with a **human audio-listened reference**; until that exists, present only AI-reference disagreement, compute/memory, model download/reproducibility, and evidence of exact output type. SRT structural correctness and forced alignment are separate dimensions.

**Security and costs:** Public GitHub repo contains code/synthetic tests only. Signed URLs in the existing control Issue reference **encrypted ciphertext**, expire, and reveal no plaintext. Neither a local Windows GPU nor finite hosted model API is necessary. All runner minutes, storage, downloads and source model terms remain subject to their own policies.

**Source checking:** Qwen model card and antirez C inference repo checked 2026-11-22, and official FunASR model card plus model-selection guide checked same date. This catalog is a point-in-time selection, not proof that one model is globally the strongest.


## 2026-11-22 — actual private modern ASR comparison, audited

- Both advanced candidate engines processed the **same private 58.191479s Mandarin/English source**, using the existing owner-only Issue #1, standard free GitHub-hosted Ubuntu CPU Runner, a short-lived **ciphertext-only** transfer and authenticated private encrypted return. No Windows execution, TinyFish or capped hosted AI inference API. No original recording, plaintext model outputs, private RSA keys or raw audio URLs in public GitHub.
- **[Qwen3-ASR 1.7B run 45014350294](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45014350294): PASS.** Pinned C engine build **4.32s**, model download **170.06s**, speech recognition **43.67s**, **626 characters of private text**, **NO SRT**. Model available as private second-opinion text only.
- **[Fun-ASR-Nano-2512 run 45015631110](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45015631110): PASS.** Pinned official CPU GGUF runtime compilation **138.22s**, weights download **10.71s**, speech inference **7.76s**, **603 private text characters**, plus **2 valid coarse VAD-timed SRT cues**, approximately 0–30s and 30–58.17s. Those are NOT fine-grained word or phrase timestamps and CANNOT replace a teaching video SRT.
- The same PRIVATE unverified-Google-AI-reference edit-distance evaluation, with NFKC, punctuation/case normalization but **NO OpenCC s2t** available in the ephemeral private runtime, produced aggregate AI-reference disagreement: approved Turbo+Smart2 **6/186 mixed units (3.23%)**, Qwen1.7B **24/186 (12.90%)**, Fun Nano **33/186 (17.74%)**; English word differences respectively **1/103**, **1/103**, **6/103**. **THESE ARE NOT CER/WER OR MODEL ACCURACY RANKINGS.** Simplified Chinese character form from modern candidate engines inflates Han differences. Human-listened reference is still unavailable.
- The prior 24-cue approved Turbo+Smart2 SRT was left untouched; candidate SRT is only 2 long VAD segments and retained **privately** for evaluation. The owner-only Google Drive fixed master comparison report was **updated in place, without creating parallel versions**. Temporary encrypted transfer objects and private keys are deleted after authenticated evaluation. Engine workflow code CI and actual GitHub CPU run success are separate evidence from validated human transcription accuracy.

**Selection for user-facing fine-grained SRT: keep Whisper Large-v3 Turbo + Smart2.** Retain Qwen3 1.7B as optional private bilingual text second opinion and Fun Nano as CPU-feasible research candidate for later dedicated alignment; neither demonstrated higher human-verified recognition accuracy or usable fine-grained SRT timing in this test.


## 2026-11-22 — real bilingual ForcedAligner acceptance versus Whisper timing

- **Observed real private-audio acceptance**: [run #45020751881](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45020751881) **Runner PASS** and authenticated SRT privately decrypted. The source was the same **58.191479-second** owner-only Mandarin/English recording, under the existing RSA-OAEP/AES-GCM signed ciphertext Issue #1 exchange. Public GitHub contains **no user audio/text/private keys**. On standard GitHub-hosted Ubuntu CPU, Whisper Large-v3 Turbo + `Qwen/Qwen3-ForcedAligner-0.6B-hf` processed 12-second audio chunks under `language=auto`.
- **Acceptance counts are now distinguished from fallback**: Qwen accepted **1 / 5** actual audio chunks; the other **4 / 5** used Whisper's original word timing. Accepted comparisons contained **38 source-word timing boundaries**. Absolute change **against the SAME RUN Whisper boundaries**, not speech-ground-truth error: median **0.060s**, P95 **0.410s**, maximum **0.410s**. These numbers **do not prove which timestamp is correct**.
- The resulting experimental SRT has **22 structurally valid cues**, no overlaps/out-of-audio spans; the existing owner-approved official Turbo+Smart2 SRT remains **24 cues**, untouched. Normalized alphanumeric text similarity between those artifacts was **96.52%**, **not** CER/WER. Differences are confounded by fresh Whisper recognition and 12-second chunk boundaries, not solely Qwen alignment.
- Resource phase metrics: model download **24.28s**, combined Whisper recognition + alignment + SRT generation **92.53s**, excluding all Runner setup and encryption-transfer waits.
- **Harness correction**: the initial [run #45020031418](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45020031418) failed after inference because alignment metrics used two counters on one CLI line, which the initial test harness wrongly treated as separate-line-only. [PR #15](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/pull/15) corrected compact metric parsing, [PR #14](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/pull/14) bounded experimental chunking (12 seconds allowed **only** for Qwen alignment), and [PR #13](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/pull/13) introduced numeric acceptance/shift reporting. The merged code passed **143 synthetic tests**. The failed run did not return a usable SRT and must not be counted as success.
- **Decision: do not turn on Qwen ForcedAligner by default for this code-switched audio.** The official aligner uses a **single language hint per audio input** and can reject or distort mixed-language cases; public issue reports additionally describe zero-duration word spans. If alignment work continues, use limited monolingual phrase experiments and an independently **human-listened word-boundary reference** before using an accuracy claim. A valid SRT and low disagreement from Whisper do not prove audio-synced timestamps.
- The owner-only Drive fixed model evaluation master was updated **in place**, no parallel master. Ephemeral encrypted Drive input/output/report staging objects were deleted. No source model retest is needed just for documentation; optional future work has a separate decision gate.
