"""Pure synthetic safety tests: signed ciphertext URLs and GitHub owner packets."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
import json
from urllib.parse import quote

from tools.signed_cipher_transport import (
    validate_signed_url, matching_packet_urls, publish_runner_public_key,
)

NOW = datetime(2026, 11, 22, 8, 0, tzinfo=timezone.utc)
RUN = 44996711609
BASE = "https://sdmntprkoreacentral.oaiusercontent.com/files/" + (
    "00000000-a56c-8206-81a8-2dc7d5113e09"
) + "/raw"


def signed_url(minutes=5, base=BASE, extra=""):
    exp = (NOW + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")
    return base + "?se=" + quote(exp) + "&sp=r&sr=b&sig=synthetic" + extra


class SignedCipherTransportTests(unittest.TestCase):
    def test_valid_temporary_url(self):
        url = signed_url()
        self.assertEqual(validate_signed_url(url, now=NOW), url)

    def test_expired_or_long_lived_is_rejected(self):
        for m in (-1, 0, 21, 90):
            with self.subTest(minutes=m), self.assertRaises(ValueError):
                validate_signed_url(signed_url(minutes=m), now=NOW)

    def test_https_signed_domain_only(self):
        unsafe = (
            "https://evil.com/files/00000000-a56c-8206-81a8-2dc7d5113e09/raw",
            "http://sdmntprkoreacentral.oaiusercontent.com/files/00000000-a56c-8206-81a8-2dc7d5113e09/raw",
            "https://sdmntprkoreacentral.oaiusercontent.com.evil.com/files/00000000-a56c-8206-81a8-2dc7d5113e09/raw",
            "https://sdmntprkoreacentral.oaiusercontent.com/private/audio.wav",
            "https://example.com/",
        )
        for path in unsafe:
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_signed_url(signed_url(base=path), now=NOW)

    def test_no_write_scopes_or_unsigned_objects(self):
        for url in (signed_url().replace("sp=r", "sp=w"),
                    signed_url().replace("sr=b", "sr=f"),
                    BASE, signed_url() + "#fragment"):
            with self.subTest(url=url[:65]), self.assertRaises(ValueError):
                validate_signed_url(url, now=NOW)

    def test_only_owner_matching_run_id(self):
        url = signed_url()
        comments = [
            {"id": 10, "user": {"login": "random"}, "body": f"/srt-packet {RUN} {url}"},
            {"id": 11, "user": {"login": "rayray12zx3-sys"}, "body": f"/srt-packet {RUN+1} {url}"},
            {"id": 12, "user": {"login": "rayray12zx3-sys"}, "body": f"/srt-packet {RUN} {url}"},
            {"id": 13, "user": {"login": "rayray12zx3-sys"}, "body": "random comment"},
            {"id": 14, "user": {"login": "rayray12zx3-sys"}, "body": f"/srt-packet {RUN} https://evil.com"},
        ]
        self.assertEqual(matching_packet_urls(comments, RUN, now=NOW), [url])

    def test_public_key_announcement_post_is_public_only(self):
        class Response:
            status = 201
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, *args): return b'{"id":12345}'
        captured = []
        def fake_urlopen(req, timeout=0):
            captured.append(req)
            return Response()
        with patch("tools.signed_cipher_transport.urlopen", side_effect=fake_urlopen):
            self.assertTrue(publish_runner_public_key(RUN, "A"*392, "test-gh-actions-token"))
        self.assertEqual(len(captured), 1)
        request = captured[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.full_url.endswith("/issues/1/comments"))
        body = json.loads(request.data.decode("utf-8"))["body"]
        self.assertEqual(body, f"/srt-key {RUN} " + "A"*392)
        self.assertNotIn("private", body.lower())

    def test_public_key_validation_rejects_secrets(self):
        with self.assertRaises(ValueError):
            publish_runner_public_key(RUN, "-----BEGIN PRIVATE KEY-----", "token")
        with self.assertRaises(ValueError):
            publish_runner_public_key(RUN, "A"*392, "")

    def test_newest_matching_packet_preferred(self):
        url = signed_url()
        newer = signed_url(extra="&scid=another")
        comments = [
            {"id": 100, "user": {"login": "rayray12zx3-sys"}, "body": f"/srt-packet {RUN} {url}"},
            {"id": 101, "user": {"login": "rayray12zx3-sys"}, "body": f"/srt-packet {RUN} {newer}"},
        ]
        self.assertEqual(matching_packet_urls(comments, RUN, now=NOW), [newer, url])


if __name__ == "__main__":
    unittest.main()
