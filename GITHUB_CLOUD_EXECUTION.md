# GitHub-hosted subtitle production — mandatory target architecture

## Hard requirements

1. **GitHub-hosted** standard Linux runner in this **public** repository performs actual Whisper/faster-whisper audio-to-SRT inference. The user's Windows/CPU/GPU/local agents are **not authorized** execution targets.
2. No metered/token/request/minute-limited hosted AI inference service. Use only open-source model weights (download static files if needed) and local inference **inside the ephemeral GitHub runner**. Do not use paid/larger runners.
3. GitHub repo stays **code-only**, and all real inputs/outputs must stay private. Never commit audio, subtitles, hashes of private media, user data, or credentials, and do not use public issue comments, pull requests, dispatch inputs or logs as transfer channels.
4. On success, validate fresh SRT against real audio with `delivery_gate.py`, then privately return/download the SRT into the current ChatGPT conversation. Only actual successful delivery counts as completed.
5. Otherwise return **BLOCKED / NOT COMPLETED** with the concrete missing transfer/execution step. A code-only CI PASS does not count.

## Execution architecture

- **Ingress (not yet implemented):** acquire private short-lived, authenticated access to the specific user-uploaded audio at runtime. The URL/credentials must be provided securely to Actions (e.g. a private secret or verified identity integration) and must never appear as a public workflow_dispatch input or in logs. The connector currently provides NO verified means of transferring this conversation's private audio to an Actions runner. Do not expose it via public links.
- **Compute:** standard `ubuntu-latest` public-repository runner. Install `requirements.txt` and, as a separate download step, retrieve verified *static open-source model weights*. Downloading weights is not a hosted model inference call and can be cached, although hosting, bandwidth and cache capacity are subject to platform limits. Run `transcribe.py AUDIO --model-dir MODEL ... --output OUTPUT.srt` with the offline inference mode enabled.
- **Validation:** `delivery_gate.py AUDIO OUTPUT.srt` must pass for non-empty chronological subtitles inside the actual audio duration. Manual speech accuracy verification is a separate gate and cannot be inferred from structural validity.
- **Egress (not yet implemented):** private authenticated transfer of the validated SRT out of the runner to the chat attachment workspace. Do NOT use normal downloadable GitHub Actions artifacts in this public repo for unencrypted SRT: readers of a public repo can access those artifacts. Do not print transcript content to logs.
- **Cleanup:** delete decrypted intermediate audio and output on runner termination; do not use storage caches for media or subtitle data.

## Current implementation status

- **Implemented:** reusable offline `transcribe.py`, structural validation, synthetic CI tests.
- **Missing:** production GitHub-hosted media transcription workflow, verified safe audio ingress, verified safe SRT egress to chat, full audio inference acceptance.
- The earlier Windows/local-first README walkthrough is **not an authorized project execution path**. It remains as legacy CLI usage illustration only; it must not be used as the production design.

## Why public artifacts are not accepted

GitHub documents that anyone signed in with repository read access can download workflow artifacts. Public-repository readers consequently must not be given an unencrypted SRT artifact. Encrypted outputs would require verified key custody and a private delivery mechanism; this project has not implemented those capabilities.

GitHub's public standard GitHub-hosted runner usage is documented as free and unlimited **for billing minutes**, but individual workflow execution, concurrency, bandwidth, storage, abuse protections and service availability are limited. This fits the rule against limited free *AI inference quotas*, not a requirement for unlimited physical compute resources.
