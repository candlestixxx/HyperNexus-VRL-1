"""Gateway dispatch: authorized forwards, unauthorized gets 403 with no upstream call."""
import httpx
import pytest  # noqa: F401  (kept for fixture discovery parity)
from fastapi.testclient import TestClient

from api.gateway import create_app
from core.vault import RadialVault
from tests.test_zero_trust import KEY_A

def _client(seen: list) -> TestClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"echo": "ok"})

    v = RadialVault()
    v.register_tenant("tenant_a", 100.0, 200.0)
    v.register_tenant("tenant_b", 300.0, 400.0)
    v.store_endpoint(KEY_A, "https://a.example.com", "sqlite:///a.db", tenant_id="tenant_a")
    app = create_app(vault=v, transport=httpx.MockTransport(handler))
    return TestClient(app)


def test_authorized_key_is_forwarded():
    seen: list = []
    with _client(seen) as client:
        r = client.post("/mcp/dispatch/leads/ingest",
                        json={"lead": 1}, headers={"X-API-Key": KEY_A})
    assert r.status_code == 200
    assert r.json()["tenant_id"] == "tenant_a"
    assert seen == ["https://a.example.com/leads/ingest"]


def test_unknown_key_gets_403_and_upstream_is_never_called():
    seen: list = []
    with _client(seen) as client:
        r = client.post("/mcp/dispatch/leads/ingest",
                        json={"lead": 1}, headers={"X-API-Key": "forged_key"})
    assert r.status_code == 403
    assert seen == []


def test_missing_key_gets_403():
    seen: list = []
    with _client(seen) as client:
        r = client.post("/mcp/dispatch/leads/ingest", json={"lead": 1})
    assert r.status_code == 403
    assert seen == []
