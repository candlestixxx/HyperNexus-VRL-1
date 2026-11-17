"""CUSUM anomaly detection + circuit breaker (fail-closed brute-force defense)."""
import time

import pytest

from core.security_monitor import CUSUMAnomalyDetector
from core.secure_vault import SecureRadialVault
from core.vrl1_algo import Ring, VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"
HALF = 1 << 63


def test_cusum_trips_under_sustained_failures_and_recovers():
    m = CUSUMAnomalyDetector(window_seconds=1.0, baseline_rate=0.0,
                             threshold=2.0, cooldown_seconds=5.0)
    m.record_failure("k", now=0.0)
    m.record_failure("k", now=0.5)
    assert m.is_open("k", now=1.0) is True
    # A success resets immediately (used by the vault's legit-traffic recovery).
    m.record_success("k", now=1.5)
    assert m.is_open("k", now=1.6) is False
    # Re-trip, then let the cooldown window expire.
    m.record_failure("k", now=2.0)
    m.record_failure("k", now=2.5)
    assert m.is_open("k", now=3.0) is True
    assert m.is_open("k", now=8.0) is False  # cooldown elapsed -> auto-close


def test_cusum_baseline_tolerates_low_failure_rate():
    # baseline 0.5 failures/s with a 10s window: a couple of failures stay under.
    m = CUSUMAnomalyDetector(window_seconds=10.0, baseline_rate=0.5,
                             threshold=5.0, cooldown_seconds=30.0)
    m.record_failure("k", now=0.0)
    m.record_failure("k", now=1.0)
    assert m.is_open("k", now=1.5) is False


def test_open_circuits_reports_remaining_cooldown():
    m = CUSUMAnomalyDetector(window_seconds=1.0, baseline_rate=0.0,
                             threshold=2.0, cooldown_seconds=10.0)
    m.record_failure("tenant:t", now=0.0)
    m.record_failure("tenant:t", now=0.5)
    circs = m.open_circuits(now=2.0)
    assert "tenant:t" in circs
    assert circs["tenant:t"] == pytest.approx(8.5, abs=0.2)


def test_circuit_breaker_fails_closed_without_burning_nonce():
    engine = VRL1ZeroTrustEngine(MASTER)
    mon = CUSUMAnomalyDetector(window_seconds=1.0, baseline_rate=0.0,
                               threshold=2.0, cooldown_seconds=5.0)
    v = SecureRadialVault(engine, monitor=mon)
    v.register_tenant("tenant_a", Ring(0, HALF))
    key, _ = v.enroll_generated_key("tenant_a", 1, "https://a.example.com",
                                    "sqlite:///a.db")
    now = int(time.time())
    # Failed auths trip the tenant breaker (baseline 0 -> any failure drifts).
    for i in range(3):
        with pytest.raises(PermissionError):
            v.authenticate(tenant_id="tenant_a", api_key="wrong-key", epoch=1,
                           current_epoch=1, nonce=f"b-{i}", ts=now, method="POST",
                           path="/x", body=b"", proof="00" * 32,
                           now=float(now + i))
    assert mon.is_open("tenant:tenant_a", now=float(now + 2)) is True
    # A valid request with a fresh nonce is rejected while open — nonce NOT burned.
    proof = engine.make_proof("tenant_a", key, "fresh-1", now, "POST", "/x", b"")
    with pytest.raises(PermissionError):
        v.authenticate(tenant_id="tenant_a", api_key=key, epoch=1, current_epoch=1,
                       nonce="fresh-1", ts=now, method="POST", path="/x", body=b"",
                       proof=proof, now=float(now + 3))
    # After cooldown the SAME nonce still succeeds (proves it was never burned).
    proof2 = engine.make_proof("tenant_a", key, "fresh-1", now, "POST", "/x", b"")
    out = v.authenticate(tenant_id="tenant_a", api_key=key, epoch=1, current_epoch=1,
                         nonce="fresh-1", ts=now, method="POST", path="/x", body=b"",
                         proof=proof2, now=float(now + 8))
    assert out["target_url"] == "https://a.example.com"
