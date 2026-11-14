"""
HyperNexus VRL-1: Data Models and Schemas
Strict Pydantic schemas for multi-tenant isolation, radial vector indexing,
API dispatching, and MCP state representation.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime, timezone
from enum import Enum

class TenantTier(str, Enum):
    TIER_0_CORE = "tier_0_core"         # Ring 0: Inner Core (HyperNexus Infrastructure)
    TIER_1_ENTERPRISE = "tier_1_enterprise" # Ring 1: United Beats / Enterprise Flagship
    TIER_2_PRO = "tier_2_pro"           # Ring 2: Excel Legacy Realty / High-throughput
    TIER_3_STANDARD = "tier_3_standard" # Ring 3: Third-Party & Community Integrations

class DatabaseEngineType(str, Enum):
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    SQLITE = "sqlite"
    MYSQL = "mysql"
    REDIS = "redis"

class RadialVectorCoordinate(BaseModel):
    """
    Polar/Radial coordinate space (r, theta, z) for O(1) secret retrieval.
    r (radius): Security ring index (0 to 3).
    theta (angle): Angle in radians [0, 2pi) derived from SHA256 hash modular mapping.
    z (depth): Encryption key generation / rotation depth.
    """
    r: float = Field(..., description="Radial ring depth representing isolation level")
    theta: float = Field(..., description="Angular offset in radians on tree ring")
    z: int = Field(default=1, description="Envelope cipher version depth")

class TenantRegistrationRequest(BaseModel):
    company_id: str = Field(..., description="Unique alphanumeric identifier (e.g. united_beats)")
    company_name: str = Field(..., description="Display company name")
    tier: TenantTier = Field(default=TenantTier.TIER_2_PRO, description="Tenant isolation ring")
    api_key: str = Field(..., description="Inbound authentication key provided to tenant")
    target_api: str = Field(..., description="Upstream destination base URL")
    db_connection: str = Field(..., description="Tenant-isolated database connection string")
    db_type: DatabaseEngineType = Field(default=DatabaseEngineType.POSTGRESQL)
    mcp_enabled: bool = Field(default=True, description="Enable TormentNexus MCP AI synchronization")
    rate_limit_rps: float = Field(default=100.0, description="Tokens per second allowed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary tenant properties")

class TenantContext(BaseModel):
    company_id: str
    company_name: str
    tier: TenantTier
    target_api: str
    db_connection: str
    db_type: DatabaseEngineType
    mcp_enabled: bool
    rate_limit_rps: float
    radial_coords: RadialVectorCoordinate
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DispatchResponse(BaseModel):
    status: str
    company_id: str
    target_url: str
    duration_ms: float
    db_logged: bool
    mcp_synced: bool
    upstream_status: int
    upstream_response: Any

class SystemTelemetry(BaseModel):
    active_tenants: int
    total_dispatched_requests: int
    avg_latency_ms: float
    active_db_pools: int
    radial_vector_rings: Dict[str, int]
    system_uptime_seconds: float
