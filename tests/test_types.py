"""Automated tests for core architectural data models and contracts."""

from __future__ import annotations

import datetime
import uuid

import pytest
from pydantic import ValidationError

from excel_intel.core.types import (
    ApprovalToken,
    AuditBlock,
    BoundingBox,
    CanonicalOperation,
    CanonicalOpType,
    CellCoordinate,
    ColumnMetadata,
    ColumnType,
    DiscoveryManifest,
    DurabilityGuarantees,
    ExecutionReport,
    ExecutionStatus,
    FileFingerprint,
    FormulaGraphMetadata,
    OperationPlan,
    PlanInvariants,
    TableMetadata,
)


def test_bounding_box_valid_and_invalid() -> None:
    """Verifies BoundingBox boundary constraints."""
    box = BoundingBox(start_row=1, start_col=1, end_row=100, end_col=10)
    assert box.start_row == 1
    assert box.end_row == 100

    # Inverted row bounds
    with pytest.raises(ValidationError):
        BoundingBox(start_row=100, start_col=1, end_row=50, end_col=10)

    # Inverted col bounds
    with pytest.raises(ValidationError):
        BoundingBox(start_row=1, start_col=10, end_row=10, end_col=5)


def test_discovery_manifest_serialization() -> None:
    """Verifies DiscoveryManifest model initialization and serialization."""
    manifest = DiscoveryManifest(
        workbook_path="Master.xlsx",
        sha256="a" * 64,
        file_size_bytes=1024,
        tables=[
            TableMetadata(
                sheet_name="Summary",
                bounding_box=BoundingBox(
                    start_row=1, start_col=1, end_row=50, end_col=5
                ),
                header_row=1,
                columns=[
                    ColumnMetadata(
                        index=1,
                        header_name="ID",
                        inferred_type=ColumnType.INTEGER,
                        type_confidence=1.0,
                    )
                ],
            )
        ],
        formula_graph=FormulaGraphMetadata(node_count=10, edge_count=15),
    )

    data = manifest.model_dump()
    assert data["workbook_path"] == "Master.xlsx"
    assert data["sha256"] == "a" * 64
    assert len(data["tables"]) == 1
    assert data["formula_graph"]["node_count"] == 10


def test_operation_plan_schema_conformance() -> None:
    """Verifies OperationPlan conforms to declarative schema constraints."""
    plan = OperationPlan(
        source_fingerprints=[
            FileFingerprint(path="Source1.xlsx", sha256="b" * 64)
        ],
        target_fingerprint=FileFingerprint(path="Master.xlsx", sha256="c" * 64),
        operations=[
            CanonicalOperation(
                op_id=1,
                op_type=CanonicalOpType.APPEND_ROWS,
                sheet_name="Data",
                target_range="A101:F150",
                payload={"row_count": 50},
            )
        ],
        invariants=PlanInvariants(
            max_rows_affected=50,
            disallow_formula_overwrites=True,
        ),
    )

    data = plan.model_dump()
    assert isinstance(plan.plan_id, uuid.UUID)
    assert len(data["operations"]) == 1
    assert data["operations"][0]["op_type"] == "APPEND_ROWS"
    assert data["invariants"]["max_rows_affected"] == 50


def test_approval_token_validation() -> None:
    """Verifies ApprovalToken creation and constraints."""
    token = ApprovalToken(
        plan_hash="d" * 64,
        signature="e" * 64,
    )

    assert len(token.plan_hash) == 64
    assert len(token.signature) == 64
    assert token.ttl_seconds == 900
    assert isinstance(token.nonce, uuid.UUID)


def test_execution_report_generation() -> None:
    """Verifies ExecutionReport model attributes."""
    now = datetime.datetime.now(datetime.timezone.utc)
    report = ExecutionReport(
        plan_id=uuid.uuid4(),
        status=ExecutionStatus.SUCCESS,
        started_at=now,
        completed_at=now,
        elapsed_ms=45.2,
        pre_state_sha256="1" * 64,
        post_state_sha256="2" * 64,
        rows_inserted=100,
        wal_commit_index=42,
        audit_ledger_entry_id="block_42",
        durability_guarantees=DurabilityGuarantees(
            hardware_flushed=True,
            atomic_replace_confirmed=True,
            storage_type="LOCAL_NTFS",
        ),
    )

    assert report.status == ExecutionStatus.SUCCESS
    assert report.rows_inserted == 100
    assert report.durability_guarantees.hardware_flushed is True
