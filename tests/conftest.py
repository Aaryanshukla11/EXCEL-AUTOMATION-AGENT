"""Shared test fixtures for the Autonomous Excel Intelligence Platform test suite."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest

from excel_intel.config import PlatformConfig


@pytest.fixture
def clean_env() -> Generator[dict[str, str], None, None]:
    """Fixture that isolates tests from ambient environment variables prefixed with EXCEL_INTEL_."""
    old_env = os.environ.copy()
    # Strip any EXCEL_INTEL_ variables
    for key in list(os.environ.keys()):
        if key.startswith("EXCEL_INTEL_"):
            del os.environ[key]

    yield os.environ 

    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def temp_storage(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary storage directory."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.fixture
def default_config(temp_storage: Path) -> PlatformConfig:
    """Fixture providing a default validated PlatformConfig instance."""
    return PlatformConfig(
        env="test",
        log_level="DEBUG",
        log_format="json",
        storage_root=temp_storage,
        max_rss_mb=250,
        token_ttl_seconds=900,
    )
