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
