# HANDOFF — subtitle-srt-toolkit

## Canonical requirements (confirmed 2026-11-20)

- Execution target: **GitHub-hosted standard Ubuntu GitHub Actions runner** ONLY. No user Windows/local machine or self-hosted runner without new explicit approval.
- Public GitHub repository contains **code, docs and synthetic tests only** — never original audio, spoken words, private audio/SRT URLs, private keys, plaintext transcript or user-media artifacts.
- **No paid/limited-free AI inference quotas.** Run open-source faster-whisper weights locally on the GitHub runner CPU. Downloading static model weights is permitted; hosted inference APIs are not.
- A generation task cannot be marked completed until a **new, real SRT** from the requested recording is validated and returned to the user in the chat. CI and synthetic tests alone never count.
- The user wants accurate Traditional Chinese, original-language speech retained, unnecessary punctuation removed, and dependable timing. No claim of human listening verification without actual audio review.

## Latest production verification — PASS

- **Actual recording processed** by a standard GitHub-hosted Ubuntu runner on 2026-11-20 via [successful cloud workflow run 44699772481](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44699772481).
- GitHub-hosted runner used `ffmpeg`, static open-source `Systran/faster-whisper-small` weights, CPU int8 inference, local OpenCC and `delivery_gate.py`. **Actual 32-cue SRT produced and structurally validated**. Earlier failed runs 44698424276 (ffmpeg missing) and 44699060502 (Python module path) were repaired.
- A private ephemeral RSA OAEP + AES-GCM exchange delivered encrypted recording through temporary shared encrypted-only Google Drive blob, never plaintext. The corresponding private decryption key remained on the ephemeral GitHub runner. An independently generated output public key encrypted SRT for return to the ChatGPT session, where it was decrypted and validated against the original 58.191-second recording. Public Drive temporary input files were deleted upon success.
- Two private conversation files were produced and verified: a **raw 32-cue Whisper Small SRT** and a **30-cue dual-transcript, text-corrected SRT**. Do **not** commit either file or their contents into the public repository. They were delivered in the 2026-11-20 conversation.
- **No manual listening QA claim:** the corrected version uses previous AI transcript as reference, not human audio-by-audio checking.
- [Synthetic 3-cue true inference smoke test PASS](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44697359699). This is supplementary evidence; the production run above is the end-to-end evidence.

## Current implementation

- `tools/cloud_handshake.py`: Runner-owned ephemeral RSA keypair, public-key upload handshake, encrypted ciphertext fetch, CPU Whisper transcription, private encrypted SRT egress in job log.
- `.github/workflows/cloud-handshake.yml`: user-authorized workflow_dispatch using only temporary encrypted file ID, caller output RSA **public** key and model choice. Standard GitHub runner, no API quota or repo secret required.
- `transcribe.py`: pre-existing local CTranslate2 model-only inference, strict offline/fail-closed model path.
- `delivery_gate.py`: validates nonempty and ordered subtitle cues relative to source audio duration; does not assert delivery itself.
- `.github/workflows/cloud-smoke.yml`: reproducible synthetic speech real-Whisper smoke check.
- Superseded `SRT_TRANSPORT_KEY` prototype and workflow have been removed from main to avoid requiring credentials.

## Remaining quality/design improvements (not a regression of production PASS)

- Automate the orchestration of ephemeral handshake and encrypted Drive file updating, so future chat uploads avoid manual step-by-step tool calls.
- Improve segmentation/word-level correctness on Mandarin-English code switching; Whisper Small included some unnatural punctuation/word splits. Model upgrades are allowed only as static downloaded weights running on standard GitHub runner and with verified costs/limits.
- Perform real audio listening verification if a claim of fully proofread word-for-word subtitles is required.
- Retain code-only privacy rule; never expose AES keys or raw captions in logs, public artifacts, workflows, dispatch inputs or source code.

## State

**PRODUCTION TRANSCRIPTION AND PRIVATE SRT DELIVERY: PASS for 2026-11-20 recording.**
**FULLY AUTOMATED REUSABLE ONE-STEP CHAT HANDOFF: NOT YET VERIFIED.**
This distinction must stay explicit; do not revive the old Windows-only direction or historical missing-model blocker as current truth.

## 2026-11-20 — stepwise model evaluation (in progress)

