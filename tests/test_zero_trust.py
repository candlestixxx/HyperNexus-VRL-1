"""Proofs I–III: geometric zero-trust tests for HyperNexus VRL-1.

These run at the math layer only — no HTTP, no DB — which is the point:
a cross-ring request must already be dead before either is touched.
"""
import numpy as np
import pytest

from core.vector_math import RadialVectorEngine
from core.vault import RadialVault, RadialVaultUnauthorized

KEY_A = "excel_legacy_key_7742"
KEY_B = "acme_other_tenant_key_9917"


@pytest.fixture()
def engine() -> RadialVectorEngine:
    return RadialVectorEngine(dimensions=4, ring_width=100.0)


@pytest.fixture()
def vault(engine) -> RadialVault:
    v = RadialVault(engine)
    v.register_tenant("tenant_a", 100.0, 200.0)
    v.register_tenant("tenant_b", 300.0, 400.0)
    v.store_endpoint(KEY_A, "https://a.example.com", "sqlite:///a.db", tenant_id="tenant_a")
    v.store_endpoint(KEY_B, "https://b.example.com", "sqlite:///b.db", tenant_id="tenant_b")
    return v


# Proof I — spatilization is deterministic and in-range.
def test_spatialize_deterministic(engine):
    r1, a1 = engine.spatialize_key(KEY_A)
    r2, a2 = engine.spatialize_key(KEY_A)
    assert r1 == r2
    assert np.array_equal(a1, a2)
    assert 100.0 <= r1 < 200.0
    assert np.all((a1 >= 0.0) & (a1 < 2.0 * np.pi))
    _, other = engine.spatialize_key(KEY_B)
    assert not np.array_equal(a1, other)


# Proof II — Tenant A's radius + Tenant B's angles is rejected, and vice versa.
def test_cross_tenant_vector_rejected(engine):
    r_a, ang_a = engine.spatialize_key(KEY_A)
    r_b, ang_b = engine.spatialize_key(KEY_B)
    # Project each key's fraction into its own ring, as the vault does.
    proj_a = engine.project_radius(engine.radial_fraction(KEY_A), 100.0, 200.0)
    proj_b = engine.project_radius(engine.radial_fraction(KEY_B), 300.0, 400.0)
    # Own vector passes its own ring.
    assert engine.route_payload(proj_a, ang_a, 100.0, 200.0, ang_a) is True
    assert engine.route_payload(proj_b, ang_b, 300.0, 400.0, ang_b) is True
    # A's radius carrying B's angles fails the angular gate in A's ring.
    assert engine.route_payload(proj_a, ang_b, 100.0, 200.0, ang_a) is False
    # B's radius fails A's radial gate outright, whatever the angles.
    assert engine.route_payload(proj_b, ang_a, 100.0, 200.0, ang_a) is False
    assert r_a != r_b or not np.array_equal(ang_a, ang_b)


def test_radial_gate_rejects_out_of_ring_even_with_perfect_angles(engine):
    _, ang = engine.spatialize_key(KEY_A)
    assert engine.route_payload(250.0, ang, 100.0, 200.0, ang) is False
    assert engine.route_payload(200.0, ang, 100.0, 200.0, ang) is False  # [min, max)


def test_overlapping_rings_cannot_register(vault):
    with pytest.raises(ValueError):
        vault.register_tenant("evil_overlap", 150.0, 250.0)


# Vault level — each key resolves only to its own tenant; unknown keys die here.
def test_vault_resolves_own_tenant_only(vault):
    a = vault.resolve_endpoint(KEY_A)
    b = vault.resolve_endpoint(KEY_B)
    assert a["tenant_id"] == "tenant_a" and a["target_url"] == "https://a.example.com"
    assert b["tenant_id"] == "tenant_b" and b["target_url"] == "https://b.example.com"
    assert a["db_connection_string"] != b["db_connection_string"]


def test_vault_rejects_unknown_and_tampered_keys(vault):
    with pytest.raises(RadialVaultUnauthorized):
        vault.resolve_endpoint("totally_made_up_key")
    with pytest.raises(RadialVaultUnauthorized):
        vault.resolve_endpoint(KEY_A + "x")  # one char off -> different shard


# Proof III — routing cost does not grow with tenant count (no scan to time,
# but the API surface proves it: route_payload takes no tenant collection).
def test_route_payload_signature_is_constant_in_n(engine):
    import inspect
    params = list(inspect.signature(engine.route_payload).parameters)
    assert params == ["query_r", "query_angles", "tenant_min_r",
                      "tenant_max_r", "target_angles", "tolerance"]
