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

## Production cloud workflow — verified signed ciphertext path (2026-11-22)

**Default assisted ChatGPT route:** The connected GitHub account posts an owner-authorized `/srt-run` command to the **existing [control Issue #1](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/issues/1)** with a fresh RSA **public** return key and `transport:"signed-url"`. The GitHub-hosted standard Ubuntu CPU Runner announces its own ephemeral RSA **public** input key through the same Issue. ChatGPT encrypts the private source recording using RSA-OAEP/AES-256-GCM, places **ciphertext only** in private temporary staging, and posts a short-lived, read-only signed ciphertext URL for that exact run. The Runner authenticates and decrypts it transiently, executes the offline Whisper Large-v3 Turbo model with Smart2, validates the SRT structure, and returns **only encrypted** subtitles. ChatGPT authenticates/decrypts the result, verifies its time range against the private audio, delivers the SRT, and removes temporary ciphertext and private-key material.

**Real private-audio proof:** [GitHub Actions run #45002968782](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45002968782) **PASS**, 58.191-second source WAV → 24 SRT cues, 17 double-line cues, with no paid browser automation, hosted AI inference API or user Windows resources. A subsequent **display-only** contraction line-break correction was merged via [PR #7](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/pull/7) and applied to the privately delivered SRT without changing recognized nonblank text or timestamps. PR #7's exact post-merge engine was not separately rerun for that private recording; the GitHub code-only tests passed.

**Components:** [owner comment dispatch](.github/workflows/issue-comment-dispatch.yml) → [reusable cloud inference](.github/workflows/cloud-handshake.yml) → [encrypted transport](tools/signed_cipher_transport.py) and [private CPU runner](tools/cloud_handshake.py). Manual `workflow_dispatch` with `transport:"drive"` remains as a legacy alternative, **not** the accepted default route; it may need separately managed anonymous read access to ciphertext only.

**Boundaries:** This is a completed **assisted ChatGPT-connector flow**, not a separately deployed one-click service or a claim of unlimited GitHub compute. It requires live authorized GitHub/Drive connectors and an assistant-side private runtime. GitHub Actions CI/structural validation does not prove verbatim transcription accuracy, exact word alignment or human proofreading. Never publish a recording, plaintext transcript/SRT, private key or plaintext media URL to this public repository, Issue or logs.

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

## Optional legacy secure-exchange helper (2026-11-21)

The original manual RSA/AES-GCM handoff remains packaged as
[`tools/secure_exchange.py`](tools/secure_exchange.py), with offline synthetic
integration tests. This is an **optional assistant-side legacy/debug helper**;
the accepted current route uses owner Issue comments and short-expiry signed ciphertext links as described above. It is **not** a command to run on the user's Windows PC. All inference remains on the GitHub-hosted CPU runner.

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

**What remains connector-dependent:** the authenticated ChatGPT session still
coordinates the private media, ephemeral keys, owner Issue command, staged
ciphertext, encrypted Runner log result, local SRT validation and chat delivery.
These steps **have succeeded end-to-end for the recorded 58.191-second audio**,
but an independent unattended one-click app has **not** been deployed.
A connector outage, expiry or permission change may block a later request;
crypto unit tests alone never guarantee future delivery or word-for-word accuracy.

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

**Still unverified for longer/batch media:** a new private ~30-minute recording or multi-file request must pass the current signed-ciphertext GitHub flow, aggregate SRT validation and actual chat attachment. The **58.191-second single-audio assisted flow is already verified**; do not confuse that acceptance with private 30-minute or multi-file acceptance.

## Fully automatic semantic subtitle segmentation (2026-11-22)

**Default mode is now `--segmentation smart`, no manual proofreading or manual splitting step.** The CPU-only algorithm uses the punctuation retained from Whisper recognition, pauses, common Chinese/English clause markers, grammatical continuation penalties, subtitle duration, and display width. It globally chooses the best word-token boundaries instead of cutting blindly at exactly N characters.

Example: `python transcribe.py source.wav --model-dir /tmp/whisper-weights --traditional --segmentation smart --max-chars 22 --line-chars 12 --max-lines 2 --max-seconds 4 --output subtitles.srt`. The same behavior applies by default to GitHub cloud and encrypted batches. `--segmentation basic` restores the earlier mechanical rules if needed.

**Limits:** no paid inference API, no extra model download, no manual approval required; punctuation and word-time estimates come from Whisper and may be mistaken. The method is *heuristic semantics*, not full language-model comprehension; one ASR token may contain several Chinese characters, and it will never invent individual character timestamps. Avoid claiming word-perfect transcription or exact timestamp accuracy without independent evidence.

### Automatic smart subtitle layout: live CPU regression

[GitHub Turbo real-inference synthetic test](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44927008739) **PASS**, 2 different clips -> 10 SRT cues, of which **8 are automatically two-line**; encrypted send/return, audio-bounded timecodes and approximate max-line width passed. [50/50 code-only tests](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/44926858655) PASS.

No manual sentence splitting or waveform editor is required. The fully automatic method is heuristic semantics (ASR punctuation, pauses, clause markers, readability), not a promise of 100% correct transcription, perfect semantics, exact per-Chinese-character timestamps or formal superiority to Subtitle Edit.

## Semantic segmentation 2.0 — automatic reading-speed handling (2026-11-22)

Default smart mode now penalizes excessively fast reading load in the global
subtitle-boundary optimization, distinguishing CJK characters and English words.
It gently extends very short subtitles **only into available silence** (up to
280 ms; never starts early or overlaps the following utterance). No manual
editing or external AI inference API is required.

`tools/subtitle_quality.py` reports aggregate, non-transcript metrics (fast
readability, very short cues, line count, width). For genuinely fast speech, an
over-speed warning is unavoidable without inventing slower speech or discarding
words. The validator preserves original recognized text and will not claim
perfectly readable captions in such cases. No blanket accuracy guarantee.

## Optional official CPU Qwen3 forced alignment (experimental)

GitHub workflow has `alignment=off|qwen`; **off is the default** until
a bilingual CPU run and a real-source alignment accuracy comparison justify
promotion. With `qwen`, the official Apache-2.0
`Qwen/Qwen3-ForcedAligner-0.6B-hf` is downloaded as static weights
inside GitHub Runner and used locally (CPU, PyTorch + Transformers).
Recognition continues to use existing Turbo. Audio is chunked to **240s or
less** for alignment; original recognized characters/word order are preserved.
If Qwen's recognized-token alignment does not match the source exactly or
gives impossible times, individual chunks automatically fall back to Whisper
word timestamps. No paid/limited API or manual proofreading required.
This is an **optional experimental mode**, not proven more accurate merely
because the model returns finer granularity.

## Legacy encrypted-Drive dispatch (historical, not the default)

An earlier owner-only GitHub Issue dispatch used `encrypted_drive_file_id` and a publicly readable ciphertext-only Drive file. It was validated for GitHub workflow triggering, but required separate anonymous read access to its encrypted rendezvous object. **Use the newer `transport:"signed-url"` path below** when a valid short-expiry ciphertext URL is available. The old `transport:"drive"` branch is kept for compatibility only. Both variants accept public RSA return metadata but must never receive plaintext media, credentials or private RSA keys.

## No paid-browser ciphertext transfer (ephemeral signed-link protocol)

**Status: live real-source PASS, 2026-11-22.** [Run #45002968782](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45002968782) verified an owner Issue command, an ephemeral public-key exchange, a signed ciphertext download, offline Whisper CPU inference, private encrypted SRT return, and chat delivery. This is not human-scored transcript correctness.

The previous GitHub comment command removed paid browser usage for **triggering** Actions but still needed an anonymously readable Google Drive file. The new opt-in `transport:"signed-url"` mode removes that Drive sharing requirement too, while retaining `transport:"drive"` for legacy compatibility.

1. In the private assistant cloud, hold the original audio and generate a **fresh private RSA return key**. Keep all plaintext and private keys off GitHub.
2. Issue #1 owner command: `/srt-run {"transport":"signed-url","output_public_key":"rsa-n:<PUBLIC_2048_BIT_MODULUS>","model":"large-v3-turbo"}`. The **input audio is not yet uploaded anywhere public**.
3. The standard GitHub-hosted runner prints its own ephemeral `SRT_INPUT_PUBLIC_KEY_B64` **and automatically posts `/srt-key <GITHUB_RUN_ID> <RSA_PUBLIC_KEY_B64>`** to the fixed Issue via its temporary, narrowly scoped GitHub Actions `GITHUB_TOKEN` (`issues: write`). The assistant reads this PUBLIC key through the connected GitHub comments tool, without reading live logs or opening a paid browser. The runner then polls for an owner-authored `/srt-packet <GITHUB_RUN_ID> <SIGNED_URL>`.
4. The assistant converts the original audio to short-lived Opus and RSA-OAEP/AES-GCM **ciphertext only**. Upload to a PRIVATE owner Drive staging file using the connected file tools; fetch an **expiring, read-only signed download URL** for that *ciphertext*, not for the audio. Owner comments `/srt-packet <RUN_ID> <SIGNED_URL>` on Issue #1. The approved origin is restricted to `https://sdmntpr*.oaiusercontent.com/files/<UUID>/raw`, with short expiry and a bounded packet size; unknown destinations, wrong run IDs, non-owner comments and non-SRT2 packets are rejected.
5. The runner GETs ciphertext from the short-lived signed link, authenticates/decrypts in its ephemeral memory, performs offline Whisper inference, validates, and logs only encrypted SRT output. The assistant decrypts/authenticates/validates the new SRT against original audio and attaches the actual file in the chat, then deletes the private staging file and private keys.
6. **No-model network diagnostic:** only the owner may post `/srt-probe <SHORT_LIVED_SIGNED_CIPHERTEXT_URL>`; runner verifies that a signed `SRT2` ciphertext URL can actually be fetched. It never downloads a speech model or consumes paid inference. Do not pass raw media URLs or private recordings.

**Trust boundary:** the signed URL is posted in a PUBLIC GitHub comment, so even though it references only authenticated ciphertext and automatically expires, it is briefly visible to anyone. Do not use if link publication of ciphertext (even temporarily) is forbidden by your privacy policy. Both a live `/srt-probe` and one real private `/srt-run` have passed; **future availability and platform quotas are still conditional** because connected tools can change URL expiry or network reachability. No unattended product-level one-click claim follows merely from the code being merged. The private Drive staging file must be deleted; expired Issue URLs remain visible but no longer authorize download.

## Private bilingual ASR quality benchmark (no inference API)

The offline program [tools/asr_quality_benchmark.py](tools/asr_quality_benchmark.py)
compares the **existing private SRTs** with a separately identified reference.
It requires a clear provenance status for that reference and never publishes
audio, SRT, transcript differences, or private report data to GitHub.

From an authorized **assistant private cloud workspace** (not the user's Windows
and not in this public repository), with the existing offline `requirements.txt`
environment installed:

```text
python -m tools.asr_quality_benchmark --reference /private/ai_reference.srt --reference-status ai-unverified --reference-origin "Existing AI-generated reference; not human checked" --candidate /private/turbo.srt --candidate /private/breeze.srt --output /private/benchmark.json
```

- Chinese characters are counted separately, English words and numerals as
  whole tokens; Unicode punctuation/spacing and case are normalized and the
  offline OpenCC `s2t` converter normalizes Simplified/Traditional Han forms.
  Every comparison uses **exact Levenshtein edit distance**, not a fuzzy
  similarity estimate; output differences are **relative to the stated reference**.
- If `reference-status=ai-unverified`, the report is explicitly
  `AI_REFERENCE_DISAGREEMENT_ONLY`: it contains **no human CER/WER** and
  cannot designate an accuracy winner. This is the correct status for the
  stored Google AI reference and the AI-corrected draft.
- Only an explicitly sourced, **human-listened and corrected** reference
  should use `reference-status=human-verified`. In that case the report
  exposes `han_cer`, `english_wer` and `mixed_unit_error_rate` measured
  against that reference. Human origin is a caller declaration; code cannot
  independently certify real human listening. These rates are **text accuracy
  only**, not exact audio word-alignment accuracy.
- The private JSON report may contain short mismatch snippets, so the program
  refuses report paths inside this public repository and prints **no transcript**
  or mismatch text to standard output. The unit tests use synthetic material
  only. The source files remain owner-only. For 30-minute material, split into
  independently verified reference segments (the exact DP has a bounded
  8,000-unit limit per comparison), and do not present a fake overall rate.
- Do not automatically overwrite the existing 24-cue approved SRT with a
  different 23-cue model run solely on the basis of AI agreement.

If the assistant's private runtime lacks the OpenCC package, explicitly pass `--han-conversion none` for a **Unicode-only preliminary report**. That report must state that Simplified/Traditional differences may be overcounted; do not compare its percentages directly with an OpenCC-normalized benchmark.


## Optional Qwen3-ASR 1.7B private CPU comparison

The existing **single owner Issue #1** accepts an explicitly authorized research request:

```text
/srt-run {"transport":"signed-url","output_public_key":"rsa-n:<FRESH_PUBLIC_RSA_2048_MODULUS>","model":"qwen3-asr-1.7b","alignment":"off"}
```

The signed ciphertext is prepared, submitted and cleaned using **the same** RSA-OAEP/AES-GCM signed-link private audio exchange as the production Turbo SRT workflow. The runner uses a previously synthetic-verified pinned pure-C OpenBLAS backend, `antirez/qwen-asr@924694251d9e0f18e5d86bbd06aa3ab5f870002d`, with the open Qwen/Qwen3-ASR-1.7B weights. The returned **encrypted JSON contains text only**, with `"timings":"none"`, `"reference_status":"ai-unverified"`; it **must never be presented as a timestamped SRT or a verified human transcript**.

This optional candidate does not change the default `large-v3-turbo` production setting or the saved private 24-cue SRT. It does not call paid or metered hosted AI inference and must not consume the user's Windows resources. The assistant must decrypt the result privately and compare with the existing private text using `tools/asr_quality_benchmark.py`, retaining provenance; no plaintext Qwen output or model disagreement may be committed to the public repository or issue.

Model and engine/source licenses: [Qwen3-ASR-1.7B Apache-2.0](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) and [antirez/qwen-asr MIT](https://github.com/antirez/qwen-asr). **Real protected audio CPU test PASS:** [run 45014350294](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45014350294), pinned C build 4.32s, weights download 170.06s, inference 43.67s, 626 transcript characters, authenticated encrypted private return. This is text-only with no word-timed SRT; no human audio reference or verified WER. Production Turbo is unchanged.


## Optional Fun-ASR-Nano-2512 official GGUF CPU contender

The existing owner-only Issue #1 also accepts the explicit optional research selection `model:"fun-asr-nano-2512"` with `transport:"signed-url"`. It uses the same short-lived RSA-OAEP/AES-256-GCM **ciphertext-only** path as the existing Turbo and Qwen1.7B workflows; no plain recordings, transcripts, SRT text or decryption keys go to this public repository or issue.

The runtime is pinned to official [modelscope/FunASR](https://github.com/modelscope/FunASR/tree/68aa96ddb96b6ec9b2f50923b9c55d223ef483af/runtime/llama.cpp) at `68aa96ddb96b6ec9b2f50923b9c55d223ef483af`, whose standalone CMake project pins `llama.cpp` source. The build uses standard GitHub Ubuntu CPU, OpenBLAS where supported, and the official GGUF conversion/download script for `fun-asr-nano` Q8 decoder plus F16 encoder and FSMN VAD. The official [Fun-ASR-Nano-2512 model](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512) advertises Apache-2.0 model weights; separate runtime/third-party dependencies still require applicable license review.

The runner returns **encrypted JSON** with the raw transcription and, **only when structural validation actually passes**, a *candidate* SRT made of VAD-based speech segments. `timings:"vad_segment_timestamps_not_word_aligned"` never claims reliable word-level timestamps; otherwise `timings:"none"` and `srt:null`. This candidate must not automatically replace the private 24-cue Whisper Turbo+Smart2 official SRT. Human-scored CER/WER remains unavailable without an audio-listened reference. Official `--srt` output is a preliminary segmentation aid, not proof of alignment quality. **Real protected audio CPU test PASS:** [run 45015631110](https://github.com/rayray12zx3-sys/subtitle-srt-toolkit/actions/runs/45015631110), official FunASR CMake build 138.22s, weights download 10.71s, ASR 7.76s, 603 transcript characters, **only two validated coarse VAD SRT segments** spanning approximately 0–30s and 30–58.17s. Those subtitles do NOT satisfy fine-grained teaching-video subtitle timing, and are never auto-promoted. Production default remains `large-v3-turbo`. No new GitHub Issue or repository is needed.


## Human-audio reference verification (private, reviewed cue baseline)

A user-usable **private, offline review workbench** is held in the owner's existing subtitle evaluation Drive folder, not in this public repository. It embeds the owner-approved 24-cue draft, original-WAV-derived waveform and locally converted MP3 playback; a reviewer can play each cue, correct the text and start/end times, mark **text** and **cue-boundary** confirmations independently, export an editable private JSON progress file and later reimport it. The workbench marks **0 of 24 cues reviewed by default** and never claims to be a verified transcript. If the compressed preview is unclear, listen to the private original WAV.

The code-only [`tools/gold_reference_review.py`](tools/gold_reference_review.py) enforces a separate offline gate using the SHA-256 of both the **private original recording** and **private original SRT**. Do not place those files, the exported JSON, a gold SRT, or any reviewer identity in this public repository or its Issues/logs.

When using a private assistant workspace with original audio and the approved SRT:

```text
python -m tools.gold_reference_review prepare --audio "/private/original.wav" --source-srt "/private/approved.srt" --out "/private/review.json"
python -m tools.gold_reference_review check --audio "/private/original.wav" --source-srt "/private/approved.srt" --review "/private/review.json"
python -m tools.gold_reference_review finalize --audio "/private/original.wav" --source-srt "/private/approved.srt" --review "/private/review.json" --out "/private/human_gold.srt" --audit-out "/private/human_gold_audit.json"
```

The browser generates a draft matching the `prepare` schema. The reviewer must listen, enter their name or pseudonym, explicitly attest to source-audio listening and confirm each cue. The CLI independently checks both original SHA-256 hashes, cue ordering, edited text, non-overlapping boundaries, source audio duration, time review flags, attestation and UTC timestamp. **No gold file can be exported with a partial review.** `finalize --text-only` allows a self-attested *text-only* reference when all text cues are confirmed but cue times have not been reviewed; this never reports word-level timestamp accuracy. All exports remain private and use restrictive file permissions.

Only after human-confirmed reference provenance is established may [`tools/asr_quality_benchmark.py`](tools/asr_quality_benchmark.py) be used in `--reference-status human-verified` mode **with `--human-audit /private/human_gold_audit.json`**, which must match the reference SHA-256 and confirm every text cue, to compute Han-character CER and English-word WER for any candidate; the resulting rates remain conditional on the supplied reviewer declaration, which software cannot independently substantiate. **The project currently has no completed human-listened gold reference.** Existing AI-to-AI comparisons and Qwen/Whisper boundary disagreement remain diagnostics, not human quality truth.

For cue timing comparison, `cue_time_disagreement(reference_srt, candidate_srt)` reports median/P95/max absolute movement **only when normalized cue text and segmentation match one-to-one**. Otherwise it returns `NOT_COMPARABLE_SEGMENTATION` or `NOT_COMPARABLE_TRANSCRIPT_OR_SEGMENTATION` instead of fabricating a timing error for 22-versus-24 cues. Cue-boundary comparisons are not word-level alignment scores.

## Preferred user workflow: Premiere Pro-exported SRT (2026-11-23)

**Premiere Pro is the default human editor; the HTML waveform workbench is optional legacy tooling, not a prerequisite.** Edit the AI-generated SRT against audio in Premiere, export it, and pass the SRT to the private assistant runtime. Splitting/merging cues (e.g. 24 AI cues to 31 editor cues) and correcting actual words are both valid.

The offline `tools/premiere_reference.py` has two separate commands:

```text
python -m tools.premiere_reference check --audio /private/original.wav --source-srt /private/approved_ai.srt --edited-srt /private/premiere_corrected.srt

# ONLY after the editor explicitly confirms listening to the recording and verifying ALL text and ALL cue boundaries:
python -m tools.premiere_reference attest --audio /private/original.wav --source-srt /private/approved_ai.srt --edited-srt /private/premiere_corrected.srt --reviewer "Editor alias" --completed-utc "2026-11-23T03:00:00Z" --confirm-full-listening --audit-out /private/premiere_audit.json
```

`check` verifies source and edited SRT structure, ordered timestamps and source-audio duration, allowing different cue counts. It never claims human gold, even when the SRT was exported from Premiere. `attest` is a **distinct, explicitly human-authorized** action requiring an editor alias, UTC completion time and all-cue listening confirmation. Its private JSON audit is SHA-256-bound to the **existing corrected SRT** and is accepted by `asr_quality_benchmark.py --reference-status human-verified --human-audit ...`. Neither operation rewrites, duplicates or publicly exposes the private SRT.

Structural validation or an editor-export filename does **not** imply actual human listening. Human self-attestation is not independently verified by software; SRT cue boundaries are not word-level timestamps. Never commit private audio, transcripts, hashes or reviewer identity to public GitHub, PR, Issue or CI logs. The original 24-cue AI SRT stays unchanged. The legacy HTML JSON flow remains available, but optional.
