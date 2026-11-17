"""Feldman verifiable secret sharing (VSS) for threshold credential release.

Goal (ROADMAP Milestone 4): shard a credential so no single node holds the
whole secret — any `t` of `n` shares reconstruct it, and every share is
publicly verifiable against commitments, so a corrupted share or a dishonest
dealer is detected *before* release.

Parameters (locked, reference implementation):
- P: RFC 3526 group 14 — a 2048-bit safe prime (P = 2Q + 1, Q prime).
- Q: (P - 1) / 2. Shamir runs over GF(Q).
- G: 2 mod P, a generator of the order-Q subgroup (2 is a quadratic residue
  mod P, so it lives in the Q-order subgroup).

Feldman commitments are C_j = G^{a_j} mod P for each coefficient a_j. A share
f(i) verifies iff G^{f(i)} == prod_j C_j^{i^j} mod P. Reconstruction is
Lagrange interpolation over GF(Q) evaluated at x=0.

Honest scope: this is the standalone VSS primitive. Multi-node distribution,
storage, and release orchestration belong to the BFT milestone (Milestone 5).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

# RFC 3526 group 14, 2048-bit MODP (safe prime). Presented as 16-hex-digit words
# exactly as in the RFC so the constant is auditable against the standard.
_P_WORDS = [
    "FFFFFFFFFFFFFFFF", "C90FDAA22168C234", "C4C6628B80DC1CD1",
    "29024E088A67CC74", "020BBEA63B139B22", "514A08798E3404DD",
    "EF9519B3CD3A431B", "302B0A6DF25F1437", "4FE1356D6D51C245",
    "E485B576625E7EC6", "F44C42E9A637ED6B", "0BFF5CB6F406B7ED",
    "EE386BFB5A899FA5", "AE9F24117C4B1FE6", "49286651ECE45B3D",
    "C2007CB8A163BF05", "98DA48361C55D39A", "69163FA8FD24CF5F",
    "83655D23DCA3AD96", "1C62F356208552BB", "9ED529077096966D",
    "670C354E4ABC9804", "F1746C08CA18217C", "32905E462E36CE3B",
    "E39E772C180E8603", "9B2783A2EC07A28F", "B5C55DF06F4C52C9",
    "DE2BCBF695581718", "3995497CEA956AE5", "15D2261898FA0510",
    "15728E5A8AACAA68", "FFFFFFFFFFFFFFFF",
]
P = int("".join(_P_WORDS), 16)
Q = (P - 1) // 2
G = 2

# 256-bit credentials are the project norm; allow up to ~1016 bits (< Q).
_MAX_SECRET_BYTES = 127


@dataclass(frozen=True)
class ThresholdShares:
    n: int
    t: int
    shares: list[tuple[int, int]]  # (x=i, y=f(i)) for i in 1..n
    commitments: list[int]         # [G^a_0, ..., G^{a_{t-1}}]
    secret_len: int                # original byte length (for exact round-trip)


def _eval_poly(coeffs: list[int], x: int, q: int = Q) -> int:
    """Horner evaluation of sum coeffs[j] * x^j mod q."""
    acc = 0
    for c in reversed(coeffs):
        acc = (acc * x + c) % q
    return acc


def split_secret(secret: bytes, n: int, t: int) -> ThresholdShares:
    """Shard `secret` into n Shamir shares with threshold t (Feldman VSS)."""
    if not (1 <= t <= n):
        raise ValueError("require 1 <= t <= n")
    if not 1 <= len(secret) <= _MAX_SECRET_BYTES:
        raise ValueError(f"secret must be 1..{_MAX_SECRET_BYTES} bytes")
    s = int.from_bytes(secret, "big")
    if not 1 <= s < Q:
        raise ValueError("secret must encode to an element of [1, Q-1]")
    # Degree-(t-1) polynomial: f(x) = s + a_1 x + ... + a_{t-1} x^{t-1}.
    coeffs = [s] + [secrets.randbelow(Q - 1) + 1 for _ in range(t - 1)]
    shares = [(i, _eval_poly(coeffs, i)) for i in range(1, n + 1)]
    commitments = [pow(G, a, P) for a in coeffs]
    return ThresholdShares(n=n, t=t, shares=shares, commitments=commitments,
                           secret_len=len(secret))


def verify_share(share: tuple[int, int], commitments: list[int]) -> bool:
    """Feldman check: G^{f(i)} == prod_j C_j^{i^j} mod P."""
    x, y = share
    lhs = pow(G, y, P)
    rhs = 1
    x_pow = 1  # x^j mod Q (exponents are mod Q in the order-Q subgroup)
    for c in commitments:
        rhs = (rhs * pow(c, x_pow, P)) % P
        x_pow = (x_pow * x) % Q
    return lhs == rhs


def reconstruct(shares: list[tuple[int, int]], t: int, length: int) -> bytes:
    """Recover the secret from any t valid shares (Lagrange at x=0)."""
    if len(shares) < t:
        raise ValueError(f"need at least {t} shares, got {len(shares)}")
    pts = shares[:t]
    secret = 0
    for i, (xi, yi) in enumerate(pts):
        num = 1
        den = 1
        for k, (xk, _) in enumerate(pts):
            if i == k:
                continue
            num = (num * (0 - xk)) % Q
            den = (den * (xi - xk)) % Q
        lagrange = (num * pow(den, -1, Q)) % Q
        secret = (secret + yi * lagrange) % Q
    return secret.to_bytes(length, "big")
