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

## Model upgrade results (2026-11-20)

The GitHub-hosted production SRT default is now **Large-v3 Turbo**, validated with a real private recording. Choose Small explicitly as a fallback. An optional private Qwen3-ASR 0.6B benchmarking workflow can generate a second-opinion transcript and `tools/text_review.py` compares the private outputs without modifying timestamps or publishing personal text. Qwen3-ASR 1.7B passed synthetic CPU feasibility only; alignment and real-audio SRT remain unverified. See [MODEL_EVALUATION.md](MODEL_EVALUATION.md).

## Model comparison milestone (2026-11-20)

Additional real private recording trials now include Breeze-ASR-25 (**33 cues**) and FireRedASR2-AED (**24 cues**, actual [GitHub production run 44752794627](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44752794627)) alongside Turbo (**31 cues**) and Small (**32 cues**). Private SRT outputs were encrypted, structurally validated, delivered to chat, and kept in an owner-only Google Drive evaluation folder, **never published in this repository**.

The production default remains **Large-v3 Turbo**, Small fallback, Qwen3-ASR 0.6B optional private-text cross-check. Models are NOT ranked by genuine CER/WER: only cross-recognizer string similarity was measured, without human verified truth. FireRed had greater inference cost and no demonstrated accuracy advantage for this test. See [MODEL_EVALUATION.md](MODEL_EVALUATION.md) for aggregate evidence.

## Next stage: reusable secure chat-to-GitHub client (2026-11-21)

The previous manual RSA/AES-GCM media handoff is now packaged as
[`tools/secure_exchange.py`](tools/secure_exchange.py), with offline synthetic
integration tests. It is an **assistant cloud-session helper**, NOT a command
to run on the user's Windows PC. All inference still runs on the GitHub-hosted
CPU runner.

**Three assistant-side helpers:**

```text
# 1) Prepare caller-owned private return key in an ephemeral assistant cloud directory
python -m tools.secure_exchange new-return-key --private-key /tmp/srt_private.pem

# 2) After the authorized assistant dispatches Actions and obtains the runner's
# public key from its live job logs:
python -m tools.secure_exchange encrypt-input --audio INPUT.wav --runner-log /tmp/job-start.log --cipher-out /tmp/encrypted_input.bin

# 3) After updating the short-lived ciphertext-only Drive object, and the runner
# reports encrypted SRT ciphertext:
python -m tools.secure_exchange finish --private-key /tmp/srt_private.pem --job-log /tmp/job-finish.log --original-audio INPUT.wav --output /mnt/data/new_subtitles.srt
```

`new-return-key` prints only the 348-character compact RSA **public** key
to pass into workflow_dispatch. The corresponding private key stays exclusively
in the assistant's short-lived workspace. `encrypt-input` compresses the
private recording locally in that **assistant cloud workspace** to 48-kbps Opus
and writes AES-256-GCM+RSA-OAEP ciphertext. Never upload plaintext to a public
GitHub repo or to the temporary public-read blob. `finish` reconstructs
chunked ciphertext (even for longer subtitles), authenticates it and validates
SRT against the original audio before writing the result, without printing the
subtitle text into public logs. The caller must then **actually attach** the
validated SRT in chat and delete both temporary ciphertext storage and
ephemeral private key.

**What remains manual/connector-dependent:** the authorized assistant must
create/share the temporary encrypted Google Drive file, dispatch GitHub Actions,
obtain the runner's public key, update the encrypted Drive file, and receive
job logs using connected authenticated tools. Neither a connector's login,
permission prompts, temporary file creation, workflow dispatch, nor chat
attachment delivery can be guaranteed by Python code alone. This is **not
a verified one-click flow**. Reusable helper + CI proves the crypto handoff,
not future end-to-end autonomous delivery or word-for-word accuracy.

The default model remains Large-v3 Turbo; no paid or quota-limited AI
inference is used. Open-source dependencies and GitHub's normal usage
limits still apply.

