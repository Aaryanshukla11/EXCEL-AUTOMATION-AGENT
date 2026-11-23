"""Tests for Alembic migration infrastructure."""

from __future__ import annotations

import os
from pathlib import Path
from alembic import command
from alembic.config import Config
import pytest


def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Verifies that Alembic can apply all migrations to a clean SQLite database and roll back cleanly."""
    db_file = tmp_path / "alembic_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    ini_path = Path("alembic.ini").resolve()
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Set environment variable so env.py picks up the correct URL
    old_env = os.environ.get("EXCEL_INTEL_DATABASE_URL")
    os.environ["EXCEL_INTEL_DATABASE_URL"] = db_url

    try:
        # Upgrade to head
        command.upgrade(alembic_cfg, "head")
        assert db_file.exists()

        # Downgrade to base
        command.downgrade(alembic_cfg, "base")
    finally:
        if old_env is not None:
            os.environ["EXCEL_INTEL_DATABASE_URL"] = old_env
        else:
            os.environ.pop("EXCEL_INTEL_DATABASE_URL", None)
