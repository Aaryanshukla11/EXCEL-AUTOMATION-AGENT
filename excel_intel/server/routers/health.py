"""Health and readiness monitoring endpoints.

Conforms strictly with canonical contract in FRONTEND_BACKEND_API_CONTRACT.md.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any, Literal, Optional
import uuid

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from excel_intel.server.admission import (
    AdmissionController,
    get_current_working_set_mb,
)
from excel_intel.server.config import ServerConfig
from excel_intel.server.database.session import DatabaseManager
from excel_intel.server.dependencies import (
    get_admission_controller,
    get_config,
    get_db_manager,
)

router = APIRouter(tags=["System"])


def probe_storage_writeability(storage_path: Path) -> None:
    """Verifies that storage_path exists and is writable.

    Guarantees ephemeral probe file cleanup via try...finally without deleting unrelated files.
    """
    if not storage_path.exists():
        storage_path.mkdir(parents=True, exist_ok=True)

    sentinel = storage_path / f".write_probe_{uuid.uuid4().hex}"
    try:
        with open(sentinel, "wb") as f:
            f.write(b"probe\n")
            f.flush()
            os.fsync(f.fileno())
    finally:
        try:
            if sentinel.exists():
                sentinel.unlink()
        except OSError:
            pass


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    status: Literal["healthy"] = Field(
        default="healthy",
        description="Application process liveness status.",
    )
    version: str = Field(
        default="0.1.0",
        description="Platform semantic version.",
    )
    env: str = Field(
        ...,
        description="Operating environment (production/development/test).",
    )
    max_rss_mb: int = Field(
        ...,
        description="Configured maximum process RSS ceiling.",
    )
    current_rss_mb: float = Field(
        ...,
        description="Active process working set memory in MiB.",
    )
    active_parsing_jobs: int = Field(
        ...,
        description="Number of concurrent heavy parsing operations currently executing.",
    )
    admission_semaphore_available: int = Field(
        ...,
        description="Remaining admission semaphore slots for heavy tasks.",
    )


class DependencyCheck(BaseModel):
    """Individual dependency health status."""

    status: Literal["ok", "degraded", "failed"]
    details: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class ReadinessResponse(BaseModel):
    """Readiness probe response model verifying actual dependency health."""

    status: Literal["ready", "not_ready"]
    timestamp: str
    checks: dict[str, DependencyCheck]


@router.get("/health", response_model=HealthResponse)
async def check_health(
    config: ServerConfig = Depends(get_config),
    admission_ctrl: AdmissionController = Depends(get_admission_controller),
) -> HealthResponse:
    """Returns server liveness, memory telemetry, and version."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        env=config.env,
        max_rss_mb=config.max_rss_mb,
        current_rss_mb=round(get_current_working_set_mb(), 2),
        active_parsing_jobs=admission_ctrl.active_parsing_jobs,
        admission_semaphore_available=admission_ctrl.available_slots,
    )


@router.get("/ready", response_model=ReadinessResponse)
async def check_readiness(
    response: Response,
    config: ServerConfig = Depends(get_config),
    admission_ctrl: AdmissionController = Depends(get_admission_controller),
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> ReadinessResponse:
    """Verifies actual availability of all runtime dependencies implemented in B1.

    Does not report healthy merely because configuration exists:
    1. Tests actual SQLite connection with ping (SELECT 1).
    2. Validates memory budget headroom.
    3. Verifies physical storage root directory accessibility and writeability.
    """
    checks: dict[str, DependencyCheck] = {}
    is_ready = True

    # 1. Database connectivity check
    try:
        latency_ms = await db_manager.ping()
        is_migrated = await db_manager.verify_migration_head()
        if not is_migrated:
            is_ready = False
            checks["database"] = DependencyCheck(
                status="failed",
                error="Database schema is not migrated to head revision.",
            )
        else:
            checks["database"] = DependencyCheck(
                status="ok",
                details={
                    "latency_ms": round(latency_ms, 2),
                    "engine": "sqlite_wal",
                    "migrated": True,
                },
            )
    except Exception as exc:
        is_ready = False
        checks["database"] = DependencyCheck(
            status="failed",
            error=f"Database ping failed: {exc}",
        )

    # 2. Process memory budget check
    current_rss_mb = round(get_current_working_set_mb(), 2)
    if current_rss_mb >= config.max_rss_mb:
        is_ready = False
        checks["memory"] = DependencyCheck(
            status="failed",
            details={
                "current_rss_mb": current_rss_mb,
                "max_rss_mb": config.max_rss_mb,
            },
            error=f"Process memory ({current_rss_mb} MiB) breached maximum ceiling ({config.max_rss_mb} MiB)",
        )
    elif current_rss_mb >= config.memory_warning_mb:
        checks["memory"] = DependencyCheck(
            status="degraded",
            details={
                "current_rss_mb": current_rss_mb,
                "warning_threshold_mb": config.memory_warning_mb,
                "max_rss_mb": config.max_rss_mb,
            },
        )
    else:
        checks["memory"] = DependencyCheck(
            status="ok",
            details={
                "current_rss_mb": current_rss_mb,
                "warning_threshold_mb": config.memory_warning_mb,
                "max_rss_mb": config.max_rss_mb,
            },
        )

    # 3. Storage directory accessibility check (Sanitized - no host paths leaked)
    try:
        storage_path: Path = config.storage_root
        probe_storage_writeability(storage_path)

        checks["storage"] = DependencyCheck(
            status="ok",
            details={
                "storage_accessible": True,
                "writable": True,
                "storage_type": "filesystem",
            },
        )
    except Exception:
        is_ready = False
        checks["storage"] = DependencyCheck(
            status="failed",
            error="Storage directory is not writable or inaccessible.",
        )

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="not_ready",
            timestamp=timestamp,
            checks=checks,
        )

    return ReadinessResponse(
        status="ready",
        timestamp=timestamp,
        checks=checks,
    )
