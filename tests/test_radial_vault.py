"""
Unit Tests for Radial Vector Vault & Polar Coordinate Derivation.
"""

import pytest
import os
from src.vault.radial_vault import RadialVectorVault
from src.models import TenantRegistrationRequest, TenantTier, DatabaseEngineType
from src.security import compute_radial_coordinate, RadialVectorCipher

@pytest.fixture
def test_vault(tmp_path):
    persistence_file = str(tmp_path / "test_radial_vault.json")
    return RadialVectorVault(persistence_path=persistence_file)

def test_cipher_encryption_roundtrip():
    cipher = RadialVectorCipher()
    secret = "postgresql://user:topsecret123@db.prod:5432/main"
    encrypted = cipher.encrypt_secret(secret)
    assert encrypted != secret
    decrypted = cipher.decrypt_secret(encrypted)
    assert decrypted == secret

def test_radial_coordinate_derivation():
    coord_tier1 = compute_radial_coordinate("ub_test_key_1", TenantTier.TIER_1_ENTERPRISE)
    assert coord_tier1.r == 1.0
    assert 0.0 <= coord_tier1.theta <= 6.29

    coord_tier0 = compute_radial_coordinate("hyp_core_key", TenantTier.TIER_0_CORE)
    assert coord_tier0.r == 0.5

def test_vault_registration_and_lookup(test_vault):
    req = TenantRegistrationRequest(
        company_id="acme_corp",
        company_name="Acme Corporation",
        tier=TenantTier.TIER_2_PRO,
        api_key="acme_secret_key_999",
        target_api="https://api.acmecorp.com/v1",
        db_connection="sqlite:///data/acme.db",
        db_type=DatabaseEngineType.SQLITE,
        mcp_enabled=True,
        metadata={"domain": "acme.hypernexus.local"}
    )
    test_vault.register_tenant(req)

    # Retrieval via API key
    ctx = test_vault.get_tenant_by_api_key("acme_secret_key_999")
    assert ctx.company_id == "acme_corp"
    assert ctx.db_connection == "sqlite:///data/acme.db" # Decrypted at runtime

    # Retrieval via Company ID
    ctx_by_id = test_vault.get_tenant_by_company_id("acme_corp")
    assert ctx_by_id is not None
    assert ctx_by_id.company_name == "Acme Corporation"

    # Retrieval via Domain
    ctx_by_domain = test_vault.get_tenant_by_domain("acme.hypernexus.local")
    assert ctx_by_domain is not None
    assert ctx_by_domain.company_id == "acme_corp"

def test_vault_invalid_key(test_vault):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        test_vault.get_tenant_by_api_key("non_existent_key")
    assert exc.value.status_code == 401

def test_vault_mask_secrets(test_vault):
    tenants = test_vault.list_all_tenants(mask_secrets=True)
    assert len(tenants) >= 3
    for t in tenants:
        assert "••••••••" in t["db_connection"]
