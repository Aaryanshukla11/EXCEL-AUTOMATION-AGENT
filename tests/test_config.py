"""Automated tests for application configuration and environment handling."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from excel_intel.config import PlatformConfig, load_config
from excel_intel.exceptions import ConfigurationError


def test_default_config_values(clean_env: dict[str, str]) -> None:
    """Verifies default configuration values match architecture baselines."""
    config = load_config()

    assert config.env == "development"  # Default for development installation
    assert config.log_level == "INFO"
    assert config.log_format == "json"
    assert config.max_rss_mb == 250  # V1.2 contractual baseline
    assert config.token_ttl_seconds == 900
    assert config.wal_flush_barrier is True
    assert config.max_decompression_ratio == 10.0


def test_explicit_production_configuration_preserved(clean_env: dict[str, str]) -> None:
    """Verifies explicit production configuration is preserved when intentionally selected."""
    os.environ["EXCEL_INTEL_ENV"] = "production"
    config = load_config()
    assert config.env == "production"


def test_environment_variable_overrides(clean_env: dict[str, str], tmp_path: Path) -> None:
    """Verifies environment variables prefixed with EXCEL_INTEL_ override defaults."""
    os.environ["EXCEL_INTEL_ENV"] = "development"
    os.environ["EXCEL_INTEL_LOG_LEVEL"] = "DEBUG"
    os.environ["EXCEL_INTEL_MAX_RSS_MB"] = "180"
    os.environ["EXCEL_INTEL_TOKEN_TTL_SECONDS"] = "1200"
    os.environ["EXCEL_INTEL_STORAGE_ROOT"] = str(tmp_path)

    config = load_config()

    assert config.env == "development"
    assert config.log_level == "DEBUG"
    assert config.max_rss_mb == 180
    assert config.token_ttl_seconds == 1200
    assert config.storage_root == tmp_path.resolve()


def test_manual_overrides_precedence(clean_env: dict[str, str]) -> None:
    """Verifies manual override dict takes precedence."""
    os.environ["EXCEL_INTEL_LOG_LEVEL"] = "WARNING"

    config = load_config(overrides={"log_level": "ERROR", "env": "test"})

    assert config.log_level == "ERROR"
    assert config.env == "test"


def test_invalid_log_level_raises_configuration_error(clean_env: dict[str, str]) -> None:
    """Verifies invalid enum values trigger ConfigurationError with exit code 1."""
    os.environ["EXCEL_INTEL_LOG_LEVEL"] = "VERBOSE_INVALID"

    with pytest.raises(ConfigurationError) as exc_info:
        load_config()

    assert exc_info.value.exit_code == 1
    assert "Failed to load and validate" in exc_info.value.message


def test_out_of_bounds_max_rss_raises_configuration_error(clean_env: dict[str, str]) -> None:
    """Verifies out-of-bounds memory quotas trigger validation errors."""
    os.environ["EXCEL_INTEL_MAX_RSS_MB"] = "10"  # Below min 64 MB

    with pytest.raises(ConfigurationError) as exc_info:
        load_config()

    assert exc_info.value.exit_code == 1


def test_out_of_bounds_token_ttl_raises_configuration_error(clean_env: dict[str, str]) -> None:
    """Verifies out-of-bounds TTL values trigger validation errors."""
    os.environ["EXCEL_INTEL_TOKEN_TTL_SECONDS"] = "10"  # Below min 60s

    with pytest.raises(ConfigurationError) as exc_info:
        load_config()

    assert exc_info.value.exit_code == 1


def test_config_immutability(default_config: PlatformConfig) -> None:
    """Verifies PlatformConfig is frozen and immutable at runtime."""
    with pytest.raises(Exception):  # ValidationError or TypeError
        default_config.max_rss_mb = 500  # type: ignore
