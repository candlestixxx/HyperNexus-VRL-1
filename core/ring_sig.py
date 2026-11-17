"""Zero-knowledge ring membership (Schnorr ring signature, AOS construction).

Proves that a signer holds the private key for *one of* a ring of public keys,
without revealing which one. Built over the same RFC 3526 group 14 used by
`core/threshold.py` (safe prime P = 2Q + 1, generator G of order Q).

Scope note (honest): this is a sound, verifiable ring-membership ZKP using a
Fiat-Shamir challenge over SHA-256. It is NOT the field-native Poseidon
commitment that ROADMAP Milestone 5 targets for SNARK-circuit friendliness —
that remains a dedicated research item. This primitive keeps its own path
(no hash-swap of the existing SHA-256 coordinate/proof flow).
"""
from __future__ import annotations

import hashlib
import secrets

from core.threshold import G, P, Q

_PKEY_BYTES = 256  # P is 2048-bit -> 256-byte fixed-width encoding


def keygen() -> tuple[int, int]:
    """Return (secret x, public y = G^x mod P)."""
    x = secrets.randbelow(Q - 1) + 1
    return x, pow(G, x, P)


def _challenge(message: bytes, ring: list[int], point: int) -> int:
    """Deterministic Fiat-Shamir challenge in [0, 2^256), i.e. inside Z_Q."""
    h = hashlib.sha256()
    h.update(b"VRL1-ring-v1")
    h.update(len(message).to_bytes(8, "big"))
    h.update(message)
    h.update(len(ring).to_bytes(8, "big"))
    for y in ring:
        h.update(y.to_bytes(_PKEY_BYTES, "big"))
    h.update(point.to_bytes(_PKEY_BYTES, "big"))
    return int.from_bytes(h.digest(), "big")


def sign(message: bytes, ring: list[int], signer_index: int, secret: int) -> dict:
    """Produce a ring signature proving `secret` is the key for ring[signer_index]."""
    n = len(ring)
    if not 0 <= signer_index < n:
        raise ValueError("signer_index must be in [0, len(ring))")
    c = [0] * n
    s = [0] * n
    u = secrets.randbelow(Q - 1) + 1
    idx = (signer_index + 1) % n
    # c_{s+1} = H(m, ring, G^u)
    c[idx] = _challenge(message, ring, pow(G, u, P))
    i = idx
    while i != signer_index:
        s[i] = secrets.randbelow(Q - 1) + 1
        # e_i = G^{s_i} * y_i^{c_i}
        e = (pow(G, s[i], P) * pow(ring[i], c[i], P)) % P
        nxt = (i + 1) % n
        c[nxt] = _challenge(message, ring, e)
        i = nxt
    # Close the ring: s_s = u - x_s * c_s  =>  G^{s_s} * y_s^{c_s} = G^u.
    s[signer_index] = (u - secret * c[signer_index]) % Q
    return {"c0": c[0], "s": s}


def verify(message: bytes, ring: list[int], signature: dict) -> bool:
    """Check the ring closure. True iff the signature is valid for this ring."""
    n = len(ring)
    c0 = signature["c0"]
    s = signature["s"]
    if len(s) != n:
        return False
    c = c0
    for i in range(n):
        # e_i = G^{s_i} * y_i^{c_i}
        e = (pow(G, s[i], P) * pow(ring[i], c, P)) % P
        c = _challenge(message, ring, e)
    return c == c0
