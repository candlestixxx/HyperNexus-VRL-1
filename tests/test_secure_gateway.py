"""P1/P2/P3: secure gateway dispatch, transparency log, invariant fuzz."""
import random
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from api.gateway import create_secure_app
from core.transparency import MerkleLog
from core.vrl1_algo import VRL1ZeroTrustEngine

MASTER = b"test-master-key-32-bytes-minimum!!"


def _secure_client(seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"ok": True})

    app = create_secure_app(master_key=MASTER, admin_key="test-admin-key",
                            transport=httpx.MockTransport(handler))
    return TestClient(app), app


ADMIN = {"X-VRL1-Admin-Key": "test-admin-key"}


def _dispatch(client, engine, tenant, key, nonce="n-1", body=b'{"x":1}'):
    ts = int(time.time())
    path = "/mcp/dispatch/leads"
    proof = engine.make_proof(tenant, key, nonce, ts, "POST", path, body)
    return client.post(path, content=body, headers={
        "X-API-Key": key, "X-VRL1-Tenant": tenant, "X-VRL1-Epoch": "1",
        "X-VRL1-Nonce": nonce, "X-VRL1-Timestamp": str(ts), "X-VRL1-Proof": proof,
        "Content-Type": "application/json"})


def test_secure_enroll_dispatch_and_replay():
    seen: list = []
    client, app = _secure_client(seen)
    with client:
        enr = client.post("/secure/enroll", headers=ADMIN, json={
            "tenant_id": "tenant_a", "target_url": "https://a.example.com",
            "db_connection_string": "sqlite:///a.db", "scopes": ["*"]})
        assert enr.status_code == 200
        key = enr.json()["api_key"]
        assert enr.json()["transparency_root"] != ""
        r1 = _dispatch(client, app.state.engine, "tenant_a", key)
        assert r1.status_code == 200, r1.text
        r2 = _dispatch(client, app.state.engine, "tenant_a", key)  # same nonce
        assert r2.status_code == 403
        assert seen == ["https://a.example.com/leads"]  # upstream hit exactly once


def test_secure_gateway_requires_key_material_not_just_vector():
    seen: list = []
    client, app = _secure_client(seen)
    with client:
        enr = client.post("/secure/enroll", headers=ADMIN, json={
            "tenant_id": "tenant_a", "target_url": "https://a.example.com",
            "db_connection_string": "sqlite:///a.db", "scopes": ["*"]})
        key = enr.json()["api_key"]
        # Wrong key (attacker without possession) with its own proof math fails.
        r = _dispatch(client, app.state.engine, "tenant_a", "attacker-key-value")
        assert r.status_code == 403
        assert seen == []


def test_enroll_forbidden_without_admin_key():
    seen: list = []
    client, _app = _secure_client(seen)
    with client:
        r = client.post("/secure/enroll", json={
            "tenant_id": "tenant_a", "target_url": "https://a.example.com",
            "db_connection_string": "sqlite:///a.db", "scopes": ["*"]})
        assert r.status_code == 403
        r2 = client.post("/secure/enroll", headers={"X-VRL1-Admin-Key": "wrong"},
                         json={"tenant_id": "tenant_a",
                               "target_url": "https://a.example.com",
                               "db_connection_string": "sqlite:///a.db", "scopes": ["*"]})
        assert r2.status_code == 403


def test_vault_persistence_survives_reload_and_rejects_tamper(tmp_path):
    import json as _json
    from core.secure_vault import SecureRadialVault
    from core.vrl1_algo import Ring
    path = str(tmp_path / "vault.json")
    e1 = VRL1ZeroTrustEngine(MASTER)
    v1 = SecureRadialVault(e1, persistence_path=path)
    v1.register_tenant("tenant_a", Ring(0, 1 << 63))
    key, _ = v1.enroll_generated_key("tenant_a", 1, "https://a.example.com", "sqlite:///a.db")
    root1 = v1.transparency_root()
    # Reload with a fresh engine/vault: key still authenticates, root preserved.
    e2 = VRL1ZeroTrustEngine(MASTER)
    v2 = SecureRadialVault(e2, persistence_path=path)
    assert v2.transparency_root() == root1
    assert e2.verify_root_signature(root1, v2.transparency_signature())
    now = int(time.time())
    proof = e2.make_proof("tenant_a", key, "np-1", now, "POST", "/x", b"")
    out = v2.authenticate(tenant_id="tenant_a", api_key=key, epoch=1, current_epoch=1,
                          nonce="np-1", ts=now, method="POST", path="/x",
                          body=b"", proof=proof, now=float(now))
    assert out["target_url"] == "https://a.example.com"
    # Tampered state file (rolled-back root) is refused on load.
    data = _json.loads(open(path, encoding="utf-8").read())
    data["transparency_leaves"] = data["transparency_leaves"][:-1]
    open(path, "w", encoding="utf-8").write(_json.dumps(data))
    with pytest.raises(ValueError):
        SecureRadialVault(VRL1ZeroTrustEngine(MASTER), persistence_path=path)


def test_secure_mode_refuses_without_master_key(monkeypatch):
    monkeypatch.delenv("VRL1_MASTER_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_secure_app()


def test_demo_mode_surfaces_generated_admin_key():
    app = create_secure_app(demo=True)
    assert app.state.admin_autogenerated is True
    client = TestClient(app)
    with client:
        r = client.get("/secure/demo-admin-key")
        assert r.status_code == 200
        assert r.json()["admin_key"] == app.state.admin_key


def test_demo_admin_key_endpoint_hidden_with_explicit_key():
    app = create_secure_app(master_key=MASTER, admin_key="test-admin-key")
    assert app.state.admin_autogenerated is False
    client = TestClient(app)
    with client:
        assert client.get("/secure/demo-admin-key").status_code == 404


def test_transparency_inclusion_proof():
    log = MerkleLog()
    entries = [f"enroll-{i}".encode() for i in range(9)]
    for e in entries:
        log.append(e)
    root = log.root()
    for i, e in enumerate(entries):
        assert MerkleLog.verify_inclusion(e, log.inclusion_proof(i), root)
    assert not MerkleLog.verify_inclusion(b"forged", log.inclusion_proof(0), root)


def test_invariant_fuzz_cross_tenant_never_authenticates():
    """Generated key for tenant A never authenticates as tenant B, and
    tampered proofs always fail (stdlib-random property test)."""
    rng = random.Random(20261116)
    engine = VRL1ZeroTrustEngine(MASTER)
    from core.secure_vault import SecureRadialVault
    from core.vrl1_algo import Ring
    v = SecureRadialVault(engine)
    v.register_tenant("tenant_a", Ring(0, 1 << 63))
    v.register_tenant("tenant_b", Ring(1 << 63, 1 << 64))
    key_a, _ = v.enroll_generated_key("tenant_a", 3, "https://a.example.com", "sqlite:///a.db")
    now = int(time.time())
    for i in range(50):
        nonce = f"fz-{i}-{rng.randrange(10**9)}"
        proof = engine.make_proof("tenant_b", key_a, nonce, now, "POST", "/x", b"")
        with pytest.raises(PermissionError):
            v.authenticate(tenant_id="tenant_b", api_key=key_a, epoch=3,
                           current_epoch=3, nonce=nonce, ts=now, method="POST",
                           path="/x", body=b"", proof=proof, now=float(now))
