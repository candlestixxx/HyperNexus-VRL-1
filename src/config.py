"""
HyperNexus VRL-1: Virtual Routing Layer 1
Configuration and Environment Settings.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "HyperNexus VRL-1 Gateway"
    # Single version source is VERSION.md (see vrl1_version.app_version);
    # FastAPI wiring overrides this default from there at import time.
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    
    # Gateway Host & Port
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Security & Radial Vault
    VAULT_MASTER_KEY: str = Field(
        default="hyp-vrl1-radial-master-key-32bytes-secret!",
        description="Master cryptographic key used for radial envelope encryption"
    )
    VAULT_PERSISTENCE_PATH: str = Field(
        default="data/radial_vault.json",
        description="Path to persistent radial vector vault registry"
    )
    DEFAULT_TOKEN_BUCKET_CAPACITY: int = 1000
    DEFAULT_REFILL_RATE_PER_SEC: float = 50.0
    
    # Target Routing Defaults
    DEFAULT_TIMEOUT_SECONDS: float = 15.0
    MAX_RETRIES: int = 3
    
    # Model Context Protocol (MCP) Configuration
    MCP_ENABLED: bool = True
    MCP_HUB_NAME: str = "TormentNexus-VRL1-Bridge"
    OLLAMA_ENDPOINT: Optional[str] = "http://localhost:11434"
    HERMES_AGENT_ENDPOINT: Optional[str] = "http://localhost:8081"
    
    # Allowed CORS Origins
    CORS_ORIGINS: List[str] = ["*"]

try:
    from vrl1_version import app_version as _vrl1_app_version
    settings = Settings(APP_VERSION=_vrl1_app_version())
except Exception:
    settings = Settings()
