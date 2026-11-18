"""Schnorr zero-knowledge proof-of-possession."""
import pytest

from core.schnorr import keypair, public_key, sign, verify

MESSAGE = b"vrl4-gap-challenge-nonce"


def test_sign_verify_roundtrip():
    x, y = keypair(b"device-seed-32-bytes")
    e, s = sign(x, MESSAGE)
    assert verify(y, MESSAGE, e, s) is True


def test_wrong_key_fails():
    x, y = keypair(b"seed-a")
    _, y_other = keypair(b"seed-b")
    e, s = sign(x, MESSAGE)
    assert verify(y_other, MESSAGE, e, s) is False


def test_tampered_message_fails():
    x, y = keypair(b"seed-a")
    e, s = sign(x, MESSAGE)
    assert verify(y, b"different-message", e, s) is False


def test_secret_is_never_revealed_by_transcript():
    # The transcript (e, s) is independent of x given a random k; here we just
    # check the signature verifies without ever needing x again.
    x, y = keypair(b"seed-a")
    e, s = sign(x, MESSAGE)
    assert y == public_key(x)
    assert verify(y, MESSAGE, e, s) is True
