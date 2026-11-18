"""VRL-4 GAP: primitives + the full physics/light/math handshake."""
import time

import pytest

from core.vrl4_gap import (GapAuthenticator, KalmanLatencyTracker, fuzzy_generate,
                           fuzzy_reproduce, haversine_km, is_within_radius,
                           max_radius_km, sign_challenge, verify_challenge)
from core.secure_vault import SecureRadialVault
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"


def _flip_bits(data: bytes, positions: list[int]) -> bytes:
    b = bytearray(data)
    for p in positions:
        b[p // 8] ^= 1 << (7 - (p % 8))
    return bytes(b)


# -- primitives ---------------------------------------------------------------
def test_fuzzy_extractor_recovers_from_noise():
    reading = b"\xA5" * (32 * 3)
    key, helper = fuzzy_generate(reading, 32, 3)
    # one bit per 3-bit block is tolerable
    positions = [b * 3 for b in range(32 * 8)]
    noisy = _flip_bits(reading, positions)
    assert fuzzy_reproduce(noisy, helper, 32, 3) == key


def test_fuzzy_extractor_diverges_on_excessive_noise():
    reading = b"\x5A" * (32 * 3)
    key, helper = fuzzy_generate(reading, 32, 3)
    positions = []
    for b in range(32 * 8):
        positions += [b * 3, b * 3 + 1]
    noisy = _flip_bits(reading, positions)
    assert fuzzy_reproduce(noisy, helper, 32, 3) != key


def test_challenge_sign_verify():
    key = b"device-secret-key-32-bytes-minimum!"
    sig = sign_challenge(key, b"nonce", b"cn", b"payload")
    assert verify_challenge(key, b"nonce", b"cn", b"payload", sig)
    assert not verify_challenge(key, b"nonce", b"cn", b"other", sig)


def test_kalman_flags_spikes():
    k = KalmanLatencyTracker(0.1, 4.0)
    for i in range(50):
        k.update(20.0 + ((i * 7) % 5) - 2.0)
    assert abs(k.estimate() - 20.0) < 1.5
    assert k.is_anomalous(200.0, 5.0)
    assert not k.is_anomalous(21.0, 5.0)


def test_geodesic_bounds():
    d = haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
    assert abs(d - 3936.0) < 50.0
    assert max_radius_km(40.0, 200.0) == pytest.approx(4000.0)
    assert is_within_radius(40.7128, -74.0060, 34.0522, -118.2437, 40.0)
    assert not is_within_radius(40.7128, -74.0060, 34.0522, -118.2437, 10.0)


# -- full handshake -----------------------------------------------------------
def _authenticator():
    engine = VRL1ZeroTrustEngine(MASTER)
    vault = SecureRadialVault(engine)
    vault.register_tenant("tenant_a", Ring(0, 1 << 64))  # full ring for the demo
    gap = GapAuthenticator(engine, vault, "tenant_a")
    return gap


def test_gap_handshake_access_granted():
    gap = _authenticator()
    reading = b"\x11" * (32 * 3)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    # prove with a slightly noisy reading (still within tolerance)
    noisy = _flip_bits(reading, [b * 3 for b in range(32 * 8)])
    proof = gap.prove(noisy, "1234", challenge)
    out = gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)
    assert out["target_url"] == "https://a.example.com"


def test_gap_handshake_rejects_tampered_signature():
    gap = _authenticator()
    reading = b"\x22" * (32 * 3)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    proof = gap.prove(reading, "1234", challenge)
    from core.vrl4_gap import GapProof
    bad = GapProof(proof.tenant_id, proof.device_id, proof.nonce, proof.client_nonce,
                   b"\x00" * 32)
    with pytest.raises(PermissionError):
        gap.verify(bad, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)


def test_gap_handshake_rejects_anomalous_latency():
    gap = _authenticator()
    reading = b"\x33" * (32 * 3)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    proof = gap.prove(reading, "1234", challenge)
    # first warm the Kalman filter with normal latency, then spike
    gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)
    with pytest.raises(PermissionError):
        gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=2000.0)


def test_gap_handshake_rejects_wrong_device_reading():
    gap = _authenticator()
    reading = b"\x44" * (32 * 3)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    # a completely different device produces a different key -> signature fails
    proof = gap.prove(b"\x99" * (32 * 3), "1234", challenge)
    with pytest.raises(PermissionError):
        gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)


# -- Schnorr (zero-knowledge) handshake --------------------------------------
def _schnorr_authenticator():
    from core.vrl4_gap import SchnorrGapAuthenticator
    engine = VRL1ZeroTrustEngine(MASTER)
    vault = SecureRadialVault(engine)
    vault.register_tenant("tenant_a", Ring(0, 1 << 64))
    return SchnorrGapAuthenticator(engine, vault, "tenant_a")


def test_schnorr_gap_handshake_access_granted():
    gap = _schnorr_authenticator()
    reading = b"\x55" * (32 * 3)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    noisy = _flip_bits(reading, [b * 3 for b in range(32 * 8)])
    proof = gap.prove(noisy, "1234", challenge)
    out = gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)
    assert out["target_url"] == "https://a.example.com"


def test_schnorr_gap_handshake_rejects_forged_signature():
    from core.vrl4_gap import GapProof
    gap = _schnorr_authenticator()
    reading = b"\x66" * (32 * 3)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    proof = GapProof("tenant_a", "", challenge.nonce, b"", (1, 2))
    with pytest.raises(PermissionError):
        gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)


def test_gap_handshake_rs_codec():
    from core.vrl4_gap import GapAuthenticator
    engine = VRL1ZeroTrustEngine(MASTER)
    vault = SecureRadialVault(engine)
    vault.register_tenant("tenant_a", Ring(0, 1 << 64))
    gap = GapAuthenticator(engine, vault, "tenant_a", codec="rs", nsym=16)
    reading = b"\x77" * 48  # key_len(32) + nsym(16)
    gap.enroll_device(reading, "1234", "https://a.example.com", "sqlite:///a.db")
    challenge = gap.issue_challenge()
    noisy = bytearray(reading)
    for p in (3, 17, 40):  # byte errors within RS correction radius
        noisy[p] ^= 0xFF
    proof = gap.prove(bytes(noisy), "1234", challenge)
    out = gap.verify(proof, device_lat=40.7128, device_lon=-74.0060, rtt_ms=5.0)
    assert out["target_url"] == "https://a.example.com"
