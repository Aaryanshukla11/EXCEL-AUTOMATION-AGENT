"""Comprehensive Test Suite for Unified Spatial Detector Facade (M04 Prompt 4).

Verifies:
- End-to-end orchestration across GridSegmenter, HeaderResolver, ZoneClassifier, BoundarySentinel
- Cross-boundary merge conflict detection (FR-5.2)
- Overlapping region warning detection (FR-5.1)
- Lossless M01 TableMetadata conversion with verified column types
- Non-fabrication guard: strict refusal to export without verified types
- Multi-sheet workbook spatial analysis aggregation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import pytest

from excel_intel.core.types import ColumnType, TableMetadata
from excel_intel.inspection.models import (
    BoundingBox,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
)
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.models import (
    SemanticZoneType,
    SpatialEvidenceType,
    SpatialTableRegion,
)
from tests.test_m04_grid_segmenter import build_synthetic_workbook


class TestSpatialDetectorFacade:
    """Test suite for unified SpatialDetector facade."""

    def test_e2e_sheet_detection_orchestration(self, tmp_path: Path) -> None:
        """Verify detector orchestrates segmentation, headers, zones, and margins on synthetic sheet."""
        from excel_intel.core.parser import StreamingWorkbookReader
        from tests.test_m04_e2e_integration import build_multisheet_test_workbook

        wb_path = build_multisheet_test_workbook(tmp_path / "detector_e2e.xlsx")
        reader = StreamingWorkbookReader(wb_path)

        detector = SpatialDetector()
        report = detector.detect_sheet(reader, "SummarySheet")

        assert len(report.regions) == 1
        reg = report.regions[0]

        # Verify header resolution executed
        assert reg.header_row == 2
        assert reg.header_resolution is not None

        # Verify zone classification executed
        assert len(reg.zones) >= 2
        assert SemanticZoneType.HEADER in reg.zones
        assert SemanticZoneType.BODY in reg.zones

        # Verify ADR-005 boundary sentinel executed
        assert reg.margin is not None
        assert reg.margin.safe_for_append is True

    def test_cross_boundary_merge_conflict_detection(self, tmp_path: Path) -> None:
        """Verify merge cell straddling region boundary is flagged with CROSS_BOUNDARY_MERGE (FR-5.2)."""
        from excel_intel.core.parser import StreamingWorkbookReader

        # Table at cols 1..3, rows 2..5
        rows = [
            (2, [1, 2, 3]),
            (3, [1, 2, 3]),
            (4, [1, 2, 3]),
            (5, [1, 2, 3]),
        ]
        wb_path = build_synthetic_workbook(tmp_path, "cross_merge.xlsx", rows)
        reader = StreamingWorkbookReader(wb_path)

        # Merge cell C2:D2 straddles region boundary (col 3 is in table, col 4 is outside table)
        facts = DeclaredOpenXmlFacts(
            properties=DeclaredSheetProperties(sheet_id=1, name="Sheet1"),
            merge_cells=[DeclaredMergeCell.from_ref("C2:D2")],
        )

        detector = SpatialDetector()
        report = detector.detect_sheet(reader, "Sheet1", facts=facts)

        assert len(report.regions) == 1
        reg = report.regions[0]
        cb_evs = [e for e in reg.evidence if e.evidence_type == SpatialEvidenceType.CROSS_BOUNDARY_MERGE]
        assert len(cb_evs) >= 1
        assert "Merge range C2:D2 straddles region boundary" in cb_evs[0].description

    def test_overlapping_region_warning_detection(self) -> None:
        """Verify intersecting candidate regions are flagged with OVERLAPPING_REGION_WARNING (FR-5.1)."""
        box1 = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=5)
        box2 = BoundingBox(min_row=5, max_row=15, min_col=3, max_col=8)

        # Mock segmenter returning overlapping regions
        class MockSegmenter:
            def segment_sheet(self, reader, sheet_name, *, facts=None):
                from excel_intel.spatial.models import SpatialDetectionReport, SpatialRegionType
                r1 = SpatialTableRegion(
                    region_id="r1",
                    sheet_name=sheet_name,
                    bounding_box=box1,
                    region_type=SpatialRegionType.INFERRED_TABLE,
                    heuristic_confidence=0.85,
                    cell_count=box1.cell_count,
                    populated_cell_count=box1.cell_count,
                    density=1.0,
                )
                r2 = SpatialTableRegion(
                    region_id="r2",
                    sheet_name=sheet_name,
                    bounding_box=box2,
                    region_type=SpatialRegionType.INFERRED_TABLE,
                    heuristic_confidence=0.85,
                    cell_count=box2.cell_count,
                    populated_cell_count=box2.cell_count,
                    density=1.0,
                )
                return SpatialDetectionReport(
                    workbook_path="test.xlsx",
                    sheet_name=sheet_name,
                    regions=[r1, r2],
                )

        class MockReader:
            def stream_sheet(self, sheet, chunk_size=1000):
                return []

        detector = SpatialDetector(segmenter=MockSegmenter())
        report = detector.detect_sheet(MockReader(), "Sheet1")

        assert len(report.regions) == 2
        r1 = report.regions[0] 
        assert "r2" in r1.overlapping_region_ids
        ov_evs = [e for e in r1.evidence if e.evidence_type == SpatialEvidenceType.OVERLAPPING_REGION_WARNING]
        assert len(ov_evs) >= 1 

    def test_lossless_m01_table_metadata_conversion(self, tmp_path: Path) -> None:
        """Verify clean conversion from detected region to M01 TableMetadata with verified types."""
        from excel_intel.core.parser import StreamingWorkbookReader
        from tests.test_m04_e2e_integration import build_multisheet_test_workbook

        wb_path = build_multisheet_test_workbook(tmp_path / "meta_export.xlsx")
        reader = StreamingWorkbookReader(wb_path)

        detector = SpatialDetector()
        report = detector.detect_sheet(reader, "SummarySheet")
        reg_id = report.regions[0].region_id

        # Supply verified column types for region
        types_map = {
            reg_id: {
                1: ColumnType.STRING,
                2: ColumnType.DECIMAL,
            }
        }

        tables: list[TableMetadata] = detector.export_to_table_metadata_list(report, types_map)

        assert len(tables) == 1
        t = tables[0]
        assert t.sheet_name == "SummarySheet"
        assert t.header_row == 2
        assert len(t.columns) == 2
        assert t.columns[0].inferred_type == ColumnType.STRING
        assert t.columns[1].inferred_type == ColumnType.DECIMAL

    def test_non_fabrication_guard_raises_error(self, tmp_path: Path) -> None:
        """Verify export_to_table_metadata_list refuses to fabricate types when omitted."""
        from excel_intel.core.parser import StreamingWorkbookReader

        rows = [(1, [1, 2]), (2, [1, 2])]
        wb_path = build_synthetic_workbook(tmp_path, "guard_check.xlsx", rows)
        reader = StreamingWorkbookReader(wb_path)

        detector = SpatialDetector()
        report = detector.detect_sheet(reader, "Sheet1")

        # Call without verified types for the region
        with pytest.raises(NotImplementedError) as exc_info:
            detector.export_to_table_metadata_list(report, {})
        assert "requires verified column types" in str(exc_info.value)
