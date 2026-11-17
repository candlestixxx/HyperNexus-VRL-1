"""Capability-attenuated agent tokens (Biscuit-style, simplified).

An admin mints a signed token that lets an agent act on a tenant's behalf
without ever holding the tenant's raw API key. The token is:

- HMAC-signed with a master-derived key, so it verifies offline (no token DB);
- caveated to a scope subset, an expiry, an optional path prefix, and an
  optional max-use budget;
- bound to one enrolled credential via its shards, so the vault can look the
  routing record up without the raw key (a bare shard is useless without the
  key — proven in tests/test_vrl1_algo.py).

max_uses accounting is in-memory per process. Shared-store backends (Redis /
Postgres) are a later milestone (ROADMAP Milestone 4); the token format is
deliberately stateless so that a shared ledger can be swapped in without
changing the wire format.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass

from core.vrl1_algo import VRL1ZeroTrustEngine


class CapabilityError(ValueError):
    """A capability token is malformed, expired, or failed signature check."""


def scopes_satisfied(requested: set[str], granted: set[str]) -> bool:
    """True if `granted` covers `requested`; a granted '*' wildcard covers all."""
    return "*" in granted or requested <= granted


@dataclass(frozen=True)
class Capability:
    tenant_id: str
    shards: tuple[int, int, int]
    scopes: list[str]
    exp: int
    path_prefix: str = ""   # empty = no path restriction
    max_uses: int = 0       # 0 = unlimited
    jti: str = ""           # unique token id (usage accounting key)
    iat: int = 0            # issued-at unix seconds

    def canonical(self) -> bytes:
        """Deterministic payload bytes; the signature covers exactly these."""
        obj = {
            "tenant_id": self.tenant_id,
            "shards": list(self.shards),
            "scopes": sorted(self.scopes),
            "exp": self.exp,
            "path_prefix": self.path_prefix,
            "max_uses": self.max_uses,
            "jti": self.jti,
            "iat": self.iat,
        }
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(data: str) -> bytes:
    # urlsafe base64 without padding
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def mint(engine: VRL1ZeroTrustEngine, *, tenant_id: str, shards: tuple[int, int, int],
         scopes: list[str], exp: int, path_prefix: str = "", max_uses: int = 0,
         now: int | None = None) -> str:
    """Create a signed capability token. Returns an opaque base64url string."""
    now = int(time.time()) if now is None else now
    if not tenant_id:
        raise ValueError("tenant_id must be non-empty")
    if not scopes:
        raise ValueError("at least one scope is required")
    if exp <= now:
        raise ValueError("exp must be in the future")
    if max_uses < 0:
        raise ValueError("max_uses must be >= 0")
    cap = Capability(tenant_id=tenant_id, shards=tuple(shards),
                     scopes=sorted(set(scopes)), exp=exp,
                     path_prefix=path_prefix or "", max_uses=max_uses,
                     jti=secrets.token_hex(12), iat=now)
    payload = cap.canonical()
    sig = engine.sign_capability(payload)
    return _b64e(payload) + "." + sig


def parse_and_verify(engine: VRL1ZeroTrustEngine, token: str,
                     now: int | None = None) -> Capability:
    """Decode + verify a token, enforcing the expiry caveat.

    Raises CapabilityError on any failure. Path-prefix and max-uses caveats
    are enforced by the vault (they need request context / a ledger).
    """
    now = int(time.time()) if now is None else now
    try:
        payload_b64, sig = token.rsplit(".", 1)
        payload = _b64d(payload_b64)
    except (ValueError, binascii.Error):
        raise CapabilityError("malformed capability token")
    if not engine.verify_capability(payload, sig):
        raise CapabilityError("capability signature invalid")
    try:
        obj = json.loads(payload)
        cap = Capability(
            tenant_id=obj["tenant_id"], shards=tuple(obj["shards"]),
            scopes=obj["scopes"], exp=obj["exp"],
            path_prefix=obj.get("path_prefix", ""),
            max_uses=obj.get("max_uses", 0), jti=obj["jti"], iat=obj["iat"])
    except (ValueError, KeyError, TypeError):
        raise CapabilityError("malformed capability payload")
    if cap.exp <= now:
        raise CapabilityError("capability expired")
    return cap


class CapabilityUsageLedger:
    """In-memory max_uses accounting. Thread-safe, not persisted (see module doc)."""

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = threading.Lock()

    def try_use(self, jti: str, max_uses: int) -> bool:
        """Atomically consume one use. False when the budget is exhausted."""
        if max_uses <= 0:
            return True  # unlimited
        with self._lock:
            n = self._counts.get(jti, 0) + 1
            if n > max_uses:
                return False
            self._counts[jti] = n
            return True
