"""Tests for /api/v1/health and /api/v1/ready endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
import pytest

from excel_intel.server.config import ServerConfig


@pytest.mark.asyncio
async def test_health_endpoint_success(client: AsyncClient, server_test_config: ServerConfig) -> None:
    """Verifies GET /api/v1/health returns 200 with correct memory telemetry."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert data["env"] == "test"
    assert data["max_rss_mb"] == server_test_config.max_rss_mb
    assert isinstance(data["current_rss_mb"], (int, float))
    assert data["current_rss_mb"] > 0
    assert data["active_parsing_jobs"] == 0
    assert data["admission_semaphore_available"] == 1

    # Verify correlation header
    assert "x-correlation-id" in response.headers


@pytest.mark.asyncio
async def test_readiness_endpoint_all_healthy(client: AsyncClient, server_test_config: ServerConfig) -> None:
    """Verifies GET /api/v1/ready returns 200 when all dependencies are healthy."""
    response = await client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ready"
    assert "timestamp" in data
    assert "checks" in data

    # 1. Database check
    db_check = data["checks"]["database"]
    assert db_check["status"] == "ok"
    assert "latency_ms" in db_check["details"]
    assert db_check["details"]["migrated"] is True

    # 2. Memory check
    mem_check = data["checks"]["memory"]
    assert mem_check["status"] in ("ok", "degraded")
    assert "current_rss_mb" in mem_check["details"]

    # 3. Storage check - must be sanitized without path leakage
    storage_check = data["checks"]["storage"]
    assert storage_check["status"] == "ok"
    assert storage_check["details"]["writable"] is True
    assert storage_check["details"]["storage_accessible"] is True
    assert "path" not in storage_check["details"]

    # Regression check: configured host storage path must NOT leak into response body
    raw_response = response.text
    assert str(server_test_config.storage_root) not in raw_response
    assert "test_storage" not in raw_response


@pytest.mark.asyncio
async def test_readiness_storage_probe_lifecycle_and_safety(server_test_config: ServerConfig) -> None:
    """Verifies storage write probe creates and deletes sentinel without affecting existing files."""
    from excel_intel.server.routers.health import probe_storage_writeability

    storage_root = server_test_config.storage_root
    # Create an existing user file in the directory
    user_file = storage_root / "important_user_sheet.xlsx"
    user_file.write_text("pre-existing content", encoding="utf-8")

    # Run write probe
    probe_storage_writeability(storage_root)

    # User file must be untouched
    assert user_file.exists()
    assert user_file.read_text(encoding="utf-8") == "pre-existing content"

    # No leftover .write_probe_* files
    probe_files = list(storage_root.glob(".write_probe_*"))
    assert len(probe_files) == 0


@pytest.mark.asyncio
async def test_readiness_storage_write_failure(client: AsyncClient) -> None:
    """Verifies storage write failure reports HTTP 503 without leaking host paths."""
    with patch("excel_intel.server.routers.health.probe_storage_writeability", side_effect=OSError("Read-only file system")):
        response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["storage"]["status"] == "failed"
        assert data["checks"]["storage"]["error"] == "Storage directory is not writable or inaccessible."


@pytest.mark.asyncio
async def test_readiness_db_unmigrated_failure(client: AsyncClient, async_app) -> None:
    """Verifies unmigrated database schema causes readiness to return 503."""
    db_manager = async_app.state.db_manager
    with patch.object(db_manager, "verify_migration_head", AsyncMock(return_value=False)):
        response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "failed"
        assert "not migrated to head" in data["checks"]["database"]["error"]


@pytest.mark.asyncio
async def test_readiness_endpoint_db_failure(client: AsyncClient, async_app) -> None:
    """Verifies GET /api/v1/ready returns 503 when the database is unreachable."""
    # Mock db_manager.ping to raise an error
    db_manager = async_app.state.db_manager
    with patch.object(db_manager, "ping", AsyncMock(side_effect=RuntimeError("Disk connection lost"))):
        response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "failed"
        assert "Disk connection lost" in data["checks"]["database"]["error"]


@pytest.mark.asyncio
async def test_readiness_endpoint_memory_exceeded(client: AsyncClient) -> None:
    """Verifies GET /api/v1/ready returns 503 when RSS breaches the hard ceiling."""
    with patch("excel_intel.server.routers.health.get_current_working_set_mb", return_value=260.0):
        response = await client.get("/api/v1/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["memory"]["status"] == "failed"
        assert "breached maximum ceiling" in data["checks"]["memory"]["error"]
