"""FastAPI dependency injection providers."""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from excel_intel.server.admission import AdmissionController
from excel_intel.server.config import ServerConfig
from excel_intel.server.database.session import DatabaseManager
from excel_intel.server.services.discovery_service import DiscoveryService
from excel_intel.server.services.quality_service import QualityService
from excel_intel.server.services.storage_service import StorageService


def get_config(request: Request) -> ServerConfig:
    """Provides the active ServerConfig instance from application state."""
    return getattr(request.app.state, "config")


def get_admission_controller(request: Request) -> AdmissionController:
    """Provides the active AdmissionController instance from application state."""
    return getattr(request.app.state, "admission_controller")


def get_db_manager(request: Request) -> DatabaseManager:
    """Provides the DatabaseManager instance from application state."""
    return getattr(request.app.state, "db_manager")


def get_storage_service(request: Request) -> StorageService:
    """Provides the StorageService instance from application state."""
    return getattr(request.app.state, "storage_service")


def get_discovery_service(request: Request) -> DiscoveryService:
    """Provides the DiscoveryService instance from application state."""
    return getattr(request.app.state, "discovery_service")


def get_quality_service(request: Request) -> QualityService:
    """Provides the QualityService instance from application state."""
    return getattr(request.app.state, "quality_service")


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an active transactional AsyncSession."""
    manager: DatabaseManager = getattr(request.app.state, "db_manager")
    async with manager.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
