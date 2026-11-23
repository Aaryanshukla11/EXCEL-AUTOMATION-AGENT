"""Server configuration and environment variable loading.

Builds upon PlatformConfig from M01 and adds server-specific settings
with environment-variable validation (prefixed with EXCEL_INTEL_).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from excel_intel.config import PlatformConfig, load_config
from excel_intel.exceptions import ConfigurationError


class ServerConfig(BaseModel):
    """Centralized, immutable server runtime configuration."""

    env: Literal["production", "development", "test"] = Field(
        default="development",
        description="Operating environment mode.",
    )
    host: str = Field(
        default="127.0.0.1",
        description="Bind host for FastAPI server (must be localhost in dev mode).",
    )
    port: int = Field(
        default=8000,
        description="Port for HTTP listener.",
        ge=1,
        le=65535,
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed CORS origin domains.",
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="Root prefix for version 1 API routes.",
    )
    storage_root: Path = Field(
        default_factory=lambda: Path("./storage").resolve(),
        description="Base path for workbook storage and staging directories.",
    )
    database_url: str = Field(
        default="sqlite+aiosqlite:///audit_vault.db",
        description="SQLAlchemy connection URI for SQLite database.",
    )
    token_ttl_seconds: int = Field(
        default=900,
        description="TTL for HMAC approval tokens (15 minutes).",
        ge=60,
        le=86400,
    )
    max_rss_mb: int = Field(
        default=250,
        description="Hard process memory ceiling in MiB (ADR-001).",
        ge=64,
        le=1024,
    )
    memory_warning_mb: float = Field(
        default=235.0,
        description="Soft memory warning ceiling in MiB.",
        ge=50.0,
        le=1000.0,
    )
    memory_throttle_threshold_mb: float = Field(
        default=180.0,
        description="Preflight memory limit for accepting heavy parsing requests.",
        ge=32.0,
        le=500.0,
    )
    admission_concurrency_limit: int = Field(
        default=1,
        description="Maximum concurrent heavy workbook parsing tasks.",
        ge=1,
        le=8,
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging verbosity threshold.",
    )
    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Format for structured logs.",
    )

    @field_validator("storage_root", mode="after")
    @classmethod
    def validate_storage_root(cls, v: Path) -> Path:
        resolved = v.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    model_config = {
        "frozen": True,
        "extra": "ignore",
    }


def get_server_config(overrides: Optional[dict[str, Any]] = None) -> ServerConfig:
    """Loads server configuration from environment variables prefixed with EXCEL_INTEL_."""
    # Start with base platform configuration defaults
    base_platform = load_config()

    env_vars: dict[str, Any] = {
        "env": base_platform.env,
        "log_level": base_platform.log_level,
        "log_format": base_platform.log_format,
        "storage_root": base_platform.storage_root,
        "token_ttl_seconds": base_platform.token_ttl_seconds,
        "max_rss_mb": base_platform.max_rss_mb,
    }

    if base_platform.sqlite_vault_path:
        db_path = str(base_platform.sqlite_vault_path)
        if not db_path.startswith("sqlite"):
            env_vars["database_url"] = f"sqlite+aiosqlite:///{db_path}"

    prefix = "EXCEL_INTEL_"
    for key, val in os.environ.items():
        if key.startswith(prefix):
            normalized_key = key[len(prefix) :].lower()
            if normalized_key == "server_host" or normalized_key == "host":
                env_vars["host"] = val
            elif normalized_key == "server_port" or normalized_key == "port":
                try:
                    env_vars["port"] = int(val)
                except ValueError:
                    pass
            elif normalized_key == "cors_origins":
                env_vars["cors_origins"] = [o.strip() for o in val.split(",") if o.strip()]
            elif normalized_key == "database_url":
                env_vars["database_url"] = val
            elif normalized_key == "memory_throttle_threshold_mb":
                try:
                    env_vars["memory_throttle_threshold_mb"] = float(val)
                except ValueError:
                    pass
            elif normalized_key == "admission_concurrency_limit":
                try:
                    env_vars["admission_concurrency_limit"] = int(val)
                except ValueError:
                    pass
            elif normalized_key in ServerConfig.model_fields:
                env_vars[normalized_key] = val

    if overrides:
        env_vars.update(overrides)

    try:
        return ServerConfig(**env_vars)
    except Exception as e:
        raise ConfigurationError(
            f"Invalid server configuration: {e}",
            context={"errors": str(e), "env_vars": {k: str(v) for k, v in env_vars.items()}},
        ) from e
