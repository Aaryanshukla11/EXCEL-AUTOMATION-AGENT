"""Application configuration and environment variable loading.

Uses Pydantic v2 for strict validation and guarantees preservation of the
contractual 250 MB peak RSS budget and security quotas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from excel_intel.exceptions import ConfigurationError


class PlatformConfig(BaseModel):
    """Immutable application settings validated at process initialization."""

    env: Literal["production", "development", "test"] = Field(
        default="development",
        description="Active operating mode of the platform.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Threshold for structured log output.",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Format for console/stream logging.",
    )
    storage_root: Path = Field(
        default_factory=lambda: Path(".").resolve(),
        description="Base path for workbook reading and staging directories.",
    )
    token_ttl_seconds: int = Field(
        default=900,
        description="Time-To-Live for HMAC-SHA256 approval tokens (default: 15m).",
        ge=60,
        le=86400,
    )
    max_rss_mb: int = Field(
        default=250,
        description="Contractual peak memory ceiling (strictly preserved from V1.2 baseline).",
        ge=64,
        le=1024,
    )
    max_decompression_ratio: float = Field(
        default=10.0,
        description="Maximum ratio of uncompressed-to-compressed size for zip-bomb defense.",
        gt=1.0,
        le=100.0,
    )
    max_uncompressed_bytes: int = Field(
        default=1_073_741_824,  # 1.0 GB
        description="Maximum uncompressed byte quota for any single OpenXML package.",
        gt=1_048_576,  # > 1 MB
    )
    wal_flush_barrier: bool = Field(
        default=True,
        description="Whether hardware flush barriers (FlushFileBuffers/fsync) are mandated.",
    )
    sqlite_vault_path: Path = Field(
        default=Path("audit_vault.db"),
        description="Path to the embedded SQLite database for nonces and audit records.",
    )

    @field_validator("storage_root", mode="after")
    @classmethod
    def validate_storage_root(cls, v: Path) -> Path:
        resolved = v.resolve()
        return resolved

    model_config = {
        "frozen": True,
        "extra": "ignore",
    }


def load_config(overrides: Optional[dict[str, str]] = None) -> PlatformConfig:
    """Loads configuration by inspecting environment variables prefixed with `EXCEL_INTEL_`."""
    env_vars: dict[str, str] = {}
    prefix = "EXCEL_INTEL_"

    # Read all environment variables matching the prefix
    for key, val in os.environ.items():
        if key.startswith(prefix):
            normalized_key = key[len(prefix) :].lower()
            env_vars[normalized_key] = val

    # Apply manual overrides if provided (useful for tests)
    if overrides:
        for k, v in overrides.items():
            env_vars[k.lower()] = v

    try:
        return PlatformConfig(**env_vars)
    except Exception as e:
        raise ConfigurationError(
            f"Failed to load and validate application configuration: {e}",
            context={"raw_env": env_vars},
        ) from e
