"""Owner-only GitHub Issue comment dispatcher; no private media in GitHub.

Only /srt-check and /srt-run with strictly validated public metadata are valid.
GitHub Actions must enforce event origin *before* calling this parser, too.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re

REPO = "rayray12zx3-sys/subtitle-srt-toolkit"
OWNER = "rayray12zx3-sys"
ISSUE_NUMBER = 1
DRIVE_ID_RE = re.compile(r"[A-Za-z0-9_-]{15,100}\Z", re.ASCII)
RSA_N_RE = re.compile(r"rsa-n:([A-Za-z0-9_-]{342})\Z", re.ASCII)
MODELS = frozenset(("large-v3-turbo", "small", "tiny", "base", "medium",
                    "large-v3", "breeze-asr-25", "qwen3-asr-1.7b",
                    "fun-asr-nano-2512"))
LANGUAGES = frozenset(("auto", "zh", "en"))
ALIGNMENTS = frozenset(("off", "qwen"))
ALLOWED = frozenset(("transport", "encrypted_drive_file_id", "output_public_key",
                     "model", "language", "alignment", "chunk_seconds"))
REQUIRED = frozenset(("output_public_key",))


def _object_no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _check_public_key(value):
    if not isinstance(value, str):
        raise ValueError("Return key must be public RSA modulus")
    match = RSA_N_RE.fullmatch(value)
    if match is None:
        raise ValueError("Expected compact RSA-2048 public modulus")
    encoded = match.group(1)
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except Exception as exc:
        raise ValueError("Malformed RSA public modulus") from exc
    if len(raw) != 256 or raw[0] < 128 or not (raw[-1] & 1):
        raise ValueError("Invalid RSA-2048 public modulus")
    return value


def validate_command(body):
    if body == "/srt-check":
        return {"smoke": "true"}
    if isinstance(body, str) and body.startswith("/srt-probe "):
        from tools.signed_cipher_transport import validate_signed_url
        return {"smoke": "probe", "probe_url": validate_signed_url(body[len("/srt-probe "):])}
    if not isinstance(body, str) or not body.startswith("/srt-run "):
        raise ValueError("Unsupported command")
    if len(body) > 1800 or "\r" in body or "\n" in body:
        raise ValueError("Command too long or multiline")
    try:
        data = json.loads(body[len("/srt-run "):],
                          object_pairs_hook=_object_no_duplicate_keys)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid JSON command") from exc
    if not isinstance(data, dict) or not REQUIRED <= data.keys() or data.keys() - ALLOWED:
        raise ValueError("Missing or unknown input fields")
    transport = data.get("transport", "drive")
    if transport not in ("drive", "signed-url"):
        raise ValueError("Invalid ciphertext transport")
    if transport == "drive":
        drive_id = data.get("encrypted_drive_file_id")
        if not isinstance(drive_id, str) or not DRIVE_ID_RE.fullmatch(drive_id):
            raise ValueError("Invalid encrypted-only Drive file ID")
    else:
        if "encrypted_drive_file_id" in data:
            raise ValueError("Signed URL transport must not include Drive ID")
        drive_id = ""
    output_key = _check_public_key(data["output_public_key"])
    model = data.get("model", "large-v3-turbo")
    language = data.get("language", "auto")
    alignment = data.get("alignment", "off")
    chunk_seconds = data.get("chunk_seconds", 600)
    if model not in MODELS or language not in LANGUAGES or alignment not in ALIGNMENTS:
        raise ValueError("Unsupported transcription option")
    if model in ("qwen3-asr-1.7b", "fun-asr-nano-2512") and (
            language != "auto" or alignment != "off"):
        raise ValueError("Text benchmark candidates require language=auto and alignment=off")
    if type(chunk_seconds) is not int or chunk_seconds not in (0, *range(60, 1801)):
        raise ValueError("Invalid chunk seconds")
    return {
        "smoke": "false",
        "transport": transport,
        "encrypted_drive_file_id": drive_id,
        "output_public_key": output_key,
        "model": model,
        "language": language,
        "alignment": alignment,
        "chunk_seconds": str(chunk_seconds),
    }


def validate_event(event):
    if not isinstance(event, dict):
        raise ValueError("Invalid GitHub event")
    issue = event.get("issue")
    comment = event.get("comment")
    repo = event.get("repository")
    if (event.get("action") != "created"
            or not isinstance(repo, dict)
            or repo.get("full_name") != REPO
            or not isinstance(issue, dict)
            or issue.get("number") != ISSUE_NUMBER
            or issue.get("pull_request") is not None
            or issue.get("state") != "open"
            or not isinstance(issue.get("user"), dict)
            or issue["user"].get("login") != OWNER
            or not isinstance(comment, dict)
            or not isinstance(comment.get("user"), dict)
            or comment["user"].get("login") != OWNER):
        raise ValueError("Unauthorized comment source")
    return validate_command(comment.get("body"))


def main():
    parser = argparse.ArgumentParser(description="Parse owner-only GitHub issue dispatch")
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_event(json.loads(args.event.read_text("utf-8")))
    except (ValueError, OSError, TypeError) as exc:
        # Only fixed validation messages, never log the original command / media.
        parser.error(str(exc))
    with args.output.open("a", encoding="utf-8") as handle:
        for key, value in result.items():
            handle.write(f"{key}={value}\n")
    print("OWNER_COMMENT_DISPATCH_VALIDATED", flush=True)


if __name__ == "__main__":
    main()
