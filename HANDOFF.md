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

## 2026-11-21 — secure exchange client automation milestone

- Continued approved project from pinned main SHA `0986d069722c87187dc2164fc5b19881eee272d3` with no open Issue/PR and no STATUS/TASKS/DECISIONS in this repo. Existing production model-selection truth remains Large-v3 Turbo default, Small fallback, Qwen 0.6B optional review.
- Implemented `tools/secure_exchange.py` to centralize assistant-session RSA-2048 return-key creation (compact public key, private key never committed), Opus+AES-256-GCM encrypted input, deterministic chunked encrypted-output log reconstruction for long SRTs, and strict validation before atomic private SRT delivery. Includes synthetic crypto handoff tests in `tests/test_secure_exchange.py`.
- Extended runner's encrypted SRT output to chunk long ciphertext instead of risking GitHub log-line truncation; increased Drive ciphertext read cap to 64MiB with fail-closed oversized rejection. Small outputs remain backward compatible with `SRT_OUTPUT_CIPHER_B64=`. CI installs only cryptography for the synthetic tests.
- Added ignore rules for temporary keys, compressed audio and ciphertext. No user audio, SRT, private key or fingerprints were committed. Only code/tests/synthetic content.
- **Checkpoint status:** REUSABLE ASSISTANT-SIDE CRYPTO HELPERS = IMPLEMENTED; verify new GitHub CI separately. **ONE-CLICK AUTHENTICATED DRIVE+GITHUB DISPATCH+CHAT DELIVERY = NOT YET VERIFIED**, since connector-authorized UI/API actions and user-file attachments still require the assistant app's cooperation. Do not claim one-click completion or rerun the user's Windows.

## 2026-11-21 — secure workflow transition checkpoint

- Pinned initial main `0986d069722c87187dc2164fc5b19881eee272d3`, verified existing HANDOFF/README/model evaluation and no open issues/PRs in this repo.
- `tools/secure_exchange.py` now supports fresh caller-owned RSA-2048 keys, 48-kbps Opus+AES-GCM private audio encryption, reconstruction of chunked encrypted SRT from GitHub logs, and strict output validation before file replacement. Long encrypted outputs no longer rely on one oversized log line. Maximum temporary Drive ciphertext download 64 MiB.
- [GitHub CI run 44914980660](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44914980660) **30/30 PASS** (includes 6 new crypto/SRT unit tests).
- [GitHub synthetic genuine CPU Whisper + encrypted assistant handoff run 44915065345](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44915065345) **PASS**, generated 3 valid SRT cues, 4.275-second synthetic voice, ciphertext revalidated and decrypted, no personal media used.
- [Strict runner-side crypto interop test run 44915193779](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44915193779) **PASS**, independently verified via GitHub run result after launch; used real CPU Whisper Tiny on synthetic voice and actual runner-side `pack/unpack` with the assistant client-side crypto helper. Distinguish model synthetic test from real attachment-to-chat acceptance.
- [GITHUB_CLOUD_EXECUTION.md](GITHUB_CLOUD_EXECUTION.md) now provides an operational single-chat-request runbook for *an authorized connected assistant* using temporary encrypted Google Drive file and GitHub Actions, including privacy and cleanup gates.
- **NOT YET ONE-CLICK:** Authenticated Drive object creation/sharing/update, GitHub dispatch, job-log read and actual chat attachment remain connector/client orchestration steps. No user Windows, PAT, user machine inference or paid/free-tier model API should be introduced. A fresh recording delivered in one user turn is required to claim end-to-end one-request acceptance.

## Stage 4 accepted checkpoint — 2026-11-21

- [30/30 code-only unit tests](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44914980660) PASS, covering authenticated encryption, compact public key, ciphertext chunk reconstruction, incomplete packet rejection, and atomic output validation.
- [Real GitHub-hosted CPU Whisper synthetic protocol rehearsal](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44915193779) PASS, using production runner-side crypto with assistant client-side crypto and an actual 3-cue SRT.
- **Accepted in this stage:** reusable cloud-side private transfer helper, long-output encrypted-log support, repo-checked assistant operating procedure, and synthetic real-inference interoperability.
- **Still not accepted:** a single new private user audio attachment automatically dispatched through connected Google Drive/GitHub services and delivered to chat without manual/permission interruptions. This remaining end-to-end *app integration* gate cannot be declared PASS based on GitHub CI/synthetic audio.

## 2026-11-21 — long audio / mixed language segmentation implementation

