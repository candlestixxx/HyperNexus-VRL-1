"""Shared-store backends (SQLite/WAL) behind the nonce + capability-usage interfaces."""
import time

import pytest

from core.secure_vault import SecureRadialVault
from core.stores import SQLiteCapabilityUsageStore, SQLiteNonceStore
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"
HALF = 1 << 63


def test_sqlite_nonce_store_replay_and_expiry(tmp_path):
    store = SQLiteNonceStore(str(tmp_path / "nonces.db"), ttl_seconds=2)
    assert store.check_and_record("t", "n1", now=0.0) is True
    assert store.check_and_record("t", "n1", now=0.5) is False  # replay
    assert store.check_and_record("t", "n2", now=0.5) is True
    assert store.check_and_record("t", "n1", now=3.0) is True  # expired
    store.close()


def test_sqlite_nonce_store_shared_across_instances(tmp_path):
    path = str(tmp_path / "shared.db")
    s1 = SQLiteNonceStore(path, ttl_seconds=10)
    s2 = SQLiteNonceStore(path, ttl_seconds=10)
    assert s1.check_and_record("t", "n", now=0.0) is True
    assert s2.check_and_record("t", "n", now=0.1) is False  # seen by another instance
    s1.close()
    s2.close()


def test_sqlite_capability_usage_store(tmp_path):
    store = SQLiteCapabilityUsageStore(str(tmp_path / "cap.db"))
    assert store.try_use("j1", 2) is True
    assert store.try_use("j1", 2) is True
    assert store.try_use("j1", 2) is False  # budget exhausted
    assert store.try_use("j2", 0) is True   # 0 == unlimited
    store.close()


def test_engine_uses_injected_shared_nonce_store(tmp_path):
    store = SQLiteNonceStore(str(tmp_path / "nonces.db"), ttl_seconds=60)
    e1 = VRL1ZeroTrustEngine(MASTER, nonce_store=store)
    e2 = VRL1ZeroTrustEngine(MASTER, nonce_store=store)
    ring = Ring(0, 1 << 64)
    key = "some-tenant-key"
    ts = int(time.time())
    radius, shards = e1.derive_coordinate("tenant_a", key, 1)
    assert ring.contains(radius)
    proof = e1.make_proof("tenant_a", key, "n-1", ts, "POST", "/x", b"")
    kwargs = dict(tenant_id="tenant_a", api_key=key, epoch=1, current_epoch=1,
                  ring=ring, target_shards=shards, nonce="n-1", ts=ts,
                  method="POST", path="/x", body=b"", proof=proof, now=float(ts))
    assert e1.verify_request(**kwargs) is True
    # A second engine sharing the same store sees the replay.
    assert e2.verify_request(**kwargs) is False
    store.close()


def test_vault_capability_usage_shared_across_instances(tmp_path):
    store = SQLiteCapabilityUsageStore(str(tmp_path / "cap.db"))
    vpath = str(tmp_path / "vault.json")
    e1 = VRL1ZeroTrustEngine(MASTER)
    v1 = SecureRadialVault(e1, persistence_path=vpath, usage_store=store)
    v1.register_tenant("tenant_a", Ring(0, HALF))
    v1.enroll_generated_key("tenant_a", 1, "https://a.example.com", "sqlite:///a.db")
    token = v1.mint_agent_token("tenant_a", scopes=["read"],
                                exp=int(time.time()) + 60, max_uses=2)
    now = float(int(time.time()))
    v1.authenticate_agent_token(token, method="POST", path="/x", now=now)
    v1.authenticate_agent_token(token, method="POST", path="/x", now=now)
    # A fresh vault (same persisted records + shared usage store) sees the
    # budget exhausted across the instance boundary.
    e2 = VRL1ZeroTrustEngine(MASTER)
    v2 = SecureRadialVault(e2, persistence_path=vpath, usage_store=store)
    with pytest.raises(PermissionError):
        v2.authenticate_agent_token(token, method="POST", path="/x", now=now)
    store.close()
