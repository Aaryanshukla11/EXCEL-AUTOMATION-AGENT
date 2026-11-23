"""Tests for SQLite database engine, PRAGMAs, and session lifecycle."""

from __future__ import annotations

from pathlib import Path
import pytest
from sqlalchemy import select, text

from excel_intel.server.database.models import Base, SystemMetadataRecord
from excel_intel.server.database.session import DatabaseManager


@pytest.mark.asyncio
async def test_sqlite_pragmas_enforced(tmp_path: Path) -> None:
    """Verifies WAL, FULL synchronous, foreign keys, and busy timeout PRAGMAs."""
    db_file = tmp_path / "pragma_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url)
    await manager.initialize()

    async with manager.engine.connect() as conn:
        # 1. Foreign keys must be ON (1)
        res_fk = await conn.execute(text("PRAGMA foreign_keys;"))
        assert res_fk.scalar() == 1

        # 2. Busy timeout must be 5000 ms
        res_bt = await conn.execute(text("PRAGMA busy_timeout;"))
        assert res_bt.scalar() == 5000

        # 3. Synchronous mode must be FULL (2)
        res_syn = await conn.execute(text("PRAGMA synchronous;"))
        assert res_syn.scalar() == 2

        # 4. Journal mode must be WAL
        res_jm = await conn.execute(text("PRAGMA journal_mode;"))
        assert str(res_jm.scalar()).lower() == "wal"

    await manager.dispose()


@pytest.mark.asyncio
async def test_database_manager_ping_and_session(tmp_path: Path) -> None:
    """Verifies ping and transactional session management."""
    db_file = tmp_path / "session_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url)
    await manager.initialize()

    # Ping latency
    latency = await manager.ping()
    assert latency >= 0.0

    # Insert record via get_session
    async for session in manager.get_session():
        record = SystemMetadataRecord(key="schema_milestone", value="B1_ACCEPTED")
        session.add(record)

    # Query record back
    async for session in manager.get_session():
        stmt = select(SystemMetadataRecord).where(SystemMetadataRecord.key == "schema_milestone")
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.value == "B1_ACCEPTED"

    await manager.dispose()


@pytest.mark.asyncio
async def test_fresh_database_initialization_via_alembic(tmp_path: Path) -> None:
    """Verifies that fresh DB initialization runs Alembic to head and stamps alembic_version."""
    db_file = tmp_path / "fresh_alembic.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url)
    assert not db_file.exists()

    await manager.initialize()
    assert db_file.exists()

    # Verify alembic_version has the head revision
    is_migrated = await manager.verify_migration_head()
    assert is_migrated is True

    async with manager.engine.connect() as conn:
        res = await conn.execute(text("SELECT version_num FROM alembic_version;"))
        version = res.scalar()
        assert version == "0002_workbook_staging"

    await manager.dispose()


@pytest.mark.asyncio
async def test_repeated_initialization_idempotent(tmp_path: Path) -> None:
    """Verifies that calling initialize() repeatedly is safe and idempotent."""
    db_file = tmp_path / "repeated_init.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url)
    await manager.initialize()
    # Call initialize a second time
    await manager.initialize()

    is_migrated = await manager.verify_migration_head()
    assert is_migrated is True
    await manager.dispose()


@pytest.mark.asyncio
async def test_alembic_upgrade_after_app_initialization(tmp_path: Path) -> None:
    """Verifies that running Alembic upgrade head after application initialization succeeds without duplicate-table error."""
    import asyncio
    from alembic import command
    from alembic.config import Config

    db_file = tmp_path / "app_then_alembic.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url)
    await manager.initialize()
    await manager.dispose()

    # Now run Alembic upgrade as a deployment tool or operator would
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    # Must complete cleanly without OperationalError: table system_metadata already exists
    await asyncio.to_thread(command.upgrade, cfg, "head")


@pytest.mark.asyncio
async def test_verify_migration_head_fails_when_unmigrated(tmp_path: Path) -> None:
    """Verifies verify_migration_head returns False on a blank database before migrations run."""
    db_file = tmp_path / "unmigrated.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url)
    # Do not call initialize()
    is_migrated = await manager.verify_migration_head()
    assert is_migrated is False
    await manager.dispose()


@pytest.mark.asyncio
async def test_migration_failure_on_invalid_ini(tmp_path: Path) -> None:
    """Verifies initialize() raises clear FileNotFoundError when alembic.ini is missing."""
    db_file = tmp_path / "invalid_ini.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    manager = DatabaseManager(database_url=db_url, alembic_ini_path="nonexistent_alembic.ini")
    with pytest.raises(FileNotFoundError) as exc_info:
        await manager.initialize()
    assert "Alembic configuration not found" in str(exc_info.value)
    await manager.dispose()
