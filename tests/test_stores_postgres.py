"""PostgreSQL shared-store backends, verified against a real local Postgres.

Uses `embedded-postgres` to spin up a real PostgreSQL server (no external
service needed), then exercises the nonce + capability-usage drivers against
it, including cross-instance sharing and engine integration.
"""
import tempfile
import time

import pytest

embedded_postgres = pytest.importorskip("embedded_postgres")

from core.stores_postgres import PostgresCapabilityUsageStore, PostgresNonceStore
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"


@pytest.fixture(scope="session")
def pg_dsn():
    """One shared PostgreSQL server for the whole test session."""
    import embedded_postgres as ep
    pgdata = tempfile.mkdtemp(prefix="vrl1_pgtest_")
    server = ep.get_server(pgdata, cleanup_mode="stop")
    server.ensure_postgres_running()
    yield server.get_uri()
    server.cleanup()


def test_postgres_nonce_store_replay_and_expiry(pg_dsn):
    store = PostgresNonceStore(pg_dsn, ttl_seconds=2)
    assert store.check_and_record("t", "n1", now=0.0) is True
    assert store.check_and_record("t", "n1", now=0.5) is False  # replay
    assert store.check_and_record("t", "n2", now=0.5) is True
    assert store.check_and_record("t", "n1", now=3.0) is True  # expired
    store.close()


def test_postgres_nonce_store_shared_across_instances(pg_dsn):
    s1 = PostgresNonceStore(pg_dsn, ttl_seconds=10)
    s2 = PostgresNonceStore(pg_dsn, ttl_seconds=10)
    assert s1.check_and_record("t", "n") is True
    assert s2.check_and_record("t", "n") is False  # seen by another instance
    s1.close()
    s2.close()


def test_postgres_capability_usage_store(pg_dsn):
    store = PostgresCapabilityUsageStore(pg_dsn)
    assert store.try_use("j1", 2) is True
    assert store.try_use("j1", 2) is True
    assert store.try_use("j1", 2) is False  # budget exhausted
    assert store.try_use("j2", 0) is True   # unlimited
    store.close()


def test_engine_uses_postgres_nonce_store(pg_dsn):
    store = PostgresNonceStore(pg_dsn, ttl_seconds=60)
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
    # A second engine sharing the same Postgres store sees the replay.
    assert e2.verify_request(**kwargs) is False
    store.close()
