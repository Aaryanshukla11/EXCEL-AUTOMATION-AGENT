"""Server test fixtures for FastAPI application shell."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncGenerator

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from excel_intel.server.app import create_app
from excel_intel.server.config import ServerConfig


@pytest.fixture
def server_test_config(tmp_path: Path) -> ServerConfig:
    """Provides an isolated ServerConfig instance for testing."""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test_vault.db"

    return ServerConfig(
        env="test",
        host="127.0.0.1",
        port=8000,
        api_prefix="/api/v1",
        storage_root=storage_dir,
        database_url=f"sqlite+aiosqlite:///{db_path}",
        max_rss_mb=250,
        memory_warning_mb=235.0,
        memory_throttle_threshold_mb=180.0,
        admission_concurrency_limit=1,
        log_level="DEBUG",
        log_format="json",
    )


@pytest_asyncio.fixture
async def async_app(server_test_config: ServerConfig) -> AsyncGenerator:
    """Initializes the FastAPI application with its lifespan."""
    app = create_app(server_test_config)
    async with app.router.lifespan_context(app):
        yield app


@pytest_asyncio.fixture
async def client(async_app) -> AsyncGenerator[AsyncClient, None]:
    """Provides an AsyncClient connected to the ASGI application."""
    transport = ASGITransport(app=async_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
