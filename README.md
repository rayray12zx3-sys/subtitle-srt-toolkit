# subtitle-srt-toolkit

A **quota-free, offline** subtitle generator based on open-source [faster-whisper](https://github.com/SYSTRAN/faster-whisper). This public GitHub repository contains **tools only**, never personal audio or generated subtitles.

## Mandatory project rule (2026-11-20)

- **Allowed for transcription:** local CPU/GPU inference on an already downloaded open-source Whisper model; offline local text cleanup and Traditional Chinese conversion.
- **Forbidden:** Google AI Studio, Gemini API, OpenAI API, Hugging Face hosted inference, free-tier inference quotas, paid speech services, token/minute/request-based AI services, and any cloud fallback.
- The program **fails closed** when local model files are absent. It will **not** download a model automatically or send audio to an API.
- Model/package acquisition is a **one-time setup**, not hosted inference. Internet service and hosting availability are not mathematically unlimited; running the downloaded model locally has no vendor AI-use quota.
- GitHub Actions may run **code-only tests** on standard runners in this public repository. GitHub documents those standard public-repo minutes as free without deducting a metered allowance, but imposes job limits, service limits and acceptable-use terms. No private audio is ever processed in Actions.
- There is **no automatic audio upload or ChatGPT-return bridge** in this repository. Do not promise a chat-delivered SRT from this code unless a verified private file-transfer and local execution pathway exists.

## First-time setup on Windows (no administrator privileges needed)

1. Install Python 3.10+ (3.11 recommended), then open a terminal in this repository.
2. Create a project-local virtual environment and install the open-source packages once:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. **One time only**, obtain an approved `faster-whisper` CTranslate2 model, for example [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3/tree/main), and place its model files in a local directory outside Git. The directory must include nonempty `model.bin` and `config.json` (keep all other tokenizer/model files too). Do not commit model weights.

## Generate subtitles without cloud AI quota

```powershell
.\.venv\Scripts\python.exe transcribe.py "C:\path\recording.wav" --model-dir "C:\path\faster-whisper-large-v3" --language zh --traditional --device cpu --compute-type int8 --output "C:\path\recording.srt"
```

The output is a local UTF-8-BOM SRT. For a compatible NVIDIA/CUDA setup, use `--device cuda --compute-type float16`; CPU mode works without GPU libraries. Omit `--language zh` to auto-detect, though mixed-language content can still require manual review. `--keep-punctuation` preserves end punctuation.

**Important:** Whisper cannot guarantee perfect word-for-word accuracy or correct all homophones. It provides automatic punctuation cleanup and timestamped recognition, **not** a fully human-verified transcript. Verify sensitive words and timing against the recording before calling it proofread.

## Code tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The unit tests do not download models, make inference requests, or use audio. The public-repository GitHub Actions workflow runs only these tests.

## Privacy

Never upload personal audio, transcripts, subtitles, model weights, login secrets, or generated media to this public GitHub repository, Issues, Pull Requests, Actions logs, artifacts or Releases. `.gitignore` is a safeguard, not a permission system.

For repeatable private transcription: the audio stays on your device, the offline model runs there, and the resulting SRT remains outside this GitHub repository.
