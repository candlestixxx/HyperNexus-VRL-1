"""
End-to-End API Integration Tests for HyperNexus VRL-1 Gateway.
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["radial_vault_active"] is True
    assert data["tenants_loaded"] >= 3

def test_portal_html_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "HyperNexus VRL-1" in response.text
    assert "Radial Vector" in response.text

def test_list_tenants():
    response = client.get("/api/v1/tenants")
    assert response.status_code == 200
    tenants = response.json()
    assert len(tenants) >= 3
    company_ids = [t["company_id"] for t in tenants]
    assert "united_beats" in company_ids
    assert "excel_legacy_realty" in company_ids

def test_dispatch_with_valid_key_united_beats():
    payload = {
        "track_id": "trk_1001",
        "artist": "United Beats Artist",
        "tempo": 126
    }
    headers = {
        "X-API-Key": "ub_live_key_9901_hypernexus_vrl1"
    }
    response = client.post("/mcp/dispatch/music/stream/ingest", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "routed"
    assert data["company"] == "united_beats"
    assert data["radial_ring"] == 1.0
    assert data["db_logged"] is True
    assert data["mcp_synced"] is True

def test_dispatch_with_excel_legacy_realty():
    payload = {
        "lead_name": "Marcus Vance",
        "budget": 850000
    }
    headers = {
        "X-API-Key": "excel_legacy_key_7742_realestate"
    }
    response = client.post("/mcp/dispatch/leads/webhook", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "routed"
    assert data["company"] == "excel_legacy_realty"
    assert data["radial_ring"] == 1.5

def test_dispatch_unauthorized():
    response = client.post("/mcp/dispatch/test", json={"foo": "bar"}, headers={"X-API-Key": "invalid_bogus_key"})
    assert response.status_code == 401

def test_onboard_new_tenant_and_dispatch():
    new_tenant = {
        "company_id": "detroit_techno_collective",
        "company_name": "Detroit Techno Collective",
        "tier": "tier_1_enterprise",
        "api_key": "dtc_live_key_5544",
        "target_api": "https://api.detroittechno.local/v1",
        "db_connection": "postgresql://dtc:secret@db.dtc.local:5432/dtc_core",
        "db_type": "postgresql",
        "mcp_enabled": True,
        "rate_limit_rps": 300.0,
        "metadata": {"genre": "techno"}
    }
    onboard_resp = client.post("/api/v1/tenants", json=new_tenant)
    assert onboard_resp.status_code == 200
    assert onboard_resp.json()["status"] == "registered"

    # Immediately dispatch with new key without server reboot
    dispatch_resp = client.post(
        "/mcp/dispatch/events/broadcast",
        json={"event": "sub-bass-festival"},
        headers={"X-API-Key": "dtc_live_key_5544"}
    )
    assert dispatch_resp.status_code == 200
    assert dispatch_resp.json()["company"] == "detroit_techno_collective"

def test_mcp_json_rpc():
    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/list"
    }
    response = client.post("/mcp/rpc", json=rpc_payload)
    assert response.status_code == 200
    result = response.json()["result"]
    assert "tools" in result
    assert len(result["tools"]) >= 3

def test_audit_ledger_retrieval():
    response = client.get("/api/v1/audit/united_beats")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    assert logs[0]["company_id"] == "united_beats"

def test_telemetry():
    response = client.get("/api/v1/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] >= 1
    assert "united_beats" in data["tenant_traffic"]
