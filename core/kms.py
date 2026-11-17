"""KMS/HSM master-key custody.

The gateway's master key must come from a KMS, not be shipped in config.
`MasterKeySource` is the narrow interface the secure app consumes;
`VaultMasterKeySource` fetches it from HashiCorp Vault KV v2. Precedence in
`create_secure_app`: explicit arg > Vault (if `VRL1_VAULT_ADDR` set) > env >
demo. This keeps the env path as a dev convenience while production custody
goes through the KMS.
"""
from __future__ import annotations

import base64
from typing import Protocol


class MasterKeySource(Protocol):
    def get_master_key(self) -> bytes: ...


class VaultMasterKeySource:
    """Reads the master key from Vault KV v2 (secret engine, versioned data)."""

    def __init__(self, addr: str, token: str, path: str = "secret/data/vrl1",
                 field: str = "master_key", timeout: float = 10.0) -> None:
        self.addr = addr.rstrip("/")
        self.token = token
        self.path = path
        self.field = field
        self.timeout = timeout

    def get_master_key(self) -> bytes:
        import httpx  # lazy: core stays importable without network deps
        url = f"{self.addr}/v1/{self.path}"
        resp = httpx.get(url, headers={"X-Vault-Token": self.token},
                         timeout=self.timeout)
        resp.raise_for_status()
        # KV v2 shape: {"data": {"data": {"<field>": "<base64>"}, "metadata": ...}}
        value = resp.json()["data"]["data"][self.field]
        return base64.b64decode(value)