- User authorized incremental upgrades, comparison logs, and choosing the best combination. Treat any unverified model as `NOT_TESTED`, not as an improvement.
- Stage 1: Add open-source `large-v3-turbo` CTranslate2 weights to current GitHub-hosted Whisper implementation, keep existing Small production baseline and encrypted private-media protocol. Log separate model download and real inference durations; compare actual SRT privately, no user text in GitHub.
- Stage 2: Evaluate Qwen3-ASR 0.6B CPU feasibility, then optionally 1.7B and forced alignment only if the 16GB standard runner can handle it. Different transcription backends require their own word/char timing solution.
- Preserve requirements: **GitHub standard public runner only, no Windows/local hardware, no hosted quota-limited AI inference, code-only public repo**. Successful baseline production from run 44699772481 remains the last validated end-to-end reference until a stronger model actually passes.

## 2026-11-20 — model selection milestone (aggregate evidence only)

- Stage 1: Real private audio Large-v3 Turbo SRT PASS [run 44727437501]; 31 cues, model download 7.28s, ASR generation 40.21s. Baseline Small PASS remains 32 cues [run 44699772481]. Both produced valid SRT.
- Stage 2: Real private audio Qwen3-ASR 0.6B text-only PASS [run 44729262014]; model download 8.23s, text generation 25.30s. Qwen has no SRT word timing in this lane; do not report it as delivered SRT.
- Stage 3: Qwen3-ASR 1.7B synthetic CPU feasibility PASS [run 44729975533], peak ~6.5GiB RSS; real private-media quality test NOT VERIFIED. Forced alignment NOT VERIFIED.
- Provisional production default: **Large-v3 Turbo** + optional private **Qwen3-ASR 0.6B cross-check**, without blindly changing text. Small is fallback. The new `tools/text_review.py` generates private disagreement reports; compare them with the audio before edits.
- See [MODEL_EVALUATION.md](MODEL_EVALUATION.md). The final optimal model combination requires human word-level quality evaluation on more representative recordings; do not claim a definitive accuracy winner based on AI-to-AI text similarity.

## 2026-11-20 — Breeze/FireRed candidate milestone

- Prior model comparison report and 6 private reference files backed up to a persistent, owner-only Google Drive folder; 2026-11-20 Breeze real SRT added as a seventh file; the main report updated **in place** and temporary ciphertext deleted.
- **Breeze actual encrypted 58.191s recording => 33-cue validated SRT PASS** on GitHub standard CPU [run 44745387647](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44745387647). Model weight download 17.61s; inference/output 59.31s. Did not replace production default; quality relative to AI Studio is unverified. A prior shortened RSA public-key dispatch failed before processing media; compact public key support repaired it.
- FireRedASR2-AED synthetic Chinese/English CPU inference PASS [run 44740104063](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44740104063): 13 timestamp items, memory ~9.1 GiB, actual-user-audio SRT NOT TESTED.
- See [MODEL_EVALUATION.md](MODEL_EVALUATION.md) for aggregate evidence. Private raw audio, SRT, transcript, ciphertext, or private-media hashes must never enter this public repo. Next possible milestone: FireRed real-media private timing evaluation with the same security and completion gate, and user-approved legal/license review for third-party model conversion.

## 2026-11-20 — user-requested candidate-model round FINISHED (latest verified checkpoint)

- Results backed up to **private Google Drive** in the existing `字幕模型評估｜subtitle-srt-toolkit` folder; the `00_模型測試結果_固定主檔.md` report was updated **in place**, preserving its Drive ID. After previous baseline files and Breeze, private `07_FireRedASR2-AED.srt` now contains the actual verified FireRed SRT.
- [FireRed real source GitHub Actions PASS 44752794627](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44752794627). Five input audio chunks -> 24 SRT cues -> validation passed -> encrypted return privately decrypted -> independently checked against 58.191s WAV. Model download 17.27s, load 9.11s, inference 141.74s, peak RSS ~9.18GiB; finish 58.165s. Prior attempt [44751494953](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44751494953) failed due to programming error assembling SRT; fix commit `687fc66a` is now in main.
- Agreement with unverified Google AI Studio AI transcription: FireRed ~96.80%, Turbo ~98.75%, Breeze ~98.97%, Small ~98.65%. Not ground-truth CER/WER; FireRed has visible repeated words and segmentation issues. **Keep Turbo default; Small fallback; Qwen3-ASR 0.6B optional crosscheck. No upgrade to FireRed or Breeze by default.**
- Public GitHub remains code, synthetic tests, numeric evaluation metadata only. Private audio, SRT, words, secrets, and user-file URLs are not public. Four temporary encrypted-only Google Drive transfer files were deleted after actual FireRed delivery.
- **Comparison round COMPLETE**; full automation of the key exchange, human listening truth labels, Qwen 1.7B real SRT, and forced aligner remain separate unverified possible future improvements. Do not mark those extra objectives as done.