- User requested continuation of limit removal: target long audio segmentation, language auto-detection and eventually private multi-file batch conversion. No new default model or user-local compute.
- Added `tools/chunking.py`: mono PCM16 WAV bounded segments with a silence-seeking boundary ±2s and no overlapping or dropped PCM samples; hard-cut fallback if no silence. The existing runner decodes authenticated Opus to PCM16 WAV using ffmpeg, so chunking remains inside standard GitHub-hosted Actions CPU.
- `transcribe.py` optionally loads Whisper **once** then sequentially processes `--chunk-seconds` partitions; detected language may vary per chunk when `--language auto`, all recognized word timecodes receive original-audio offsets, final SRT still passes `delivery_gate.py`. Default for standalone CLI remains no splitting for backward compatibility.
- Main cloud workflow defaults to `--chunk-seconds 600` and `--language auto`, with explicit zh/en choice if Whisper automatic detection proves unreliable for code-switching recordings. These are *per-chunk multilingual recognition*, not guaranteed word-level code switching.
- **DO NOT CLAIM 30-60-minute real source verified** from code/CI/synthetic fixtures. Any long-audio runner smoke test and subsequent private real recording must pass before raising supported length claims. Streaming model inference is still sequential and subject to 100-minute job ceiling.

## 2026-11-21 — private multi-file batch conversion (CI/synthetic evaluation pending)

- Added `tools/batch_bundle.py`: strict authenticated-envelope-internal `SRTBATCH1` ZIP manifest for **1–8 clips** with non-identifying `clip_XXXX` IDs, no plaintext source filenames in public metadata, 64MiB plaintext input cap and 16MiB output cap, strict ZIP member/ordering checks.
- `tools.secure_exchange encrypt-batch` accepts repeated `--audio` source paths and stores only one RSA/AES-GCM ciphertext object; `finish-batch` decrypts one ZIP of SRTs and validates each against the matching original audio, publishing a brand-new private directory only once **all** cues pass.
- Runner `cloud_handshake.py` auto-detects private batch and runs each clip sequentially with the same pre-downloaded model and existing chunk/language options. Single-audio protocol remains backward compatible.
- **VERIFIED SYNTHETIC RUNNER BATCH:** two distinct speech clips completed actual GitHub-hosted Whisper Large-v3 Turbo inference, 19 valid cues, AES-GCM/RSA roundtrip and atomic delivery into a private synthetic test output ([run 44917772851](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917772851)). Eight-item bundle layout is unit-tested, but 8-source real inference and a live ChatGPT attachment-to-chat batch remain UNVERIFIED. GitHub 100-minute cap and input size still apply.

## 2026-11-21 — length + batch upgrade: verified latest acceptance

- New `tools/chunking.py` partitions mono PCM16 WAV into non-overlapping nominal 600s pieces with a nearby quiet cut where possible, conserves exact source samples, translates individual recognized word timestamps back to original audio. CLI standalone defaults unchanged; GitHub standard runner now uses `--chunk-seconds 600` by default and `--language auto`, with forced `zh`/`en` options.
- [41/41 GitHub code-only unit tests PASS](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917772932): chunking/sample exactness, timestamp offsets, auto/forced language modes, 8-item bounded batch ZIP and all-or-nothing output validation.
- [30-minute continuous SYNTHETIC English speech on standard Github-hosted CPU, real Whisper Tiny: PASS](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917558587): input length 1800.0s, **1591 cues** structurally validated, last cue ends 1799.98s; **311.40s** ASR-processing command wall time (model downloaded in a prior step), process peak RSS **952,808 KiB**. This is not a 30-minute Turbo benchmark or a word-perfect human-reviewed transcript.
- [Two-file real Whisper Tiny encrypted/validated batch synthetic PASS](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917424926): 20 SRT cues overall, independent file timing and client-to-runner RSA/AES-GCM.
- [Two-file real **Whisper Large-v3 Turbo** encrypted/validated batch synthetic PASS](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917772851): 19 SRT cues overall, both outputs individually validated and decrypted; production default compatibility regression checked.
- Operational limits remain: **8 clips/batch**, max 64MiB (compressed encrypted input packet incl. RSA overhead), output bundle 16MiB before encryption, 100m production job ceiling, at most 30m waiting for encrypted input, approx 3m FFmpeg compression timeout per file on the assistant cloud client. No verified claim that 8 long recordings fit within one job.
- **NOT VERIFIED:** fresh user-supplied 30-minute private audio transcription with Turbo; user-wide word-level manual QA; any 60-minute real recording; and completely unattended chat-app-to-Google-Drive-to-GitHub-to-chat attachment handoff. Model selection remains Turbo primary, Small fallback, Qwen3-ASR 0.6B optional second-opinion text.
- Public GitHub still contains no actual private audio, transcribed words, SRT or keys. No user Windows, self-hosted runner or rate-limited hosted AI inference is used.
