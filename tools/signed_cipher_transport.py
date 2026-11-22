"""Read ephemeral AES-GCM ciphertext from a signed short-lived OpenAI file URL.

The GitHub runner obtains an owner-authored /srt-packet RUN_ID URL comment
on the existing public control Issue. The URL MUST point to ciphertext, never
to a plaintext recording. Only approved https://sdmntpr*.oaiusercontent.com
signed-file download links can be fetched.

No PAT, user PC, paid browser, or permanent public file sharing is needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

REPO = "rayray12zx3-sys/subtitle-srt-toolkit"
OWNER = "rayray12zx3-sys"
ISSUE = 1
MAX_PACKET_BYTES = 64 * 1024 * 1024 + 512

# The temporary signed file host returned by a connected, owner-authorized file
# fetch operation is constrained to this host family, never arbitrary URLs.
_HOST = re.compile(r"sdmntpr[a-z0-9-]*\.oaiusercontent\.com\Z", re.ASCII)
_PATH = re.compile(r"/files/[0-9a-f-]{36}/raw\Z", re.ASCII)
_PACKET = re.compile(r"/srt-packet ([1-9][0-9]{6,}) (https://\S{30,3600})\Z", re.ASCII)


def validate_signed_url(value: str, now=None) -> str:
    if not isinstance(value, str) or not 50 < len(value) < 3600:
        raise ValueError("Invalid signed ciphertext URL length")
    if any(ch.isspace() for ch in value):
        raise ValueError("Invalid signed ciphertext URL whitespace")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port is not None or parsed.fragment
            or not _HOST.fullmatch(parsed.hostname or "")
            or not _PATH.fullmatch(parsed.path)):
        raise ValueError("Unexpected ciphertext download origin")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if not all(k in query and len(query[k]) == 1 for k in ("se", "sig", "sp", "sr")):
        raise ValueError("Missing URL signed token fields")
    if query["sp"] != ["r"] or query["sr"] != ["b"]:
        raise ValueError("URL is not read-only")
    try:
        expires = datetime.fromisoformat(query["se"][0].replace("Z", "+00:00"))
        reference = now or datetime.now(timezone.utc)
        if expires.tzinfo is None:
            raise ValueError("Unzoned expiry")
        # Reject expired links and unusually long-lived public links.
        if not reference < expires <= reference + timedelta(minutes=20):
            raise ValueError("Expiry is not short lived")
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid ciphertext URL expiration") from exc
    return value


def matching_packet_urls(comments, run_id: int, now=None):
    """Yield newest valid public ciphertext links from real owner comments only."""
    selected = []
    for item in comments:
        if not isinstance(item, dict) or item.get("user", {}).get("login") != OWNER:
            continue
        body = item.get("body")
        match = _PACKET.fullmatch(body) if isinstance(body, str) else None
        if match is None or int(match.group(1)) != run_id:
            continue
        try:
            url = validate_signed_url(match.group(2), now=now)
        except ValueError:
            continue
        selected.append((int(item.get("id", 0)), url))
    return [url for _id, url in sorted(selected, reverse=True)]


def _github_issue_comments(token: str):
    if not token:
        raise RuntimeError("GitHub Actions read-only issue token unavailable")
    # Issue is bounded and reused. Read only the newest 10 pages; inputs are
    # server-authenticated GitHub issue comments, never client-supplied log text.
    found = []
    for page in range(1, 11):
        path = (f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments"
                f"?per_page=100&page={page}")
        req = Request(path, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "User-Agent": "subtitle-srt-toolkit-ephemeral-cipher",
        })
        with urlopen(req, timeout=20) as response:
            chunk = json.load(response)
        if not isinstance(chunk, list):
            raise ValueError("Unexpected GitHub comments response")
        found.extend(chunk)
        if len(chunk) < 100:
            break
    return found


def find_packet_urls(run_id: int, token: str):
    return matching_packet_urls(_github_issue_comments(token), run_id)


def fetch_signed_ciphertext(url: str) -> bytes:
    """Fetch only a signed short-lived encrypted blob, disallow offsite redirects."""
    validate_signed_url(url)
    req = Request(url, headers={"User-Agent": "subtitle-srt-toolkit/1.0"})
    with urlopen(req, timeout=40) as response:
        final_url = response.geturl()
        # Never follow a redirect to an unrelated host or unverified location.
        if urlsplit(final_url).hostname != urlsplit(url).hostname:
            raise ValueError("Unexpected ciphertext redirect")
        cipher = response.read(MAX_PACKET_BYTES + 1)
    if len(cipher) > MAX_PACKET_BYTES or not cipher.startswith(b"SRT2"):
        raise ValueError("Not a bounded SRT2 ciphertext packet")
    return cipher

def publish_runner_public_key(run_id: int, encoded_public_key: str, token: str):
    """Publish only ephemeral RSA PUBLIC key to the single owner control Issue.

    This avoids paid browser access to live (in-progress) GitHub Actions logs.
    The GitHub-provided short-lived GITHUB_TOKEN is scoped to issues:write;
    never publish RSA private keys, plaintext or signed ciphertext links here.
    """
    if (type(run_id) is not int or run_id <= 0
            or not isinstance(encoded_public_key, str)
            or not re.fullmatch(r"[A-Za-z0-9+/=]{380,500}", encoded_public_key)
            or not token):
        raise ValueError("Invalid runner public-key announcement")
    body = f"/srt-key {run_id} {encoded_public_key}"
    url = f"https://api.github.com/repos/{REPO}/issues/{ISSUE}/comments"
    req = Request(url, data=json.dumps({"body": body}).encode("utf-8"),
                  headers={
                      "Accept": "application/vnd.github+json",
                      "Authorization": "Bearer " + token,
                      "Content-Type": "application/json",
                      "User-Agent": "subtitle-srt-toolkit-ephemeral-pubkey",
                  }, method="POST")
    with urlopen(req, timeout=25) as response:
        if response.status != 201:
            raise ValueError("Runner public-key announcement failed")
        metadata = json.load(response)
    if not isinstance(metadata, dict) or not metadata.get("id"):
        raise ValueError("Missing GitHub public-key comment receipt")
    return True
