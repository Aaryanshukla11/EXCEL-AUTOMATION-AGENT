"""FastAPI application factory and lifecycle supervisor.

Constructs the production application shell with:
- Lifespan context management (DB initialization, engine cleanup)
- Request correlation ID middleware
- Structured JSON access logging
- CORS configuration
- RFC 7807 error handlers
- Versioned routing (/api/v1)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from excel_intel.logging import StructuredLogger, get_logger
from excel_intel.server.admission import AdmissionController
from excel_intel.server.config import ServerConfig, get_server_config
from excel_intel.server.database.session import DatabaseManager
from excel_intel.server.errors import register_error_handlers
from excel_intel.server.middleware import (
    CorrelationIdMiddleware,
    RequestLoggingMiddleware,
)
from excel_intel.server.routers.discovery import router as discovery_router
from excel_intel.server.routers.health import router as health_router
from excel_intel.server.routers.quality import router as quality_router
from excel_intel.server.routers.workbooks import router as workbooks_router
from excel_intel.server.services.discovery_service import DiscoveryService
from excel_intel.server.services.quality_service import QualityService
from excel_intel.server.services.storage_service import StorageService

logger: StructuredLogger = get_logger("ApplicationShell")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown."""
    config: ServerConfig = app.state.config
    logger.info(
        "ApplicationStarting",
        message="Initializing Autonomous Excel Intelligence Platform backend shell...",
        context={
            "env": config.env,
            "host": config.host,
            "port": config.port,
            "max_rss_mb": config.max_rss_mb,
            "storage_root": str(config.storage_root),
        },
    )

    # 1. Initialize Admission Controller
    admission_ctrl = AdmissionController(
        concurrency_limit=config.admission_concurrency_limit,
        throttle_threshold_mb=config.memory_throttle_threshold_mb,
        hard_limit_mb=float(config.max_rss_mb),
    )
    app.state.admission_controller = admission_ctrl

    # 2. Initialize Database Engine and verify schema
    db_manager = DatabaseManager(database_url=config.database_url)
    await db_manager.initialize()
    app.state.db_manager = db_manager

    # 3. Initialize Storage Service
    storage_service = StorageService(
        storage_root=config.storage_root,
        max_upload_bytes=config.max_rss_mb * 1024 * 1024,
    )
    app.state.storage_service = storage_service

    # 4. Initialize Discovery Service
    discovery_service = DiscoveryService()
    app.state.discovery_service = discovery_service

    # 5. Initialize Quality Service
    quality_service = QualityService(discovery_service=discovery_service)
    app.state.quality_service = quality_service

    logger.info(
        "ApplicationReady",
        message="Backend foundation initialized successfully. Ready for incoming requests.",
    )

    yield

    # Shutdown sequence
    logger.info(
        "ApplicationShuttingDown",
        message="Shutting down application shell...",
    )
    await db_manager.dispose()
    logger.info("ApplicationStopped", message="Backend service stopped cleanly.")


def create_app(config: Optional[ServerConfig] = None) -> FastAPI:
    """Factory creating and configuring the FastAPI backend application."""
    if config is None:
        config = get_server_config()

    app = FastAPI(
        title="Autonomous Excel Intelligence Platform API",
        description="Backend service engine for autonomous spreadsheet analysis, discovery, and execution.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.env != "production" else None,
        redoc_url="/redoc" if config.env != "production" else None,
    )

    # Store configuration on application state
    app.state.config = config

    # Register Middlewares (Order: Outer to Inner)
    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Correlation ID Middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 3. Structured Request Logging Middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Register RFC 7807 Exception Handlers
    register_error_handlers(app)

    # Include Versioned Routers (/api/v1)
    app.include_router(health_router, prefix=config.api_prefix)
    app.include_router(workbooks_router, prefix=config.api_prefix)
    app.include_router(discovery_router, prefix=config.api_prefix)
    app.include_router(quality_router, prefix=config.api_prefix)

    return app
