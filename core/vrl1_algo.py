"""
HyperNexus VRL-1 — Tier-1 zero-trust engine (corrected protocol).

Locked parameters (docs/SPEC.md):
- d = 4: one uint64 radius word + three uint64 angular shards = 256 bits.
- Exact integer equality only. No tolerance, no fuzzy match, ever.
- Coordinates are STATIC per (tenant, key, epoch). A nonce never enters
  the coordinate; it protects the per-request proof instead.
- Per-request proof of possession: HMAC(proof_key, nonce|ts|method|path|body_hash).
  A stolen coordinate vector without the key therefore passes nothing.
- Per-tenant keys via HKDF from the master key; records AEAD-bound to
  (tenant, radius, shards, epoch, scopes) as associated data.

Prototype hash is HMAC-SHA256. It is NOT a drop-in Poseidon replacement:
a ZK tier needs a field-native commitment designed alongside the circuit.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import struct
import threading
import time
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

UINT64 = 1 << 64


def _canon(*fields: bytes) -> bytes:
    """Length-prefixed canonical encoding (kills ':'-style ambiguity)."""
    out = b"VRL1\x01"
    for f in fields:
        out += struct.pack(">Q", len(f)) + f
    return out


def _u64s(digest: bytes) -> tuple[int, tuple[int, int, int]]:
    w = struct.unpack(">4Q", digest[:32])
    return w[0], (w[1], w[2], w[3])


@dataclass(frozen=True)
class Ring:
    """Tenant ring over the uint64 radius space, [r_min, r_max)."""
    r_min: int
    r_max: int

    def __post_init__(self) -> None:
        if not (0 <= self.r_min < self.r_max <= UINT64):
            raise ValueError("require 0 <= r_min < r_max <= 2**64")

    def contains(self, r: int) -> bool:
        return self.r_min <= r < self.r_max

    def overlaps(self, other: "Ring") -> bool:
        return self.r_min < other.r_max and other.r_min < self.r_max


class NonceLedger:
    """Tenant-scoped, expiring, bounded replay ledger.

    A nonce is recorded ONLY after a request fully verifies, so failed
    attempts cannot poison a victim's nonce. Thread-safe for concurrent agents.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 1_000_000) -> None:
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._seen: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    def check_and_record(self, tenant_id: str, nonce: str, now: float | None = None) -> bool:
        """Atomically: False if replayed/expired-ledger-full, else record + True."""
        now = time.time() if now is None else now
        key = (tenant_id, nonce)
        with self._lock:
            self._seen = {k: t for k, t in self._seen.items() if now - t < self.ttl}
            if key in self._seen:
                return False
            if len(self._seen) >= self.max_entries:
                return False  # fail closed under flood rather than evict silently
            self._seen[key] = now
            return True


