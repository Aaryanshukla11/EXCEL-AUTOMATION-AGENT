"""Automated tests for platform error taxonomy and exit codes."""

from __future__ import annotations

import pytest

from excel_intel.exceptions import (
    AuditFailureError,
    ConfigurationError,
    DurabilityFaultError,
    FormulaCycleError,
    InvariantViolationError,
    KeyCollisionError,
    PlatformError,
    PlatformIOError,
    SchemaViolationError,
    TokenExpiredError,
    TokenReplayError,
    TokenVerificationError,
    UnsupportedFormatError,
    VolatileMutationError,
)


def test_exception_exit_codes_match_architecture() -> None:
    """Verifies all exceptions match Section 13.2 exit codes and categories."""
    assert ConfigurationError.exit_code == 1
    assert ConfigurationError.category == "ERR_CONFIG_INVALID"

    assert PlatformIOError.exit_code == 2
    assert PlatformIOError.category == "ERR_IO_FAILURE"

    assert UnsupportedFormatError.exit_code == 3
    assert UnsupportedFormatError.category == "ERR_UNSUPPORTED_FORMAT"

    assert SchemaViolationError.exit_code == 10
    assert SchemaViolationError.category == "ERR_SCHEMA_VIOLATION"

    assert FormulaCycleError.exit_code == 11
    assert FormulaCycleError.category == "ERR_FORMULA_CYCLE"

    assert VolatileMutationError.exit_code == 12
    assert VolatileMutationError.category == "ERR_VOLATILE_MUTATION"

    assert KeyCollisionError.exit_code == 13
    assert KeyCollisionError.category == "ERR_KEY_COLLISION"

    assert TokenExpiredError.exit_code == 20
    assert TokenExpiredError.category == "ERR_TOKEN_EXPIRED"

    assert TokenReplayError.exit_code == 21
    assert TokenReplayError.category == "ERR_TOKEN_REPLAY"

    assert TokenVerificationError.exit_code == 22
    assert TokenVerificationError.category == "ERR_TOKEN_VERIFICATION_FAILED"

    assert DurabilityFaultError.exit_code == 30
    assert DurabilityFaultError.category == "ERR_DURABILITY_FAULT"

    assert AuditFailureError.exit_code == 40
    assert AuditFailureError.category == "ERR_AUDIT_FAILURE"

    assert InvariantViolationError.exit_code == 50
    assert InvariantViolationError.category == "ERR_INVARIANT_VIOLATION"


def test_exception_serialization() -> None:
    """Verifies error dictionary serialization includes diagnostic context."""
    err = FormulaCycleError(
        "Circular reference detected in formula graph.",
        context={"cycle_path": ["A1", "B2", "A1"]},
    )

    data = err.to_dict()
    assert data["error_category"] == "ERR_FORMULA_CYCLE"
    assert data["exit_code"] == 11
    assert data["message"] == "Circular reference detected in formula graph."
    assert data["context"]["cycle_path"] == ["A1", "B2", "A1"]


def test_custom_exit_code_override() -> None:
    """Verifies exit code can be overridden dynamically."""
    err = PlatformError("Generic failure", exit_code=99)
    assert err.exit_code == 99
