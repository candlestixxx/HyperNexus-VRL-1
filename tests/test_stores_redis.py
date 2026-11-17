"""Redis shared-store backends, verified against fakeredis (no server needed)."""
import time

import pytest

fakeredis = pytest.importorskip("fakeredis")

from core.stores_redis import RedisCapabilityUsageStore, RedisNonceStore
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"


def _client():
    return fakeredis.FakeRedis()


def test_redis_nonce_store_replay_and_expiry():
    client = _client()
    store = RedisNonceStore(client=client, ttl_seconds=2)
    assert store.check_and_record("t", "n1", now=0.0) is True
    assert store.check_and_record("t", "n1", now=0.5) is False  # replay
    assert store.check_and_record("t", "n2", now=0.5) is True
    store.close()


def test_redis_nonce_store_shared_across_instances():
    client = _client()
    s1 = RedisNonceStore(client=client, ttl_seconds=10)
    s2 = RedisNonceStore(client=client, ttl_seconds=10)
    assert s1.check_and_record("t", "n") is True
    assert s2.check_and_record("t", "n") is False  # seen by another instance
    s1.close()
    s2.close()


def test_redis_capability_usage_store():
    client = _client()
    store = RedisCapabilityUsageStore(client=client)
    assert store.try_use("j1", 2) is True
    assert store.try_use("j1", 2) is True
    assert store.try_use("j1", 2) is False  # budget exhausted
    assert store.try_use("j2", 0) is True   # unlimited
    store.close()


def test_engine_uses_redis_nonce_store():
    client = _client()
    store = RedisNonceStore(client=client, ttl_seconds=60)
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
    # A second engine sharing the same Redis store sees the replay.
    assert e2.verify_request(**kwargs) is False
    store.close()
