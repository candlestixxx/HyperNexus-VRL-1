"""Reed-Solomon codec: encode/decode, error correction, and fuzzy extractor."""
import pytest

from core.reed_solomon import (ReedSolomonError, rs_correct_msg, rs_encode_msg)


def _corrupt(data: bytes, positions: list[int], values: list[int]) -> bytes:
    b = bytearray(data)
    for p, v in zip(positions, values):
        b[p] ^= v  # v != 0 flips bits at that byte
    return bytes(b)


def test_rs_encode_decode_no_errors():
    nsym = 16
    msg = bytes(range(32))
    codeword = rs_encode_msg(msg, nsym)
    assert rs_correct_msg(codeword, nsym) == msg


def test_rs_corrects_up_to_half_parity_errors():
    nsym = 16  # corrects up to 8 byte errors
    msg = b"hypernexus-vrl4-device-key-32b!!"
    assert len(msg) == 32
    codeword = rs_encode_msg(msg, nsym)
    for t in (1, 4, 8):
        corrupted = _corrupt(codeword, list(range(t)), [0x5A] * t)
        assert rs_correct_msg(corrupted, nsym) == msg


def test_rs_rejects_too_many_errors():
    nsym = 16
    msg = b"hypernexus-vrl4-device-key-32b!!"
    codeword = rs_encode_msg(msg, nsym)
    corrupted = _corrupt(codeword, list(range(9)), [0x5A] * 9)  # 9 > 8
    with pytest.raises(ReedSolomonError):
        rs_correct_msg(corrupted, nsym)


def test_rs_fuzzy_extractor_recovers_from_noise():
    # Code-offset fuzzy extractor using RS as the inner code.
    from core.reed_solomon import rs_correct_msg, rs_encode_msg
    import hashlib, os
    nsym = 16
    key = hashlib.sha256(b"device-seed").digest()  # 32 bytes
    codeword = rs_encode_msg(key, nsym)            # 48 bytes
    reading = bytes([0xA5] * len(codeword))
    helper = bytes(c ^ r for c, r in zip(codeword, reading))
    # flip a few bytes in the reading (<= 8 tolerable)
    noisy = bytearray(reading)
    for p in (3, 17, 40):
        noisy[p] ^= 0xFF
    recovered = bytes(h ^ r for h, r in zip(helper, bytes(noisy)))
    assert rs_correct_msg(recovered, nsym) == key
