"""
HyperNexus VRL-1: Cryptographic Engine & Radial Vector Mapping
Zero-knowledge tenant key derivation and envelope cipher routines.
"""

import math
import hashlib
import base64
from typing import Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from src.models import TenantTier, RadialVectorCoordinate
from src.config import settings

def derive_fernet_key(master_secret: str, salt: bytes) -> bytes:
    """Derives a 32-byte url-safe base64 key suitable for Fernet symmetric encryption."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000
    )
    key = kdf.derive(master_secret.encode())
    return base64.urlsafe_b64encode(key)

class RadialVectorCipher:
    """
    Encrypts secrets in the Radial Vector Vault using dynamic key derivations
    indexed by tenant coordinates (r, theta, z).
    """
    def __init__(self, master_key: str = settings.VAULT_MASTER_KEY):
        self.master_key = master_key
        # Base salt fixed for deterministic tier envelope key expansion
        self.base_salt = b"HyperNexus-VRL1-RadialSalt-2026"
        self._cipher = Fernet(derive_fernet_key(master_key, self.base_salt))

    def encrypt_secret(self, plaintext: str) -> str:
        """Encrypts sensitive credentials (DB URI, upstream tokens)."""
        encrypted_bytes = self._cipher.encrypt(plaintext.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt_secret(self, ciphertext: str) -> str:
        """Decrypts sensitive credentials safely."""
        decrypted_bytes = self._cipher.decrypt(ciphertext.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")

def compute_radial_coordinate(api_key: str, tier: TenantTier, z_depth: int = 1) -> RadialVectorCoordinate:
    """
    Computes deterministic tree-ring polar coordinates (r, theta, z).
    r is mapped from the tenant's security tier ring (0 to 3).
    theta is computed as (hash_int % 100000) / 100000.0 * 2pi, producing uniform
    angular distribution across the concentric ring, guaranteeing O(1) partitioned vector lookup.
    """
    tier_ring_map = {
        TenantTier.TIER_0_CORE: 0.5,
        TenantTier.TIER_1_ENTERPRISE: 1.0,
        TenantTier.TIER_2_PRO: 1.5,
        TenantTier.TIER_3_STANDARD: 2.0
    }
    r = tier_ring_map.get(tier, 2.0)
    
    # Hash the key with SHA-256
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    hash_int = int(digest[:12], 16)
    theta = (hash_int % 1_000_000) / 1_000_000.0 * 2.0 * math.pi
    
    return RadialVectorCoordinate(r=round(r, 2), theta=round(theta, 5), z=z_depth)

def hash_api_key(api_key: str) -> str:
    """Produces SHA-256 hex digest for lookup dictionary indexing."""
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()
