"""Platform error taxonomy and standardized exit codes.

Aligns with Section 13.2 of the Release 1.0 System Architecture Design (SAD).
Every platform exception provides a deterministic exit code, error category,
and structured diagnostic context.
"""

from typing import Any, Optional


class PlatformError(Exception):
    """Base exception for all Autonomous Excel Intelligence Platform errors."""

    exit_code: int = 1
    category: str = "ERR_GENERIC"

    def __init__(
        self,
        message: str,
        *,
        context: Optional[dict[str, Any]] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context or {}
        if exit_code is not None:
            self.exit_code = exit_code

    def to_dict(self) -> dict[str, Any]:
        """Serialize error details for diagnostic reporting and structured logs."""
        return {
            "error_category": self.category,
            "exit_code": self.exit_code,
            "message": self.message,
            "context": self.context,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, exit_code={self.exit_code}, context={self.context!r})"


# ==============================================================================
# Configuration & Environment Errors (Exit codes 1 - 9)
# ==============================================================================

class ConfigurationError(PlatformError):
    """Raised when runtime configuration or environment settings are invalid."""

    exit_code: int = 1
    category: str = "ERR_CONFIG_INVALID"


class PlatformIOError(PlatformError):
    """Raised when an unrecoverable input/output error occurs."""

    exit_code: int = 2
    category: str = "ERR_IO_FAILURE"


class UnsupportedFormatError(PlatformError):
    """Raised when a workbook format or feature is not supported in the active profile."""

    exit_code: int = 3
    category: str = "ERR_UNSUPPORTED_FORMAT"


# ==============================================================================
# Schema & Semantic Errors (Exit codes 10 - 19)
# ==============================================================================

class SchemaViolationError(PlatformError):
    """Raised when workbook content violates declared structural constraints."""

    exit_code: int = 10
    category: str = "ERR_SCHEMA_VIOLATION"


class FormulaCycleError(PlatformError):
    """Raised when the static formula dependency DAG contains a circular reference."""

    exit_code: int = 11
    category: str = "ERR_FORMULA_CYCLE"


class VolatileMutationError(PlatformError):
    """Raised when an operation attempts to mutate or invalidate a volatile function cell."""

    exit_code: int = 12
    category: str = "ERR_VOLATILE_MUTATION"


class KeyCollisionError(PlatformError):
    """Raised when an operation triggers an unresolved primary/unique key collision."""

    exit_code: int = 13
    category: str = "ERR_KEY_COLLISION"


class PlatformResourceLimitError(PlatformError):
    """Raised when an operation exceeds memory, file size, or resource quotas."""

    exit_code: int = 14
    category: str = "ERR_RESOURCE_EXHAUSTED"


class CorruptWorkbookError(PlatformError):
    """Raised when a workbook structure or binary package is corrupted."""

    exit_code: int = 15
    category: str = "ERR_CORRUPT_WORKBOOK"


# ==============================================================================
# Security & Token Governance Errors (Exit codes 20 - 29)
# ==============================================================================

class TokenExpiredError(PlatformError):
    """Raised when an HMAC approval token's timestamp exceeds the allowed TTL."""

    exit_code: int = 20
    category: str = "ERR_TOKEN_EXPIRED"


class TokenReplayError(PlatformError):
    """Raised when an approval token nonce has already been consumed in the vault."""

    exit_code: int = 21
    category: str = "ERR_TOKEN_REPLAY"


class TokenVerificationError(PlatformError):
    """Raised when an HMAC approval token signature is invalid or forged."""

    exit_code: int = 22
    category: str = "ERR_TOKEN_VERIFICATION_FAILED"


# ==============================================================================
# Durability, Storage & Audit Errors (Exit codes 30 - 49)
# ==============================================================================

class DurabilityFaultError(PlatformError):
    """Raised when a physical hardware flush barrier or atomic replacement fails."""

    exit_code: int = 30
    category: str = "ERR_DURABILITY_FAULT"


class AuditFailureError(PlatformError):
    """Raised when cryptographic audit block appending or hash-chain verification fails."""

    exit_code: int = 40
    category: str = "ERR_AUDIT_FAILURE"


class InvariantViolationError(PlatformError):
    """Raised when an operation breaches a core architectural invariant (e.g. zero creation)."""

    exit_code: int = 50
    category: str = "ERR_INVARIANT_VIOLATION"


__all__ = [
    "PlatformError",
    "ConfigurationError",
    "PlatformIOError",
    "UnsupportedFormatError",
    "SchemaViolationError",
    "FormulaCycleError",
    "VolatileMutationError",
    "KeyCollisionError",
    "PlatformResourceLimitError",
    "CorruptWorkbookError",
    "TokenExpiredError",
    "TokenReplayError",
    "TokenVerificationError",
    "DurabilityFaultError",
    "AuditFailureError",
    "InvariantViolationError",
]
