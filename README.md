# subtitle-srt-toolkit

**Actual GitHub-hosted speech-to-SRT inference and private chat delivery have been verified.**

[Production run: original audio → Whisper Small → validated, encrypted SRT, completed successfully](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44699772481) (2026-11-20). [Synthetic real-model smoke test](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44697359699) also passed.

This PUBLIC repository includes **tools and synthetic tests only**. It does not hold any private original audio, subtitles, plaintext transcripts, user-media artifacts, or decryption keys.

## Hard requirements

- **Compute must use a standard GitHub-hosted Ubuntu Runner**, not a user's Windows PC or self-hosted runner.
- **Zero paid or finite free-tier hosted AI inference**: download static open-source Whisper model weights and run `faster-whisper` with CTranslate2 CPU inference within the ephemeral GitHub Actions runner. Standard public-repository GitHub Actions usage has platform policy, job time and capacity limits, although no metered paid AI inference/API is used.
- The output must be a new **real SRT** processed from the requested source recording. `delivery_gate.py` verifies non-empty, ordered and correctly bounded timecoded cues. The task is not completed until the verified SRT actually reaches the requester.
- Do not publish WAV, SRT, transcription text, media hashes, plaintext audio URLs or private keys into the repository, GitHub Actions workflow inputs, issues, logs or artifacts.
- Word-for-word correctness is **not** established by structural validation. Preserve fillers/original languages; verify against source audio before claiming manual proofreading.

## Production cloud workflow

**Workflow:** [Private audio to SRT - ephemeral GitHub CPU runner](.github/workflows/cloud-handshake.yml)

**Runner program:** [`tools/cloud_handshake.py`](tools/cloud_handshake.py)

The ephemeral runner creates an RSA keypair, prints **only the public key**, and waits for a temporary encrypted ciphertext file. The authorized caller encrypts the source audio with an AES-256-GCM session key wrapped in that public RSA key, updates the temporary encrypted-only input in a short-lived public-read blob, and supplies the file ID to `workflow_dispatch`. The workflow downloads **ciphertext only**, decrypts privately in the runner, normalizes audio, downloads static open-source Whisper weights, runs the model on CPU, validates the resulting SRT, and encrypts the output to the caller's separate public RSA key. The caller decrypts it and delivers the .srt attachment directly in chat, then deletes temporary ciphertext storage.

Only public keys and encrypted payloads pass through public metadata. No GitHub secret, hosted AI inference API or local user computer is used.

**Important:** This is a verified end-to-end capability, **not** yet a one-click user interface. The orchestrating ChatGPT session must carry out the temporary encrypted input/output exchange; the workflow cannot automatically retrieve a ChatGPT attachment without that orchestration. Never place a raw recording URL in the workflow's `encrypted_drive_file_id` field.

## Reproducible cloud smoke test

[Cloud CPU Whisper smoke test workflow](.github/workflows/cloud-smoke.yml) generates a synthetic voice WAV on the runner, downloads static `faster-whisper-tiny` weights, performs actual open-source CPU inference, and validates the output. It makes no calls to hosted inference services. It uses synthetic media only, and does **not** substitute for acceptance of a real private recording.

## CLI internals

`transcribe.py` is the reusable offline engine called by the cloud workflow:

```text
python transcribe.py source.wav --model-dir /tmp/whisper-weights --language zh --traditional --device cpu --compute-type int8 --output /tmp/new.srt
python delivery_gate.py source.wav /tmp/new.srt
```

The CTranslate2 model directory must be present locally **within the GitHub runner** before inference; `transcribe.py` never falls back to online model access or an inference API.

## Verified and unverified

- **Verified 2026-11-20:** one real private recording (58.191 seconds) generated a valid 32-cue SRT via a GitHub-hosted CPU Runner; ciphertext was privately returned, decrypted, and a user-facing SRT attachment was delivered. See [HANDOFF](HANDOFF.md).
- **Not verified:** automatic one-action future-user audio upload to GitHub without orchestration; human listening-based word-perfect QA; large-v3 runtime for user recordings.
- See [GITHUB_CLOUD_EXECUTION.md](GITHUB_CLOUD_EXECUTION.md) for architecture background and [DELIVERY_GATE.md](DELIVERY_GATE.md) for acceptance rules. Historical documents mentioning blocked transfer describe the former state; the verified 2026-11-20 execution in HANDOFF supersedes those blockers.
