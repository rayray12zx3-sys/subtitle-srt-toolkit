"""Synthetic encrypted packet selection through the production runner helper."""
import unittest
from unittest.mock import Mock

from cryptography.hazmat.primitives.asymmetric import rsa
from tools.cloud_handshake import INPUT_AAD, pack, wait_for_media


class CloudHandshakeTests(unittest.TestCase):
    def test_bad_or_expired_candidate_cannot_mask_a_valid_candidate(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        valid = pack(b"synthetic test input", private.public_key(), INPUT_AAD)
        unavailable = Mock(side_effect=OSError("synthetic transport failure"))
        corrupt = Mock(return_value=valid[:-1])
        accepted = Mock(return_value=valid)
        unnecessary = Mock(side_effect=AssertionError("Already authenticated"))
        payload = wait_for_media(lambda: (unavailable, corrupt, accepted, unnecessary), private, 2)
        self.assertEqual(payload, b"synthetic test input")
        unavailable.assert_called_once_with()
        corrupt.assert_called_once_with()
        accepted.assert_called_once_with()
        unnecessary.assert_not_called()
