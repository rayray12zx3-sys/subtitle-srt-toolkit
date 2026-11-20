# Verified GitHub-hosted cloud transcription design

## Current state (2026-11-20)

**PASS for one actual 58.191-second recording.** [Production run 44699772481](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44699772481) completed on a standard GitHub-hosted Ubuntu CPU runner. The runner produced 32 validated SRT cues using open-source Whisper Small, returned only RSA/AES-GCM ciphertext in the workflow log, and the caller decrypted it into a user-delivered .srt in the conversation.

**No user's Windows hardware or self-hosted runner, no paid API, no quota-limited free AI inference.** The public repository stores code/docs/synthetic tests only; the source recording and subtitle text never entered repository commits or public logs.

## Reproducible architecture

1. The caller prepares a short-lived temporary cloud object containing **only AES-GCM encrypted audio**; its contents are not decryptable without a fresh RSA private key.
2. The caller generates a separate RSA keypair for output-return encryption, keeps its private half out of GitHub, and dispatches [cloud-handshake.yml](.github/workflows/cloud-handshake.yml) with an encrypted file ID, output *public* key, and selected OSS model name.
3. The GitHub-hosted runner creates its own fresh RSA keypair and emits just the *public* half into its live action logs, then polls the temporary ciphertext object for a packet encrypted to that public key.
4. The caller encrypts audio via a fresh AES-256-GCM key wrapped under the runner's RSA public key, updates the existing ciphertext object's bytes without changing its public file ID.
5. The runner downloads ciphertext, decrypts only in its temporary working directory, normalizes to 16kHz mono via FFmpeg, downloads static weights from the open-source model repository, then runs `transcribe.py` using CTranslate2 CPU locally.
6. `delivery_gate.py` checks the new output SRT against the actual normalized recording. The runner encrypts the SRT to the caller's independent public key and prints only an encrypted output packet.
7. The caller privately decrypts, separately validates against the original WAV, provides the real .srt file to the user in ChatGPT, and deletes temporary cloud ciphertext objects.

## Security / operational limits

- Do **not** put user media, transcript text, ephemeral **private** keys, or plaintext output in GitHub code, workflow inputs, issue/PR comments, public artifacts, or logs.
- Reading temporary ciphertext is permitted only while it is encrypted; delete temporary objects afterward.
- Runner-owned private input decryption key is ephemeral and never leaves its job memory.
- The job runs with `permissions: contents: read`; it does not need an AI API token or a repository secret.
- Both real media delivery and final user-facing output validation are required to declare task completion.
- GitHub public standard-runner jobs are subject to GitHub's timeouts, limits, use policies and service availability, even though no free-tier inference quota is consumed.
- This protocol is demonstrated, but not yet packaged as one-click automation. A controlling authorized client must orchestrate the two-stage key exchange and private transfer.
- Human listening QA is separate; successful syntax/timing validation does not guarantee transcript is 100% word-perfect.

## Evidence

- [Successful real-media production run](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44699772481), Whisper Small, 32 cues, return decrypted in chat.
- [Successful synthetic voice-model smoke test](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44697359699).
- Historical failed prototypes are resolved: missing FFmpeg in 44698424276 and Python import path in 44699060502. They are not current blockers.

The [HANDOFF](HANDOFF.md) records the latest verified status and future improvements.
