"""KMS master-key custody via HashiCorp Vault (verified against a local dev server)."""
import base64
import os
import re
import shutil
import subprocess
import time

import httpx
import pytest

from api.gateway import create_secure_app
from core.kms import VaultMasterKeySource

VAULT_BIN = os.environ.get("VRl1_VAULT_BIN") or shutil.which("vault")
pytestmark = pytest.mark.skipif(VAULT_BIN is None, reason="vault binary not available")

MASTER = b"test-master-key-32-bytes-minimum!!"


@pytest.fixture(scope="module")
def vault():
    proc = subprocess.Popen(
        [VAULT_BIN, "server", "-dev"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    token = None
    # Vault prints "Root Token: <token>" to stdout in dev mode.
    for _ in range(400):
        line = proc.stdout.readline()
        if not line:
            continue
        m = re.search(r"Root Token:\s*(\S+)", line)
        if m:
            token = m.group(1)
            break
    addr = "http://127.0.0.1:8200"
    for _ in range(100):
        try:
            if httpx.get(f"{addr}/v1/sys/health", timeout=1.0).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.1)
    assert token is not None, "vault dev server did not emit a root token"
    # Seed the master key into KV v2.
    httpx.post(f"{addr}/v1/secret/data/vrl1",
               headers={"X-Vault-Token": token},
               json={"data": {"master_key": base64.b64encode(MASTER).decode()}},
               timeout=5.0).raise_for_status()
    yield {"addr": addr, "token": token}
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_vault_source_fetches_master_key(vault):
    src = VaultMasterKeySource(vault["addr"], vault["token"])
    assert src.get_master_key() == MASTER


def test_vault_source_bad_token_fails(vault):
    src = VaultMasterKeySource(vault["addr"], "bad-token")
    with pytest.raises(httpx.HTTPStatusError):
        src.get_master_key()


def test_create_secure_app_uses_vault_master_key(vault, monkeypatch):
    monkeypatch.setenv("VRL1_VAULT_ADDR", vault["addr"])
    monkeypatch.setenv("VRL1_VAULT_TOKEN", vault["token"])
    monkeypatch.delenv("VRL1_MASTER_KEY", raising=False)
    app = create_secure_app(admin_key="test-admin-key")
    assert app.state.engine._master == MASTER
