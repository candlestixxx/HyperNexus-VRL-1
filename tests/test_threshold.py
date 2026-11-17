"""Feldman VSS: threshold credential release (split, verify, reconstruct)."""
import pytest

from core.threshold import G, P, Q, reconstruct, split_secret, verify_share

SECRET = b"vrl1-master-key-32-bytes-minimum!!"  # 33 bytes -> 264 bits (< Q)


def test_group_constants_sane():
    # RFC 3526 group 14 is a safe prime: P = 2Q + 1, and G=2 lives in the
    # order-Q subgroup (2^Q == 1 mod P, order > 2).
    assert P % 2 == 1
    assert Q == (P - 1) // 2
    assert 2 * Q + 1 == P
    assert pow(G, Q, P) == 1
    assert pow(G, 2, P) != 1


def test_threshold_split_verify_reconstruct_roundtrip():
    n, t = 5, 3
    th = split_secret(SECRET, n, t)
    assert th.n == n and th.t == t
    assert len(th.shares) == n
    assert len(th.commitments) == t
    # Every share verifies against the public commitments.
    for share in th.shares:
        assert verify_share(share, th.commitments) is True
    # Any t shares reconstruct the exact original secret.
    assert reconstruct(th.shares[:t], t, th.secret_len) == SECRET
    assert reconstruct(th.shares[-t:], t, th.secret_len) == SECRET
    assert reconstruct([th.shares[0], th.shares[2], th.shares[4]], t,
                       th.secret_len) == SECRET


def test_tampered_share_fails_verification():
    th = split_secret(SECRET, 4, 2)
    x, y = th.shares[0]
    assert verify_share((x, y + 1), th.commitments) is False
    assert verify_share((x + 1, y), th.commitments) is False


def test_insufficient_shares_cannot_reconstruct():
    th = split_secret(SECRET, 4, 3)
    with pytest.raises(ValueError):
        reconstruct(th.shares[:2], 3, th.secret_len)


def test_different_deals_are_independent():
    a = split_secret(SECRET, 3, 2)
    b = split_secret(SECRET, 3, 2)
    # Same secret, same params, but fresh randomness => different commitments.
    assert a.commitments != b.commitments
    # Both reconstruct correctly.
    assert reconstruct(a.shares, 2, a.secret_len) == SECRET
    assert reconstruct(b.shares, 2, b.secret_len) == SECRET


def test_rejects_degenerate_inputs():
    with pytest.raises(ValueError):
        split_secret(SECRET, 2, 3)  # t > n
    with pytest.raises(ValueError):
        split_secret(b"", 3, 2)     # empty secret
    with pytest.raises(ValueError):
        split_secret(b"\x00" * 33, 3, 2)  # secret encodes to 0
