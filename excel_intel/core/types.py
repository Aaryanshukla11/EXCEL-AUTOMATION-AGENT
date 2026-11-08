"""Frozen architectural data types, schemas, and contract models.

Implements the declarative contracts specified in Section 6.2 and Section 14
of the Release 1.0 System Architecture Design (SAD).
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Literal, Optional
import uuid

from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# Coordinate & Spatial Models
# ==============================================================================

class CellCoordinate(BaseModel):
    """Represents a discrete 1-indexed cell coordinate within a worksheet."""

    row: int = Field(..., ge=1, description="1-indexed row number.")
    col: int = Field(..., ge=1, description="1-indexed column number.")

    model_config = {"frozen": True}


class BoundingBox(BaseModel):
    """Represents a rectangular tabular boundary within a worksheet."""

    start_row: int = Field(..., ge=1)
    start_col: int = Field(..., ge=1)
    end_row: int = Field(..., ge=1)
    end_col: int = Field(..., ge=1)

    @field_validator("end_row")
    @classmethod
    def check_row_bounds(cls, v: int, info: Any) -> int:
        if "start_row" in info.data and v < info.data["start_row"]:
            raise ValueError("end_row must be greater than or equal to start_row")
        return v

    @field_validator("end_col")
    @classmethod
    def check_col_bounds(cls, v: int, info: Any) -> int:
        if "start_col" in info.data and v < info.data["start_col"]:
            raise ValueError("end_col must be greater than or equal to start_col")
        return v

    model_config = {"frozen": True}


# ==============================================================================
# Discovery & Schema Manifest (§14.1 A)
# ==============================================================================

class ColumnType(str, Enum):
    """Statistical semantic data types discovered across column cells."""

    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    STRING = "STRING"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"
    FORMULA = "FORMULA"


class ColumnMetadata(BaseModel):
    """Metadata describing a single column within a detected tabular region."""

    index: int = Field(..., ge=1)
    header_name: str
    inferred_type: ColumnType
    type_confidence: float = Field(..., ge=0.0, le=1.0)
    nullable: bool = True
    formula_pattern: Optional[str] = None

    model_config = {"frozen": True}


class TableMetadata(BaseModel):
    """Metadata describing a detected table or contiguous tabular grid."""

    sheet_name: str
    bounding_box: BoundingBox
    header_row: int = Field(..., ge=1)
    columns: list[ColumnMetadata]
    is_list_object: bool = False
    list_object_name: Optional[str] = None

    model_config = {"frozen": True}


class FormulaGraphMetadata(BaseModel):
    """Summary of static formula dependency analysis across the workbook."""

    node_count: int = Field(default=0, ge=0)
    edge_count: int = Field(default=0, ge=0)
    has_cycles: bool = False
    volatile_cells: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class DiscoveryManifest(BaseModel):
    """Complete structural discovery manifest emitted by the Deterministic Core."""

    manifest_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    workbook_path: str
    sha256: str = Field(..., min_length=64, max_length=64)
    file_size_bytes: int = Field(..., ge=0)
    tables: list[TableMetadata]
    formula_graph: FormulaGraphMetadata

    model_config = {"frozen": True}


# ==============================================================================
# Declarative Canonical Operations & Operation-Plan (§6.1, §6.2)
# ==============================================================================

class CanonicalOpType(str, Enum):
    """The 5 authorized declarative mutation operations (ADR-002, ADR-006)."""

    APPEND_ROWS = "APPEND_ROWS"
    INSERT_ROW = "INSERT_ROW"
    UPDATE_CELL = "UPDATE_CELL"
    EXTEND_TABLE = "EXTEND_TABLE"
    PROPAGATE_FORMULA = "PROPAGATE_FORMULA"


class SourceLineage(BaseModel):
    """Auditable provenance pointing back to the source records."""

    source_workbook: str
    source_sheet: str
    source_row_indices: list[int]

    model_config = {"frozen": True}


class CanonicalOperation(BaseModel):
    """A discrete, declarative spreadsheet mutation step."""

    op_id: int = Field(..., ge=1)
    op_type: CanonicalOpType
    sheet_name: str
    target_range: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source_lineage: Optional[SourceLineage] = None

    model_config = {"frozen": True}


class PlanInvariants(BaseModel):
    """Pre-conditions and boundary constraints enforced during shadow validation."""

    max_rows_affected: int = Field(..., ge=0)
    disallow_formula_overwrites: bool = True
    required_schema_checksum: Optional[str] = None

    model_config = {"frozen": True}


class FileFingerprint(BaseModel):
    """Cryptographic hash binding an operation plan to exact physical files."""

    path: str
    sha256: str = Field(..., min_length=64, max_length=64)

    model_config = {"frozen": True}


class OperationPlan(BaseModel):
    """Declarative JSON contract emitted by Cognitive Orchestrator (Schema 2020-12)."""

    plan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source_fingerprints: list[FileFingerprint]
    target_fingerprint: FileFingerprint
    operations: list[CanonicalOperation]
    invariants: PlanInvariants

    model_config = {"frozen": True}


# ==============================================================================
# Security & Token Governance (§8.1)
# ==============================================================================

class ApprovalToken(BaseModel):
    """HMAC-SHA256 symmetric MAC token verifying human operator sign-off."""

    plan_hash: str = Field(..., min_length=64, max_length=64)
    nonce: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    ttl_seconds: int = Field(default=900, ge=60)
    signature: str = Field(..., min_length=64, max_length=64)

    model_config = {"frozen": True}


# ==============================================================================
# Execution & Durability Reports (§14.1 B)
# ==============================================================================

class ExecutionStatus(str, Enum):
    """Terminal state of a transaction execution order."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class DurabilityGuarantees(BaseModel):
    """Receipt proving physical synchronization barriers were committed."""

    hardware_flushed: bool
    atomic_replace_confirmed: bool
    storage_type: Literal[
        "LOCAL_NTFS", "LOCAL_POSIX", "SMB_NETWORK", "CLOUD_SYNC_ROOT"
    ]

    model_config = {"frozen": True}


class ExecutionReport(BaseModel):
    """Final auditable execution receipt returned by the Deterministic Execution Layer."""

    execution_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    plan_id: uuid.UUID
    status: ExecutionStatus
    started_at: datetime.datetime
    completed_at: datetime.datetime
    elapsed_ms: float
    pre_state_sha256: str = Field(..., min_length=64, max_length=64)
    post_state_sha256: str = Field(..., min_length=64, max_length=64)
    rows_inserted: int = Field(default=0, ge=0)
    rows_updated: int = Field(default=0, ge=0)
    cells_modified: int = Field(default=0, ge=0)
    wal_commit_index: int = Field(default=0, ge=0)
    audit_ledger_entry_id: str
    durability_guarantees: DurabilityGuarantees

    model_config = {"frozen": True}


# ==============================================================================
# Cryptographic Audit Ledger (§9.1)
# ==============================================================================

class AuditBlock(BaseModel):
    """An immutable block in the append-only SHA-256 provenance chain."""

    block_index: int = Field(..., ge=0)
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    operator_id: str
    pre_state_hash: str = Field(..., min_length=64, max_length=64)
    post_state_hash: str = Field(..., min_length=64, max_length=64)
    plan_hash: str = Field(..., min_length=64, max_length=64)
    previous_block_hash: str = Field(..., min_length=64, max_length=64)
    current_block_hash: str = Field(..., min_length=64, max_length=64)

    model_config = {"frozen": True}
