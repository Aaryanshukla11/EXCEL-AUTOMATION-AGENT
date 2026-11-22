"""Integration tests for M05 Canonical DiscoveryManifest Synthesis Facade (FR-6).

Validates end-to-end integration across M04 spatial detection, M05 semantic type inference,
and M05 formula dependency analysis, producing the canonical M01 DiscoveryManifest.
"""

import uuid
import pytest

from excel_intel.core.types import ColumnType, DiscoveryManifest
from excel_intel.formulas.graph import CycleStatus, FormulaGraphReport
from excel_intel.adapters.manifest_adapter import build_discovery_manifest
from excel_intel.spatial.models import (
    BoundingBox as SpatialBoundingBox,
    HeaderResolutionReport,
    HeaderResolutionStatus,
    ResolvedHeaderColumn,
    SpatialDetectionReport,
    SpatialRegionType,
    SpatialTableRegion,
)
from excel_intel.types.models import (
    ColumnTypeProfile,
    InferenceState,
    RegionTypeReport,
    SamplingDiagnostics,
    ValueCategory,
)


def _build_test_fixtures() -> tuple[SpatialDetectionReport, dict[str, RegionTypeReport], FormulaGraphReport]:
    """Construct valid test fixtures across M04 and M05 Prompt 2 & Prompt 4."""
    region_id = "table_sheet1_r1_c1"
    resolved_cols = [
        ResolvedHeaderColumn(
            col_index=1,
            resolved_name="ID",
            raw_name="ID",
            source_coordinate="Sheet1!A1",
            region_id=region_id,
            sheet_name="Sheet1",
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
        ),
        ResolvedHeaderColumn(
            col_index=2,
            resolved_name="Amount",
            raw_name="Amount",
            source_coordinate="Sheet1!B1",
            region_id=region_id,
            sheet_name="Sheet1",
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
        ),
    ]

    header_resolution = HeaderResolutionReport(
        region_id=region_id,
        sheet_name="Sheet1",
        status=HeaderResolutionStatus.HIGH_CONFIDENCE,
        header_row_start=1,
        header_row_end=1,
        header_row_count=1,
        columns=resolved_cols,
        heuristic_confidence=1.0,
    )

    box = SpatialBoundingBox(min_row=1, max_row=10, min_col=1, max_col=2)
    region = SpatialTableRegion(
        region_id=region_id,
        sheet_name="Sheet1",
        header_row=1,
        bounding_box=box,
        region_type=SpatialRegionType.INFERRED_TABLE,
        heuristic_confidence=0.95,
        cell_count=20,
        populated_cell_count=20,
        density=1.0,
        header_resolution=header_resolution,
    )

    detection_report = SpatialDetectionReport(
        workbook_path="test_book.xlsx",
        sheet_name="Sheet1",
        regions=[region],
    )

    # RegionTypeReport from M05 Prompt 2
    sampling_diag = SamplingDiagnostics(
        total_rows=9,
        total_cols=2,
        sampled_rows=9,
        sampled_cols=2,
        sampled_cells=18,
    )
    type_report = RegionTypeReport(
        region_id=region_id,
        sheet_name="Sheet1",
        body_row_start=2,
        body_row_end=10,
        body_col_start=1,
        body_col_end=2,
        sampling=sampling_diag,
        columns={
            1: ColumnTypeProfile(
                col_index=1,
                state=InferenceState.INFERRED,
                candidate_type=ColumnType.INTEGER,
                inferred_type=ColumnType.INTEGER,
                heuristic_support_score=1.0,
                total_cells=9,
                effective_cells=9,
                populated_cells=9,
                null_cells=0,
                nullability_ratio=0.0,
            ),
            2: ColumnTypeProfile(
                col_index=2,
                state=InferenceState.INFERRED,
                candidate_type=ColumnType.DECIMAL,
                inferred_type=ColumnType.DECIMAL,
                heuristic_support_score=0.95,
                total_cells=9,
                effective_cells=9,
                populated_cells=9,
                null_cells=0,
                nullability_ratio=0.0,
            ),
        },
    )

    # FormulaGraphReport from M05 Prompt 4
    graph_report = FormulaGraphReport(
        node_count=10,
        edge_count=12,
        has_cycles=False,
        cycle_status=CycleStatus.NO_CYCLES,
        is_complete=True,
        volatile_cells=["Sheet1!C1"],
    )

    return detection_report, {region_id: type_report}, graph_report


def test_build_discovery_manifest_success() -> None:
    """Test successful DiscoveryManifest assembly combining M04, M05-P2, and M05-P4."""
    detection_report, type_reports, graph_report = _build_test_fixtures()
    sha256 = "e" * 64
    manifest_id = uuid.uuid4()

    manifest = build_discovery_manifest(
        workbook_path="C:/data/test_book.xlsx",
        sha256=sha256,
        file_size_bytes=4096,
        detection_report=detection_report,
        region_type_reports=type_reports,
        formula_graph_report=graph_report,
        manifest_id=manifest_id,
    )

    assert isinstance(manifest, DiscoveryManifest)
    assert manifest.manifest_id == manifest_id
    assert manifest.workbook_path == "C:/data/test_book.xlsx"
    assert manifest.sha256 == sha256
    assert manifest.file_size_bytes == 4096

    # Verify TableMetadata conversion
    assert len(manifest.tables) == 1
    table = manifest.tables[0]
    assert table.sheet_name == "Sheet1"
    assert len(table.columns) == 2
    assert table.columns[0].header_name == "ID"
    assert table.columns[0].inferred_type == ColumnType.INTEGER
    assert table.columns[1].header_name == "Amount"
    assert table.columns[1].inferred_type == ColumnType.DECIMAL

    # Verify FormulaGraphMetadata
    assert manifest.formula_graph.node_count == 10
    assert manifest.formula_graph.edge_count == 12
    assert manifest.formula_graph.has_cycles is False
    assert manifest.formula_graph.volatile_cells == ["Sheet1!C1"]


def test_build_discovery_manifest_invalid_sha256() -> None:
    """Test validation failure on invalid SHA-256 length."""
    detection_report, type_reports, graph_report = _build_test_fixtures()
    with pytest.raises(ValueError, match="sha256 must be exactly 64 hexadecimal characters"):
        build_discovery_manifest(
            workbook_path="test.xlsx",
            sha256="short_hash",
            file_size_bytes=100,
            detection_report=detection_report,
            region_type_reports=type_reports,
            formula_graph_report=graph_report,
        )


def test_build_discovery_manifest_missing_types_error() -> None:
    """Test error when verified types are missing for a detected region."""
    detection_report, _, graph_report = _build_test_fixtures()
    sha256 = "a" * 64

    with pytest.raises(NotImplementedError, match="requires verified column types"):
        build_discovery_manifest(
            workbook_path="test.xlsx",
            sha256=sha256,
            file_size_bytes=100,
            detection_report=detection_report,
            region_type_reports={},  # Missing region!
            formula_graph_report=graph_report,
        )