class VRL1ZeroTrustEngine:
    def __init__(self, master_key: bytes, nonce_ledger: NonceLedger | None = None) -> None:
        if len(master_key) < 32:
            raise ValueError("master_key must be >= 32 bytes (use KMS/HSM in production)")
        self._master = master_key
        self.d = 4
        self.nonces = nonce_ledger or NonceLedger()
        self._tenant_keys: dict[str, bytes] = {}
        self._lock = threading.Lock()

    # -- key hierarchy ------------------------------------------------------
    def _tenant_key(self, tenant_id: str) -> bytes:
        with self._lock:
            key = self._tenant_keys.get(tenant_id)
            if key is None:
                key = HKDF(algorithm=hashes.SHA256(), length=32,
                           salt=None, info=b"vrl1-tenant:" + tenant_id.encode()
                           ).derive(self._master)
                self._tenant_keys[tenant_id] = key
            return key

    @staticmethod
    def generate_api_key() -> str:
        """256-bit CSPRNG key. The system issues keys; it does not accept passwords."""
        return secrets.token_urlsafe(32)

    # -- coordinates (static per epoch; NO nonce here) ------------------------
    def derive_coordinate(self, tenant_id: str, api_key: str, epoch: int
                          ) -> tuple[int, tuple[int, int, int]]:
        msg = _canon(tenant_id.encode(), api_key.encode(), struct.pack(">q", epoch))
        digest = hmac.new(self._tenant_key(tenant_id), msg, hashlib.sha256).digest()
        return _u64s(digest)

    def proof_key(self, tenant_id: str, api_key: str) -> bytes:
        """Key the client uses to prove possession per request."""
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                    info=b"vrl1-proof:" + tenant_id.encode()).derive(api_key.encode())

    # -- per-request proof ------------------------------------------------------
    @staticmethod
    def _proof_msg(nonce: str, ts: int, method: str, path: str, body: bytes) -> bytes:
        return _canon(nonce.encode(), struct.pack(">q", ts), method.upper().encode(),
                      path.encode(), hashlib.sha256(body).digest())

    def make_proof(self, tenant_id: str, api_key: str, nonce: str, ts: int,
                   method: str, path: str, body: bytes = b"") -> str:
        return hmac.new(self.proof_key(tenant_id, api_key),
                        self._proof_msg(nonce, ts, method, path, body),
                        hashlib.sha256).hexdigest()

    def verify_request(self, *, tenant_id: str, api_key: str, epoch: int,
                       current_epoch: int, ring: Ring,
                       target_shards: tuple[int, int, int],
                       nonce: str, ts: int, method: str, path: str,
                       body: bytes, proof: str, max_skew_seconds: int = 120,
                       now: float | None = None) -> bool:
        """Full statement: freshness + proof-of-possession + range + exact shard.

        The nonce is burned only if every other check passes (enforced by
        recording it last, atomically, via check_and_record)."""
        now = time.time() if now is None else now
        # 1. Freshness: epoch must be current (or previous during rotation dual-read)
        if epoch not in (current_epoch, current_epoch - 1):
            return False
        if abs(now - ts) > max_skew_seconds:
            return False
        # 2. Proof of possession (constant-time compare)
        expected = self.make_proof(tenant_id, api_key, nonce, ts, method, path, body)
        if not hmac.compare_digest(expected, proof):
            return False
        # 3+4. Range + exact shard match on the re-derived coordinate
        radius, shards = self.derive_coordinate(tenant_id, api_key, epoch)
        if not ring.contains(radius):
            return False
        if shards != tuple(target_shards):
            return False
        # Replay: burn the nonce only now that everything else passed.
        return self.nonces.check_and_record(tenant_id, nonce, now=now)

    def sign_root(self, root_hex: str) -> str:
        """HMAC signature over a transparency root (master-derived signing key)."""
        sig_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                       info=b"vrl1-sign:transparency").derive(self._master)
        return hmac.new(sig_key, bytes.fromhex(root_hex), hashlib.sha256).hexdigest()

    def verify_root_signature(self, root_hex: str, signature: str) -> bool:
        return hmac.compare_digest(self.sign_root(root_hex), signature)

    # -- AEAD record binding ------------------------------------------------------
    def _record_key(self, tenant_id: str) -> bytes:
        return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                    info=b"vrl1-record:" + tenant_id.encode()).derive(self._master)

    @staticmethod
    def _aad(tenant_id: str, radius: int, shards: tuple, epoch: int, scopes: list[str]) -> bytes:
        return _canon(tenant_id.encode(), struct.pack(">Q", radius),
                      struct.pack(">3Q", *shards), struct.pack(">q", epoch),
                      json.dumps(sorted(scopes)).encode())

    def seal_record(self, tenant_id: str, radius: int, shards: tuple, epoch: int,
                    scopes: list[str], record: dict) -> bytes:
        aead = ChaCha20Poly1305(self._record_key(tenant_id))
        nonce = secrets.token_bytes(12)
        ct = aead.encrypt(nonce, json.dumps(record).encode(),
                          self._aad(tenant_id, radius, shards, epoch, scopes))
        return nonce + ct

    def open_record(self, tenant_id: str, radius: int, shards: tuple, epoch: int,
                    scopes: list[str], blob: bytes) -> dict:
        """Raises cryptography.exceptions.InvalidTag if moved/tampered/rolled."""
        aead = ChaCha20Poly1305(self._record_key(tenant_id))
        pt = aead.decrypt(blob[:12], blob[12:],
                          self._aad(tenant_id, radius, shards, epoch, scopes))
        return json.loads(pt)
