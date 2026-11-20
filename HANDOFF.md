# HANDOFF — subtitle-srt-toolkit

## Current direction (confirmed 2026-11-20)

- Public GitHub repository contains **only code**.
- The subtitle generation path must **never consume a limited free AI-service quota**, subscription credits, or paid inference requests.
- Use a pre-downloaded local Whisper/faster-whisper model on CPU/GPU, with offline OpenCC conversion.
- **No** Google AI Studio/Gemini, OpenAI API, Hugging Face Inference API, or other cloud AI transcription.
- GitHub public standard-runner Actions may run code-only unit tests (free minutes per GitHub documentation, subject to job and fair-use limits). No personal media in CI.
- Model not present => fail without contacting the network.

## Verified and not verified

- **Static guard implemented:** local model-path requirement, offline environment variables, no API service calls in the transcription tool.
- **CI:** See Actions for results of the latest commit; do not claim pass before inspecting it.
- **Unverified:** real end-to-end local model transcription on the user's Windows machine, manual word-level verification, and direct delivery of locally generated SRT back to ChatGPT.
- No always-on personal computer or automatic cloud processing is assumed.

## Next scoped milestone

Verify a real audio-to-SRT run with local model files, examine accuracy, and design a private return path to the chat that uses no metered/free-tier AI quota. Keep the private audio and SRT out of the public repository. Do not add another service or repository unless necessary.

The user's newer hard limit supersedes any earlier plan to use Google AI Studio for transcription.

## 2026-11-20 — private-audio comparison attempt (BLOCKED)

- The ChatGPT execution environment could read the private uploaded WAV and existing SRT, but had no `faster_whisper`, `ctranslate2`, `opencc`, or CTranslate2 Whisper model weights installed. Its network could not resolve the public model-download domain. No hosted inference or metered API was used.
- This environment therefore produced **no new offline transcript** and **no model-to-model accuracy comparison**. Do not misstate the existing seven passing code unit tests as evidence of end-to-end transcription.
- The existing SRT was inspected *outside GitHub* for format/timing only. Source audio, filename, transcript and SRT text were **not** submitted to the public repository.
- Next action: in a machine with a pre-downloaded, locally available CTranslate2 Whisper model and project-local Python packages, run the private audio through `transcribe.py --model-dir <local-path>`; compare the generated SRT to the baseline off-repository. Keep the source and artifacts private.

## Mandatory completion condition (2026-11-20)

- **NO VALIDATED SRT DELIVERED TO USER => TASK NOT COMPLETED.** This is a hard requirement, not advice.
- Implemented: `delivery_gate.py` fails closed on missing, empty, unparseable, overlapping or out-of-range SRT. `transcribe.py` validates a temporary file before publishing the output and otherwise returns `BLOCKED`.
- A valid file yields only `OUTPUT_VALIDATED_NOT_YET_DELIVERED`; an executor must separately verify a real, accessible attachment/link in the conversation before declaring `COMPLETED`.
- Do not substitute old SRT, code checks, issues, or progress messages for a newly produced requested subtitle artifact. No finite free-tier AI quotas, paid models, hosted inference, or audio in this public GitHub repository.
- The private uploaded audio's **new offline model transcription** remains BLOCKED because this current container lacks model weights and cannot download them. A previously delivered SRT exists but must not be represented as the output of this offline pipeline.
- Next acceptance: real offline model run with private audio and end-to-end SRT delivery. Follow [DELIVERY_GATE.md](DELIVERY_GATE.md).

## 2026-11-20 — user correction: GitHub cloud ONLY (supersedes local execution assumption)

- **Confirmed requirement:** Speech-to-text inference must run on **GitHub-hosted standard runner** in GitHub Actions, not on the user's Windows PC, local workstation, or self-hosted runner. The user never authorized use of personal local compute. Earlier local-Windows routing was an assistant mistake and is superseded.
- Public repo **contains only code and documentation**. No WAV, SRT, transcript, private URL, secret, input payload, or real-media checksum may be committed, included in public workflow inputs, printed to logs, or uploaded as public Actions artifacts.
- **Cost constraint:** Use only free standard GitHub-hosted runners on the PUBLIC repository and open-source Whisper model weights for runner-local inference; no quota-limited free AI inference, token/minute/request API, paid GPU runners, or subscription credits. GitHub's free standard public runner usage is subject to per-job/platform limits and terms, not guaranteed infinite capacity.
- The runner can explicitly download **static open-source model files** before execution, then execute faster-whisper on the GitHub-hosted Ubuntu runner without using an inference API. The current program's fail-closed `--model-dir` rule remains in force at inference time.
- **Critical unimplemented prerequisites:** private temporary ingress of audio to the GitHub runner, and private egress of the validated SRT to the chat, without disclosing either on the public repository or its artifacts/logs. GitHub manual workflow inputs should NOT contain a public/private media URL or sensitive data. Do not attempt to bypass these constraints with exposed media links.
- Full task remains **BLOCKED / NOT COMPLETED** until an actual WAV is handled by the Github-hosted runner and the newly generated validated SRT is delivered in the conversation. Do not repeat Windows setup instructions or suggest self-hosted/local fallback without explicit fresh approval.
- Current code-only GitHub Actions unit test success does not satisfy production transcription. See [GITHUB_CLOUD_EXECUTION.md](GITHUB_CLOUD_EXECUTION.md).
