"""Abstract interfaces for the Deterministic Execution & Durability Tier.

Specifies protocols for in-memory shadow validation, Write-Ahead Logging (WAL),
HMAC symmetric approval token verification, and immutable audit logging.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable
import uuid

from excel_intel.core.types import (
    ApprovalToken,
    AuditBlock,
    ExecutionReport,
    OperationPlan,
)


@runtime_checkable
class ShadowEngineProtocol(Protocol):
    """Protocol for in-memory dry-run execution and invariant verification."""

    def validate_plan(
        self,
        *,
        target_path: Path,
        plan: OperationPlan,
    ) -> bool:
        """Execute in-memory dry run against virtual grid to verify invariants.

        Raises:
            InvariantViolationError: If zero-creation or formula invariants are violated.
            KeyCollisionError: If primary/unique candidate key collisions occur.
            FormulaCycleError: If circular formula references are introduced.
        """
        ...


@runtime_checkable
class HMACAuthorityProtocol(Protocol):
    """Protocol for generating and validating symmetric approval tokens."""

    def issue_token(
        self,
        *,
        plan_hash: str,
        ttl_seconds: int = 900,
    ) -> ApprovalToken:
        """Generate an HMAC-SHA256 approval token with an ephemeral session key."""
        ...

    def verify_and_consume_nonce(
        self,
        *,
        token: ApprovalToken,
    ) -> bool:
        """Atomically verify token signature and consume nonce in SQLite vault.

        Raises:
            TokenExpiredError: If token timestamp exceeds TTL.
            TokenReplayError: If nonce was previously consumed.
            TokenVerificationError: If HMAC signature is invalid.
        """
        ...


@runtime_checkable
class TransactionManagerProtocol(Protocol):
    """Protocol for the 6-phase Write-Ahead Logging physical durability engine."""

    def execute_transaction(
        self,
        *,
        target_path: Path,
        plan: OperationPlan,
        token: ApprovalToken,
    ) -> ExecutionReport:
        """Execute atomic 6-phase WAL write sequence with hardware sync barriers.

        Raises:
            DurabilityFaultError: If OS flush barrier or atomic replacement fails.
        """
        ...

    def startup_recovery(self) -> list[uuid.UUID]:
        """Scan WAL and resolve interrupted transactions idempotently."""
        ...


@runtime_checkable
class AuditLedgerProtocol(Protocol):
    """Protocol for append-only SHA-256 cryptographic provenance logging."""

    def record_block(
        self,
        *,
        report: ExecutionReport,
        operator_id: str,
    ) -> AuditBlock:
        """Append an immutable audit block to the cryptographic hash chain."""
        ...

    def verify_chain_integrity(self) -> bool:
        """Verify 100% cryptographic integrity of the historical block chain."""
        ...
