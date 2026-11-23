"""Database engine creation, session management, and SQLite PRAGMA enforcement.

Guarantees ADR durability requirements:
- PRAGMA journal_mode = WAL;
- PRAGMA synchronous = FULL;
- PRAGMA foreign_keys = ON;
- PRAGMA busy_timeout = 5000;
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from excel_intel.logging import StructuredLogger, get_logger
from excel_intel.server.database.models import Base

logger: StructuredLogger = get_logger("DatabaseSession")


def _attach_sqlite_pragmas(engine: AsyncEngine) -> None:
    """Enforces SQLite WAL, FULL synchronous, foreign keys, and busy timeout on every connection."""

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragmas(dbapi_connection: any, connection_record: any) -> None:  # type: ignore
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = FULL;")
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
        finally:
            cursor.close()


def create_database_engine(
    database_url: str,
    echo: bool = False,
) -> AsyncEngine:
    """Creates a configured AsyncEngine for SQLite with required PRAGMAs."""
    is_sqlite = database_url.startswith("sqlite")
    connect_args = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        database_url,
        echo=echo,
        connect_args=connect_args,
    )

    if is_sqlite:
        _attach_sqlite_pragmas(engine)

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Creates an async sessionmaker bound to the engine."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
        class_=AsyncSession,
    )


class DatabaseManager:
    """Manages database lifecycle, table creation, and connection pinging."""

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        alembic_ini_path: Optional[str] = None,
    ) -> None:
        self._database_url = database_url
        self._engine = create_database_engine(database_url, echo=echo)
        self._session_factory = create_session_factory(self._engine)
        self._alembic_ini_path = alembic_ini_path or "alembic.ini"
        self._migration_lock = asyncio.Lock()
        self._initialized: bool = False

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def _run_alembic_migrations(self) -> None:
        """Executes Alembic migrations to head in a worker thread."""
        def _apply() -> None:
            from alembic import command
            from alembic.config import Config

            ini_file = Path(self._alembic_ini_path).resolve()
            if not ini_file.exists():
                raise FileNotFoundError(
                    f"Alembic configuration not found at {ini_file}"
                )
            alembic_cfg = Config(str(ini_file))
            alembic_cfg.set_main_option("sqlalchemy.url", self._database_url)
            # Ensure environment variable is synchronized
            os.environ["EXCEL_INTEL_DATABASE_URL"] = self._database_url
            command.upgrade(alembic_cfg, "head")

        await asyncio.to_thread(_apply)

    async def initialize(self) -> None:
        """Establishes Alembic as the single authoritative schema manager and migrates to head."""
        async with self._migration_lock:
            await self._run_alembic_migrations()
            self._initialized = True
            logger.info(
                "DatabaseInitialized",
                message="Database schema migrated to head via Alembic.",
                context={"url": self._database_url},
            )

    async def verify_migration_head(self) -> bool:
        """Checks if the database has alembic_version table with an active version."""
        try:
            async with self._engine.connect() as conn:
                res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
                version = res.scalar()
                return version is not None
        except Exception:
            return False

    async def dispose(self) -> None:
        """Closes all connections and disposes the engine."""
        await self._engine.dispose()
        logger.info("DatabaseDisposed", message="Database engine cleanly disposed.")

    async def ping(self) -> float:
        """Executes SELECT 1 to verify database health and measures latency in milliseconds."""
        start = time.perf_counter()
        async with self._engine.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            val = res.scalar()
            if val != 1:
                raise RuntimeError(f"Unexpected database ping result: {val}")
        return (time.perf_counter() - start) * 1000.0

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Async generator yielding an AsyncSession with automatic transaction management."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
