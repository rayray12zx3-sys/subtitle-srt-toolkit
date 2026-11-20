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
