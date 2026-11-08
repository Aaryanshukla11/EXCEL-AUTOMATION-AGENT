"""Automated tests for CLI entry point, arguments, and command dispatching."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

import pytest

from excel_intel import __version__
from excel_intel.cli import create_parser, main


def test_parser_creation() -> None:
    """Verifies that the root argument parser creates expected subcommands."""
    parser = create_parser()
    assert parser.prog == "excel-intel"

    # Test subcommand parsing
    args = parser.parse_args(["validate-config"])
    assert args.subcommand == "validate-config"

    args = parser.parse_args(["inspect", "sample.xlsx"])
    assert args.subcommand == "inspect"
    assert args.workbook == "sample.xlsx"


def test_cli_help_stdout() -> None:
    """Verifies invoking CLI without args outputs help and exits 0."""
    stdout_buf = io.StringIO()
    with redirect_stdout(stdout_buf):
        exit_code = main([])

    assert exit_code == 0
    assert "usage: excel-intel" in stdout_buf.getvalue()


def test_cli_validate_config_success() -> None:
    """Verifies validate-config subcommand exits with 0 and reports status."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
        exit_code = main(["validate-config"])

    assert exit_code == 0
    output = stdout_buf.getvalue()
    assert f"v{__version__}" in output
    assert "Configuration Status: VALID" in output
    assert "Max RSS Limit:        250 MB" in output


def test_cli_subcommand_dispatch_notice() -> None:
    """Verifies subcommands report foundation readiness without executing unapproved mutations."""
    stdout_buf = io.StringIO()
    with redirect_stdout(stdout_buf):
        exit_code = main(["inspect", "sample.xlsx"])

    assert exit_code == 0
    output = stdout_buf.getvalue()
    assert "Subcommand: inspect" in output
    assert "Notice: Foundation M01 established." in output


def test_cli_invalid_arg_exits_with_code_2() -> None:
    """Verifies invalid CLI flag choices exit with code 2."""
    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        exit_code = main(["--log-level", "INVALID_LEVEL", "validate-config"])

    assert exit_code == 2
    assert "invalid choice" in stderr_buf.getvalue()


def test_cli_invalid_config_exits_with_error_code(clean_env: dict[str, str]) -> None:
    """Verifies invalid configuration environment variables exit with exit code 1."""
    clean_env["EXCEL_INTEL_MAX_RSS_MB"] = "10"  # Below minimum 64 MB
    stderr_buf = io.StringIO()
    with redirect_stderr(stderr_buf):
        exit_code = main(["validate-config"])

    assert exit_code == 1
    assert "Configuration Error" in stderr_buf.getvalue()
