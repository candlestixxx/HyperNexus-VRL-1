"""Schnorr zero-knowledge proof-of-possession over RFC 3526 group 14.

Proves knowledge of a secret `x` given only its public key `Y = G^x mod P`,
without revealing `x`. VRL-4 GAP uses this so a device proves possession of its
key in zero-knowledge — the secret never crosses the wire.

    sign:    k <-R- [1, q), R = G^k, e = H(R || m) mod q, s = k - x*e mod q
    verify:  R' = G^s * Y^e, accept iff H(R' || m) == e
"""
from __future__ import annotations

import hashlib
import secrets

from core.threshold import G, P, Q

_PKEY_BYTES = 256  # P is 2048-bit


def secret_from_seed(seed: bytes) -> int:
    """Deterministically map a 256-bit seed into Z_q (nonzero)."""
    h = hashlib.sha256(b"vrl4-schnorr:" + seed).digest()
    return (int.from_bytes(h, "big") % (Q - 1)) + 1


def public_key(secret: int) -> int:
    return pow(G, secret, P)


def keypair(seed: bytes) -> tuple[int, int]:
    """Return (secret, public) from a seed."""
    x = secret_from_seed(seed)
    return x, public_key(x)


def _challenge(r: int, message: bytes) -> int:
    h = hashlib.sha256(r.to_bytes(_PKEY_BYTES, "big") + message).digest()
    return int.from_bytes(h, "big") % Q


def sign(secret: int, message: bytes) -> tuple[int, int]:
    k = secrets.randbelow(Q - 1) + 1
    r = pow(G, k, P)
    e = _challenge(r, message)
    s = (k - secret * e) % Q
    return e, s


def verify(public: int, message: bytes, e: int, s: int) -> bool:
    r = (pow(G, s, P) * pow(public, e, P)) % P
    return _challenge(r, message) == e