## Long-duration and mixed-language settings (2026-11-21)

The GitHub-hosted private cloud workflow now exposes two bounded controls:

- `language=auto|zh|en` — **auto** per-segment Whisper language detection is the new cloud default; explicit zh/en remains selectable. Code-switching inside one segment can still be misrecognized and requires audio review.
- `chunk_seconds=600` (default) — split decoded mono PCM16 WAV into non-overlapping nominal 10-minute segments; choose a nearby quiet point if present, otherwise hard split. Recognized word timestamps are offset back to original file positions and globally validated. `0` disables splitting; valid nonzero values are 2–3600 seconds. Whisper model weights are initialized once per file. Manual transcripts and timing QA remain unverified.

This changes **code behavior only** until a real long-file GitHub inference run is validated. There is still a 100-minute job timeout, finite CPU/RAM/storage, and 64MiB encrypted transfer limit. Automatic detection is not guaranteed accurate for mixed language, and silence-seeking splits can still cut words when there is no nearby silence.

## Private batch of multiple recordings (2026-11-21)

One GitHub-hosted CPU job can now accept an encrypted multi-audio packet containing **1–8 files**. In the assistant cloud workspace only (not user Windows):

```text
python -m tools.secure_exchange encrypt-batch --audio first.wav --audio second.m4a --runner-log /tmp/start.log --cipher-out /tmp/encrypted-batch.bin
python -m tools.secure_exchange finish-batch --private-key /tmp/caller.pem --job-log /tmp/end.log --audio first.wav --audio second.m4a --output-dir /mnt/data/new-srt-batch
```

Returned files are named `clip_0001.srt` and `clip_0002.srt` in input order. A failed clip blocks the whole delivery. The authorized caller still must upload encrypted-only bytes, initiate GitHub Actions and actually attach private SRTs in chat. **Verified with actual GitHub-hosted Whisper inference on two synthetic audio clips** (Turbo and Tiny). This does **not** establish a new private multi-audio request's automatic delivery, nor an 8-source workload's completion within 100 minutes.

## Length/automatic language/batch CPU verification

[30m continuous synthetic speech test](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917558587) **PASS** on standard GitHub-hosted CPU with **Whisper Tiny**, 1,591 SRT cues, final timestamp 29:59.980, audio-processing command wall 311.40s and process memory peak 952,808 KiB. Synthetic 30m is not evidence of 30m private Turbo throughput or human-verified accuracy.

[Encrypted two-source production Turbo model synthetic regression](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917772851) **PASS**, 19 validated SRT cues over 2 independent clips; [code-only CI](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44917772932) **41/41 PASS**.

Next true app integration gate: a **new private** 30m recording or multi-file upload must traverse authorized Google Drive temporary ciphertext, GitHub, SRT validation and actual chat attachment, without manual user relay. Until that happens, **automatic one-request delivery remains UNVERIFIED**.

## Fully automatic semantic subtitle segmentation (2026-11-22)

**Default mode is now `--segmentation smart`, no manual proofreading or manual splitting step.** The CPU-only algorithm uses the punctuation retained from Whisper recognition, pauses, common Chinese/English clause markers, grammatical continuation penalties, subtitle duration, and display width. It globally chooses the best word-token boundaries instead of cutting blindly at exactly N characters.

Example: `python transcribe.py source.wav --model-dir /tmp/whisper-weights --traditional --segmentation smart --max-chars 22 --line-chars 12 --max-lines 2 --max-seconds 4 --output subtitles.srt`. The same behavior applies by default to GitHub cloud and encrypted batches. `--segmentation basic` restores the earlier mechanical rules if needed.

**Limits:** no paid inference API, no extra model download, no manual approval required; punctuation and word-time estimates come from Whisper and may be mistaken. The method is *heuristic semantics*, not full language-model comprehension; one ASR token may contain several Chinese characters, and it will never invent individual character timestamps. Avoid claiming word-perfect transcription or exact timestamp accuracy without independent evidence.
