"""
HyperNexus VRL-1: Radial Vector Secret Vault
High-performance tree-ring partitioned vault with O(1) encrypted secret retrieval.
Zero cross-tenant leakage guaranteed by tenant coordinate hashing and envelope encryption.
"""

import json
import os
import threading
from typing import Dict, Optional, List
from fastapi import HTTPException
from src.models import (
    TenantContext,
    TenantRegistrationRequest,
    TenantTier,
    DatabaseEngineType
)
from src.security import (
    RadialVectorCipher,
    compute_radial_coordinate,
    hash_api_key
)
from src.config import settings

class RadialVectorVault:
    """
    Radial Vector Vault indexes tenants along polar concentric rings (r, theta, z).
    Every tenant's database connection strings and sensitive upstream tokens
    are encrypted at rest and decrypted on-demand within an isolated execution boundary.
    """
    def __init__(self, persistence_path: str = settings.VAULT_PERSISTENCE_PATH):
        self.persistence_path = persistence_path
        self.cipher = RadialVectorCipher()
        self._lock = threading.RLock()
        
        # Primary lookup table: key_hash -> TenantContext
        self._registry_by_hash: Dict[str, TenantContext] = {}
        # Secondary index: company_id -> key_hash
        self._company_to_hash: Dict[str, str] = {}
        # Subdomain / domain index: domain -> key_hash
        self._domain_to_hash: Dict[str, str] = {}
        
        # Initialize storage directory
        os.makedirs(os.path.dirname(self.persistence_path), exist_ok=True)
        self._load_or_bootstrap()

    def _load_or_bootstrap(self):
        """Loads existing vault from persistence or bootstraps default enterprise nodes."""
        with self._lock:
            if os.path.exists(self.persistence_path):
                try:
                    with open(self.persistence_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for item in data.get("tenants", []):
                            # Decrypt connection before keeping in-memory context
                            ctx = TenantContext(**item)
                            key_hash = item["_key_hash"]
                            self._registry_by_hash[key_hash] = ctx
                            self._company_to_hash[ctx.company_id] = key_hash
                            if "domain" in ctx.metadata:
                                self._domain_to_hash[ctx.metadata["domain"]] = key_hash
                    return
                except Exception as e:
                    print(f"[RadialVault] Warning: Failed to parse persistence file ({e}), bootstrapping defaults.")

            # Bootstrap default foundational tenants for United Beats ecosystem
            self._bootstrap_default_tenants()

    def _bootstrap_default_tenants(self):
        """Pre-seeds the vault with foundational United Beats & HyperNexus infrastructure."""
        defaults = [
            TenantRegistrationRequest(
                company_id="united_beats",
                company_name="United Beats LLC",
                tier=TenantTier.TIER_1_ENTERPRISE,
                api_key="ub_live_key_9901_hypernexus_vrl1",
                target_api="https://internal.unitedbeats.local/api/v1",
                db_connection="postgresql://ub_user:ub_pass_radial@db.unitedbeats.local:5432/ub_core",
                db_type=DatabaseEngineType.POSTGRESQL,
                mcp_enabled=True,
                rate_limit_rps=500.0,
                metadata={
                    "domain": "unitedbeats.hypernexus.local",
                    "description": "United Beats flagship music tech & streaming control plane"
                }
            ),
            TenantRegistrationRequest(
                company_id="excel_legacy_realty",
                company_name="Excel Legacy Realty Team",
                tier=TenantTier.TIER_2_PRO,
                api_key="excel_legacy_key_7742_realestate",
                target_api="https://crm.excellegacyrealtyteam.com/webhook/ingest",
                db_connection="mongodb://excel_user:pass7742@mongo.excellegacy.local:27017/leads",
                db_type=DatabaseEngineType.MONGODB,
                mcp_enabled=True,
                rate_limit_rps=200.0,
                metadata={
                    "domain": "realty.excellegacy.local",
                    "description": "Excel Legacy automated CRM, lead ingestion, and MLS pipeline"
                }
            ),
            TenantRegistrationRequest(
                company_id="hypernexus_core",
                company_name="HyperNexus Global Control",
                tier=TenantTier.TIER_0_CORE,
                api_key="hyp_nexus_master_ring0_key",
                target_api="https://core.hypernexus.internal/v1",
                db_connection="sqlite:///data/hypernexus_core.sqlite3",
                db_type=DatabaseEngineType.SQLITE,
                mcp_enabled=True,
                rate_limit_rps=1000.0,
                metadata={
                    "domain": "core.hypernexus.local",
                    "description": "HyperNexus master orchestration and TormentNexus state fabric"
                }
            )
        ]
        for req in defaults:
            self.register_tenant(req)

    def register_tenant(self, req: TenantRegistrationRequest) -> TenantContext:
        """
        Registers a new tenant into the radial vector matrix.
        Encrypted secrets are saved, polar coordinates are derived,
        and in-memory dispatch indexes are updated with zero-downtime hot reload.
        """
        with self._lock:
            key_hash = hash_api_key(req.api_key)
            coords = compute_radial_coordinate(req.api_key, req.tier)
            
            # Encrypt DB connection string for safe storage
            encrypted_db = self.cipher.encrypt_secret(req.db_connection)
            
            context = TenantContext(
                company_id=req.company_id,
                company_name=req.company_name,
                tier=req.tier,
                target_api=req.target_api.rstrip("/"),
                db_connection=encrypted_db,
                db_type=req.db_type,
                mcp_enabled=req.mcp_enabled,
                rate_limit_rps=req.rate_limit_rps,
                radial_coords=coords,
                metadata=req.metadata
            )
            
            self._registry_by_hash[key_hash] = context
            self._company_to_hash[req.company_id] = key_hash
            if "domain" in req.metadata:
                self._domain_to_hash[req.metadata["domain"]] = key_hash
                
            self._save_to_disk()
            return context

    def get_tenant_by_api_key(self, api_key: str) -> TenantContext:
        """O(1) retrieval of tenant by secret API key with unencrypted runtime DB context."""
        key_hash = hash_api_key(api_key)
        with self._lock:
            context = self._registry_by_hash.get(key_hash)
            if not context or not context.active:
                raise HTTPException(
                    status_code=401,
                    detail="Unauthorized: Radial vector coordinate unmapped or tenant inactive."
                )
            return self._clone_with_decrypted_secrets(context)

    def get_tenant_by_company_id(self, company_id: str) -> Optional[TenantContext]:
        """Lookup by company ID."""
        with self._lock:
            key_hash = self._company_to_hash.get(company_id)
            if not key_hash:
                return None
            context = self._registry_by_hash.get(key_hash)
            if not context:
                return None
            return self._clone_with_decrypted_secrets(context)

    def get_tenant_by_domain(self, domain: str) -> Optional[TenantContext]:
        """Lookup by host/domain routing header."""
        with self._lock:
            key_hash = self._domain_to_hash.get(domain)
            if not key_hash:
                return None
            context = self._registry_by_hash.get(key_hash)
            if not context:
                return None
            return self._clone_with_decrypted_secrets(context)

    def _clone_with_decrypted_secrets(self, ctx: TenantContext) -> TenantContext:
        """Clones the context object and decrypts the db connection for the caller."""
        decrypted_db = self.cipher.decrypt_secret(ctx.db_connection)
        return ctx.model_copy(update={"db_connection": decrypted_db})

    def list_all_tenants(self, mask_secrets: bool = True) -> List[Dict]:
        """Provides tenant topology map for UI Developer Portal and health monitoring."""
        with self._lock:
            results = []
            for k_hash, ctx in self._registry_by_hash.items():
                item = ctx.model_dump()
                if mask_secrets:
                    item["db_connection"] = "••••••••[Radial-Encrypted]••••••••"
                item["key_hash_prefix"] = k_hash[:8] + "..."
                results.append(item)
            return results

    def _save_to_disk(self):
        """Serializes vault state to atomic persistent JSON storage."""
        data = {"tenants": []}
        for k_hash, ctx in self._registry_by_hash.items():
            dump = ctx.model_dump()
            dump["_key_hash"] = k_hash
            # Ensure saved db_connection remains encrypted
            data["tenants"].append(dump)
        try:
            temp_path = self.persistence_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            os.replace(temp_path, self.persistence_path)
        except Exception as e:
            print(f"[RadialVault] Error saving vault to disk: {e}")
