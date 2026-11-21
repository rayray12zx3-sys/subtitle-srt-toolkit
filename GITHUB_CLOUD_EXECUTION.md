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

## 2026-11-21 — One-request assistant operating procedure (connector-dependent)

**User-facing goal:** An authorized ChatGPT assistant takes a conversation audio attachment and returns a verified SRT in the same conversation. The user should not need to execute Windows commands, copy a relay prompt, create a second project, pay an inference API, or transcribe using their own hardware. This is a **procedure for a live, permitted assistant with connected GitHub/Drive access**, not a deployed independent one-click application. The stage must be reported `UNVERIFIED` until a future one-request private input-to-chat-output acceptance trial passes.

**Preconditions:** The authorized assistant can inspect conversation uploads; temporarily create, update, share, then delete a ciphertext-only Google Drive file; dispatch/read GitHub Actions; and privately create/read files in its own short-lived cloud working directory. All these actions must be available and permitted, not assumed. Run permission prompts only when needed; never request credentials or PAT in the conversation. Preserve the model default `large-v3-turbo` and the code-only public GitHub rule.

1. **Source and preparation.** Read the user's actual attached recording. Reject missing/empty media. Work only in the assistant's ephemeral cloud directory, not user Windows. Generate a caller-owned RSA-2048 return key using `python -m tools.secure_exchange new-return-key --private-key /tmp/srt_request_private.pem`. Keep the private PEM out of all public output; only use the short `PUBLIC_KEY_ONLY=rsa-n:...` in GitHub workflow inputs.
2. **Ciphertext-only rendezvous.** Upload a harmless random binary placeholder to a short-lived Google Drive file. Grant *only that individual placeholder object* temporary Anyone-with-link Viewer permission. Record its ID privately for cleanup. Do not share the parent folder or any audio/SRT.
3. **Runner dispatch.** Dispatch `.github/workflows/cloud-handshake.yml` via the authorized GitHub connector or connected browser, with `encrypted_drive_file_id` referencing this binary object, `output_public_key` set to the caller's public key, `model=large-v3-turbo`. Do not place private audio text or secrets into workflow inputs. Run on standard `ubuntu-latest` with `permissions: contents: read`.
4. **Input exchange.** Fetch the current job's **public** `SRT_INPUT_PUBLIC_KEY_B64` from live GitHub logs. Use `python -m tools.secure_exchange encrypt-input --audio INPUT.wav --runner-log job-start.log --cipher-out encrypted_input.bin` to prepare Opus+AES-GCM+RSA-OAEP ciphertext in the assistant's cloud environment. Replace the bytes of that **same temporary** Google Drive ID; do not create a second shared raw-media object. The runner decrypts privately and runs static OSS Whisper weights without inference API calls.
5. **Verify & deliver.** Read logs for `SRT_OUTPUT_CIPHER_B64` **or** `SRT_OUTPUT_CIPHER_PARTS` + exact contiguous `SRT_OUTPUT_CIPHER_PART_####` and `SRT_OUTPUT_CIPHER_READY=1`. Use `python -m tools.secure_exchange finish --private-key /tmp/srt_request_private.pem --job-log job-finish.log --original-audio INPUT.wav --output OUTPUT.srt`. This authenticates the ciphertext and checks actual audio duration, nonempty subtitles, sequential cues and nonoverlapping timestamps before atomic output publication in the private chat working directory. Then **actually attach/link** that file in the user-facing answer. `CI PASS`, `Runner SUCCESS` or `SRT_VALIDATED_NOT_YET_DELIVERED` is never sufficient for task completion without the delivered attachment.
6. **Cleanup, whether success or failure.** Delete temporary shared Google Drive ciphertext objects, ephemeral PEM/private keys, any transient Opus/audio and decrypted SRT copies not meant for delivery; do not write private data to issues, PRs, public Actions artifacts or repository commits. Record only the execution run URL and aggregate (nonprivate) timings; never a plaintext transcript, audio hash or file path on public GitHub. If upload/update/dispatch/log read is unavailable, report precisely the blocked step and stop without claiming a usable SRT.

**Verification gates:**
- [Production proof, earlier real user recording](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44727437501): Whisper Turbo validated new private SRT.
- [Encrypted handoff real-inference synthetic rehearsal](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44915065345): CPU real Whisper, private envelope and SRT validator.
- [Strict runner/client interoperability rehearsal](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44915193779): use actual `cloud_handshake.pack/unpack` with assistant `secure_exchange`; **PASS**, result confirmed; actual runner `pack/unpack` and assistant helper successfully exchanged an encrypted synthetic voice recording and generated an authenticated 3-cue SRT.
- GitHub code-only CI includes 30 synthetic tests including truncation, tampering and invalid SRT handling.

**Remaining acceptance:** A completely new user-uploaded audio recording must travel through all the above connector actions **without further user copy/paste/manual relay**, return the real SRT in the *same chat*, and clean up temporary cloud objects. Only then mark `ONE-REQUEST_WORKFLOW_PASS`. Tool availability, connector authentication and UI permissions are not guaranteed by the repository; no false one-click claim.

## Latest bounded synthetic CPU acceptance (2026-11-21)

- [30 minutes of continuous synthetic speech, Whisper Tiny](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917558587) PASS: 1800s, 1591 cues, end 1799.98s, model compute stage 311.40s, 952,808KiB peak RSS. Validates 600s chunk offsets in a standard cloud runner, **not** Turbo 30m latency or correctness.
- [Two synthetic clips, production Turbo, encrypted batch](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917772851) PASS: 19 cues, complete decrypt + strict validation for both clips. 8-file protocol maximum; 8-file inference runtime **NOT tested**.
- `--language auto` works in code and synthetic English; Mandarin/English word-level correctness under automatic language detection remains unverified on a new private source.
- Future full acceptance requires user source file(s), live connector access, no plaintext in public Github or public Drive, and delivery in current chat.
