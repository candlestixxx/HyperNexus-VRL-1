"""Tier-1 VRL-1: integer torus, proof-of-possession, replay, AEAD, rings."""
import time

import pytest
from cryptography.exceptions import InvalidTag

from core.secure_vault import KeyOutOfRing, SecureRadialVault, ShardCollisionPanic
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"
HALF = 1 << 63


@pytest.fixture()
def engine() -> VRL1ZeroTrustEngine:
    return VRL1ZeroTrustEngine(MASTER)


@pytest.fixture()
def vault(engine) -> SecureRadialVault:
    v = SecureRadialVault(engine)
    v.register_tenant("tenant_a", Ring(0, HALF))
    v.register_tenant("tenant_b", Ring(HALF, 1 << 64))
    return v


def _auth(vault, engine, tenant, key, epoch=7, nonce="n-1", now=None):
    now = int(time.time()) if now is None else now
    proof = engine.make_proof(tenant, key, nonce, now, "POST", "/leads", b"{}")
    return vault.authenticate(tenant_id=tenant, api_key=key, epoch=epoch,
                              current_epoch=epoch, nonce=nonce, ts=now,
                              method="POST", path="/leads", body=b"{}",
                              proof=proof, now=float(now))


def test_coordinate_is_static_per_epoch_and_integer(engine):
    r1, s1 = engine.derive_coordinate("tenant_a", "some-key", 7)
    r2, s2 = engine.derive_coordinate("tenant_a", "some-key", 7)
    assert (r1, s1) == (r2, s2)
    assert isinstance(r1, int) and all(isinstance(x, int) for x in s1)
    r3, _ = engine.derive_coordinate("tenant_a", "some-key", 8)
    assert r3 != r1  # epoch moves the coordinate (rotation)


def test_generated_key_authenticates_end_to_end(vault, engine):
    key, info = vault.enroll_generated_key("tenant_a", 7, "https://a.example.com", "sqlite:///a.db")
    out = _auth(vault, engine, "tenant_a", key)
    assert out["target_url"] == "https://a.example.com"
    assert info["radius"] < HALF


def test_stolen_vector_without_key_gets_nothing(vault, engine):
    key, info = vault.enroll_generated_key("tenant_a", 7, "https://a.example.com", "sqlite:///a.db")
    # Attacker knows radius+shards (info) but not the key: forged proof fails.
    now = int(time.time())
    forged = engine.make_proof("tenant_a", "attacker-guess", "n-x", now, "POST", "/leads", b"{}")
    with pytest.raises(PermissionError):
        vault.authenticate(tenant_id="tenant_a", api_key="attacker-guess", epoch=7,
                           current_epoch=7, nonce="n-x", ts=now, method="POST",
                           path="/leads", body=b"{}", proof=forged, now=float(now))


def test_replay_rejected_and_failed_attempt_does_not_burn_nonce(vault, engine):
    key, _ = vault.enroll_generated_key("tenant_a", 7, "https://a.example.com", "sqlite:///a.db")
    now = int(time.time())
    # Failed attempt with nonce n-9 (bad proof) must NOT burn it.
    with pytest.raises(PermissionError):
        vault.authenticate(tenant_id="tenant_a", api_key=key, epoch=7, current_epoch=7,
                           nonce="n-9", ts=now, method="POST", path="/leads",
                           body=b"{}", proof="00" * 32, now=float(now))
    # Same nonce with the correct proof now succeeds.
    proof = engine.make_proof("tenant_a", key, "n-9", now, "POST", "/leads", b"{}")
    vault.authenticate(tenant_id="tenant_a", api_key=key, epoch=7, current_epoch=7,
                       nonce="n-9", ts=now, method="POST", path="/leads",
                       body=b"{}", proof=proof, now=float(now))
    # Replay of the exact same valid request fails.
    with pytest.raises(PermissionError):
        vault.authenticate(tenant_id="tenant_a", api_key=key, epoch=7, current_epoch=7,
                           nonce="n-9", ts=now, method="POST", path="/leads",
                           body=b"{}", proof=proof, now=float(now))


def test_cross_ring_key_cannot_enroll_and_rings_cannot_overlap(engine):
    v = SecureRadialVault(engine)
    v.register_tenant("tenant_a", Ring(0, HALF))
    with pytest.raises(ValueError):
        v.register_tenant("tenant_b", Ring(HALF - 1, 1 << 64))
    # A BYO key deriving out-of-ring is refused, not projected into compliance.
    key = "byo-key-that-lands-wherever-it-lands"
    r, _ = engine.derive_coordinate("tenant_a", key, 7)
    if r >= HALF:
        with pytest.raises(KeyOutOfRing):
            v.enroll_key("tenant_a", key, 7, "https://a.example.com", "sqlite:///a.db")


def test_aead_record_cannot_be_moved_or_tampered(engine):
    blob = engine.seal_record("tenant_a", 123, (1, 2, 3), 7, ["read"],
                              {"target_url": "https://a.example.com"})
    assert engine.open_record("tenant_a", 123, (1, 2, 3), 7, ["read"], blob)
    with pytest.raises(InvalidTag):  # moved to a different shard
        engine.open_record("tenant_a", 123, (9, 9, 9), 7, ["read"], blob)
    with pytest.raises(InvalidTag):  # scope escalation attempt
        engine.open_record("tenant_a", 123, (1, 2, 3), 7, ["admin"], blob)
    with pytest.raises(InvalidTag):  # tampered ciphertext
        engine.open_record("tenant_a", 123, (1, 2, 3), 7, ["read"], blob[:-1] + b"\x00")


def test_shard_collision_panics(monkeypatch, vault, engine):
    key, info = vault.enroll_generated_key("tenant_a", 7, "https://a.example.com", "sqlite:///a.db")
    monkeypatch.setattr(engine, "derive_coordinate",
                        lambda t, k, e: (info["radius"], info["shards"]))
    with pytest.raises(ShardCollisionPanic):
        vault.enroll_key("tenant_a", "another-key", 7, "https://x.example.com", "sqlite:///x.db")
