"""Schnorr ring signature (AOS): correctness + security properties."""
import pytest

from core.ring_sig import keygen, sign, verify

MESSAGE = b"ring-membership-proof"


@pytest.fixture(scope="module")
def ring():
    # 4 members; keep the secrets so tests can sign with any of them.
    members = [keygen() for _ in range(4)]
    return [x for x, _ in members], [y for _, y in members]


def test_ring_signature_verifies(ring):
    secrets, pubs = ring
    sig = sign(MESSAGE, pubs, signer_index=2, secret=secrets[2])
    assert verify(MESSAGE, pubs, sig) is True


def test_any_member_can_sign_anonymously(ring):
    secrets, pubs = ring
    # Every member's signature verifies against the same ring.
    for i in range(len(pubs)):
        sig = sign(MESSAGE, pubs, signer_index=i, secret=secrets[i])
        assert verify(MESSAGE, pubs, sig) is True


def test_wrong_message_fails(ring):
    secrets, pubs = ring
    sig = sign(MESSAGE, pubs, signer_index=0, secret=secrets[0])
    assert verify(b"different-message", pubs, sig) is False


def test_wrong_secret_for_claimed_index_fails(ring):
    secrets, pubs = ring
    # Sign claiming index 0 but using index 1's secret -> ring does not close.
    sig = sign(MESSAGE, pubs, signer_index=0, secret=secrets[1])
    assert verify(MESSAGE, pubs, sig) is False


def test_non_member_key_cannot_sign(ring):
    secrets, pubs = ring
    outsider_x, _ = keygen()  # not in the ring
    # The ring only contains pubs; signing with an outsider secret must fail.
    sig = sign(MESSAGE, pubs, signer_index=0, secret=outsider_x)
    assert verify(MESSAGE, pubs, sig) is False


def test_tampered_signature_fails(ring):
    secrets, pubs = ring
    sig = sign(MESSAGE, pubs, signer_index=1, secret=secrets[1])
    tampered = {"c0": sig["c0"], "s": list(sig["s"])}
    tampered["s"][0] = (tampered["s"][0] + 1) % (2**64)
    assert verify(MESSAGE, pubs, tampered) is False


def test_wrong_ring_fails(ring):
    secrets, pubs = ring
    other_secrets, other_pubs = [keygen() for _ in range(3)], []
    other_pubs = [y for _, y in zip(other_secrets, other_pubs)]
    sig = sign(MESSAGE, pubs, signer_index=0, secret=secrets[0])
    assert verify(MESSAGE, other_pubs, sig) is False
