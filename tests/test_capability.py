"""Capability-attenuated agent tokens: mint, verify, caveats, tamper, budget."""
import time

import pytest

from core.capability import CapabilityError, CapabilityUsageLedger, mint, parse_and_verify
from core.secure_vault import SecureRadialVault
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


def test_capability_roundtrip_and_tamper(engine):
    now = int(time.time())
    token = mint(engine, tenant_id="tenant_a", shards=(1, 2, 3), scopes=["read"],
                 exp=now + 60, path_prefix="/mcp/dispatch/leads", max_uses=5, now=now)
    cap = parse_and_verify(engine, token, now=now)
    assert cap.tenant_id == "tenant_a"
    assert cap.shards == (1, 2, 3)
    assert cap.scopes == ["read"]
    assert cap.max_uses == 5
    # Tampered payload (flip a char in the base64 body) fails the signature.
    b64, sig = token.rsplit(".", 1)
    flipped = ("A" if b64[-1] != "A" else "B")
    with pytest.raises(CapabilityError):
        parse_and_verify(engine, b64[:-1] + flipped + "." + sig, now=now)
    # Wrong signature fails.
    with pytest.raises(CapabilityError):
        parse_and_verify(engine, b64 + "." + "00" * 32, now=now)


def test_capability_expiry(engine):
    now = int(time.time())
    token = mint(engine, tenant_id="t", shards=(1, 2, 3), scopes=["read"],
                 exp=now + 1, now=now)
    with pytest.raises(CapabilityError):
        parse_and_verify(engine, token, now=now + 2)


def test_usage_ledger():
    led = CapabilityUsageLedger()
    assert led.try_use("a", 2) is True
    assert led.try_use("a", 2) is True
    assert led.try_use("a", 2) is False
    assert led.try_use("b", 0) is True  # 0 == unlimited


def test_vault_mint_and_authenticate_agent_token(vault):
    vault.enroll_generated_key("tenant_a", 1, "https://a.example.com", "sqlite:///a.db")
    now = int(time.time())
    token = vault.mint_agent_token("tenant_a", scopes=["read"], exp=now + 60,
                                   path_prefix="/mcp/dispatch/leads", max_uses=3, now=now)
    out = vault.authenticate_agent_token(token, method="POST",
                                         path="/mcp/dispatch/leads/1", now=float(now))
    assert out["tenant_id"] == "tenant_a"
    assert out["target_url"] == "https://a.example.com"
    assert out["scopes"] == ["read"]  # attenuated, not the full enrollment scopes


def test_agent_token_path_prefix_enforced(vault):
    vault.enroll_generated_key("tenant_a", 1, "https://a.example.com", "sqlite:///a.db")
    now = int(time.time())
    token = vault.mint_agent_token("tenant_a", scopes=["read"], exp=now + 60,
                                   path_prefix="/mcp/dispatch/leads", now=now)
    with pytest.raises(PermissionError):
        vault.authenticate_agent_token(token, method="POST",
                                       path="/mcp/dispatch/other", now=float(now))
    vault.authenticate_agent_token(token, method="POST",
                                   path="/mcp/dispatch/leads/9", now=float(now))


def test_agent_token_scope_escalation_rejected_at_mint(vault):
    vault.enroll_generated_key("tenant_a", 1, "https://a.example.com",
                               "sqlite:///a.db", scopes=["read"])
    now = int(time.time())
    with pytest.raises(ValueError):
        vault.mint_agent_token("tenant_a", scopes=["admin"], exp=now + 60, now=now)


def test_agent_token_max_uses_exhausted(vault):
    vault.enroll_generated_key("tenant_a", 1, "https://a.example.com", "sqlite:///a.db")
    now = int(time.time())
    token = vault.mint_agent_token("tenant_a", scopes=["read"], exp=now + 60,
                                   max_uses=2, now=now)
    for _ in range(2):
        vault.authenticate_agent_token(token, method="POST", path="/x", now=float(now))
    with pytest.raises(PermissionError):
        vault.authenticate_agent_token(token, method="POST", path="/x", now=float(now))


def test_agent_token_tampered_fails_authentication(vault):
    vault.enroll_generated_key("tenant_a", 1, "https://a.example.com", "sqlite:///a.db")
    now = int(time.time())
    token = vault.mint_agent_token("tenant_a", scopes=["read"], exp=now + 60, now=now)
    b64, sig = token.rsplit(".", 1)
    tampered = b64[:-1] + ("A" if b64[-1] != "A" else "B") + "." + sig
    with pytest.raises(PermissionError):
        vault.authenticate_agent_token(tampered, method="POST", path="/x", now=float(now))
