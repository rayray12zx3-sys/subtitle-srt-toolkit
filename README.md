# subtitle-srt-toolkit

Free, open-source audio-to-SRT subtitles using [faster-whisper](https://github.com/SYSTRAN/faster-whisper).

**Code only:** The public repository must never contain user audio, videos, transcripts, subtitles, output artifacts, credentials, or model weights. GitHub Actions runs source tests only; it does **not** transcribe private recordings. Keep any audio and generated SRT outside this repository.

## Usage

Python 3.10+; the model downloads the first time it runs. CUDA GPU optional.

```bash
python -m pip install -r requirements.txt
python transcribe.py "recording.wav" --model large-v3 --language zh --output "recording.srt"
```

Remove `--language zh` to autodetect language. Add `--device cpu --compute-type int8` for CPU transcription. `--keep-punctuation` retains terminal punctuation.

The tool generates word-timestamped SRT segments and conservatively removes terminal punctuation. **ASR output is not proof of a fully corrected transcript**: manually verify words and timestamps against audio before claiming it is proofread. `--language zh` does not guarantee Traditional Chinese characters; inspect or convert carefully without changing spoken words.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Privacy

Do not put media, SRT, or transcript content into the public GitHub repository, GitHub issues, PRs, CI logs, artifacts, or releases. `.gitignore` is an additional guard, not a complete privacy guarantee.
