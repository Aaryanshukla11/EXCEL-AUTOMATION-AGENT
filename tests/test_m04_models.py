"""Unit tests for M04 Spatial Data Models (models.py).

Verifies:
1. Strict field validation and immutability (frozen=True).
2. 1-indexed coordinate enforcement and bounding-box validation.
3. Heuristic confidence scores bounded in [0.0, 1.0].
4. Declared vs. inferred evidence semantics.
5. Nested and overlapping region relationships.
6. JSON serialization and deserialization roundtrip.
7. M01 TableMetadata compatibility and intentional unsupported bridge error when unresolved.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from excel_intel.core.types import ColumnMetadata, ColumnType, TableMetadata
from excel_intel.inspection.models import BoundingBox
from excel_intel.spatial.models import (
    CorridorOrientation,
    SeparationCorridor,
    SpatialDetectionReport,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialRegionType,
    SpatialTableRegion,
)


class TestSpatialModels:
    def test_bounding_box_and_region_validation(self) -> None:
        """Verify 1-indexed coordinates and positive bounding box dimensions."""
        box = BoundingBox(min_row=5, max_row=20, min_col=2, max_col=10)
        assert box.min_row == 5
        assert box.max_row == 20
        assert box.min_col == 2
        assert box.max_col == 10
        assert box.row_count == 16
        assert box.col_count == 9
        assert box.cell_count == 144

        # Invalid bounds
        with pytest.raises(ValidationError):
            BoundingBox(min_row=10, max_row=5, min_col=1, max_col=5)

        with pytest.raises(ValidationError):
            BoundingBox(min_row=1, max_row=5, min_col=8, max_col=2)

        # 0-indexed rejection (le/ge constraints)
        with pytest.raises(ValidationError):
            BoundingBox(min_row=0, max_row=5, min_col=1, max_col=5)

    def test_spatial_table_region_immutability(self) -> None:
        """Verify frozen Pydantic configuration prevents mutation."""
        box = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=5)
        region = SpatialTableRegion(
            region_id="spat_sheet1_r1_10_c1_5",
            sheet_name="Sheet1",
            bounding_box=box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=0.85,
            cell_count=50,
            populated_cell_count=45,
            density=0.90,
        )

        with pytest.raises(ValidationError):
            region.sheet_name = "Mutated"

        with pytest.raises(ValidationError):
            region.density = 0.50

    def test_confidence_bounds_enforcement(self) -> None:
        """Verify confidence is strictly clamped in [0.0, 1.0]."""
        box = BoundingBox(min_row=1, max_row=5, min_col=1, max_col=5)

        with pytest.raises(ValidationError):
            SpatialTableRegion(
                region_id="r1",
                sheet_name="S1",
                bounding_box=box,
                region_type=SpatialRegionType.INFERRED_TABLE,
                heuristic_confidence=1.05,  # > 1.0
                cell_count=25,
                populated_cell_count=20,
                density=0.80,
            )

        with pytest.raises(ValidationError):
            SpatialTableRegion(
                region_id="r1",
                sheet_name="S1",
                bounding_box=box,
                region_type=SpatialRegionType.INFERRED_TABLE,
                heuristic_confidence=-0.1,  # < 0.0
                cell_count=25,
                populated_cell_count=20,
                density=0.80,
            )

    def test_json_roundtrip_preservation(self) -> None:
        """Verify lossless serialization and deserialization."""
        box = BoundingBox(min_row=2, max_row=15, min_col=3, max_col=8)
        ev = SpatialEvidence(
            evidence_type=SpatialEvidenceType.VERTICAL_CORRIDOR_ISOLATION,
            description="Isolated horizontally by 2 blank columns",
            heuristic_score=0.95,
            provenance="M04:GridSegmenter:unit_test",
            coordinates=box,
        )
        corridor = SeparationCorridor(
            orientation=CorridorOrientation.VERTICAL,
            start_index=9,
            end_index=10,
            width=2,
            span_min=2,
            span_max=15,
        )
        region = SpatialTableRegion(
            region_id="spat_SheetA_r2_15_c3_8",
            sheet_name="SheetA",
            bounding_box=box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            is_declared=False,
            heuristic_confidence=0.88,
            evidence=[ev],
            cell_count=84,
            populated_cell_count=70,
            density=0.8333,
        )

        report = SpatialDetectionReport(
            workbook_path="test_wb.xlsx",
            sheet_name="SheetA",
            regions=[region],
            sparse_islands=[],
            corridors_detected=[corridor],
            lookahead_window_size=50,
            total_populated_cells_evaluated=70,
        )

        json_str = report.model_dump_json()
        restored = SpatialDetectionReport.model_validate_json(json_str)

        assert restored == report
        assert restored.regions[0].region_id == region.region_id
        assert restored.regions[0].bounding_box == box
        assert restored.corridors_detected[0] == corridor

    def test_declared_vs_inferred_semantics(self) -> None:
        """Verify distinction between declared OpenXML tables and inferred hypotheses."""
        box = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=4)

        # Declared
        declared = SpatialTableRegion(
            region_id="spat_decl_tbl",
            sheet_name="Sheet1",
            bounding_box=box,
            region_type=SpatialRegionType.DECLARED_TABLE,
            is_declared=True,
            declared_name="SalesTable",
            heuristic_confidence=1.0,
            cell_count=40,
            populated_cell_count=40,
            density=1.0,
        )
        assert declared.is_declared is True
        assert declared.declared_name == "SalesTable"
        assert declared.heuristic_confidence == 1.0

        # Inferred
        inferred = SpatialTableRegion(
            region_id="spat_inf_tbl",
            sheet_name="Sheet1",
            bounding_box=box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            is_declared=False,
            heuristic_confidence=0.75,
            cell_count=40,
            populated_cell_count=30,
            density=0.75,
        )
        assert inferred.is_declared is False
        assert inferred.declared_name is None

    def test_nested_and_overlapping_relationships(self) -> None:
        """Verify nested parent-child and overlapping region tracking."""
        outer_box = BoundingBox(min_row=1, max_row=50, min_col=1, max_col=20)
        inner_box = BoundingBox(min_row=10, max_row=30, min_col=5, max_col=15)

        child = SpatialTableRegion(
            region_id="child_region",
            sheet_name="Sheet1",
            bounding_box=inner_box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=0.80,
            parent_region_id="parent_region",
            cell_count=inner_box.cell_count,
            populated_cell_count=200,
            density=round(200 / inner_box.cell_count, 4),
        )
        parent = SpatialTableRegion(
            region_id="parent_region",
            sheet_name="Sheet1",
            bounding_box=outer_box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=0.85,
            child_region_ids=["child_region"],
            cell_count=outer_box.cell_count,
            populated_cell_count=800,
            density=round(800 / outer_box.cell_count, 4),
        )

        assert child.parent_region_id == "parent_region"
        assert parent.child_region_ids == ["child_region"]

    def test_to_table_metadata_unresolved_raises_not_implemented(self) -> None:
        """Verify that to_table_metadata refuses to fabricate missing header/type data."""
        box = BoundingBox(min_row=2, max_row=20, min_col=1, max_col=5)
        region = SpatialTableRegion(
            region_id="spat_unresolved",
            sheet_name="Sheet1",
            bounding_box=box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=0.85,
            cell_count=95,
            populated_cell_count=90,
            density=0.9474,
            header_row=None,  # Unresolved in Prompt 2
            columns=None,     # Unresolved in Prompt 2
        )

        with pytest.raises(NotImplementedError) as exc_info:
            region.to_table_metadata()

        assert "Lossless conversion to TableMetadata requires resolved header_row" in str(exc_info.value)

    def test_to_table_metadata_lossless_bridge_when_resolved(self) -> None:
        """Verify lossless conversion to M01 TableMetadata when header & columns are populated."""
        box = BoundingBox(min_row=2, max_row=20, min_col=1, max_col=2)
        cols = [
            ColumnMetadata(
                index=1,
                header_name="ID",
                inferred_type=ColumnType.INTEGER,
                type_confidence=0.99,
            ),
            ColumnMetadata(
                index=2,
                header_name="Revenue",
                inferred_type=ColumnType.DECIMAL,
                type_confidence=0.95,
            ),
        ]
        region = SpatialTableRegion(
            region_id="spat_resolved",
            sheet_name="Sheet1",
            bounding_box=box,
            region_type=SpatialRegionType.DECLARED_TABLE,
            is_declared=True,
            declared_name="RevenueTable",
            heuristic_confidence=1.0,
            cell_count=38,
            populated_cell_count=38,
            density=1.0,
            header_row=2,
            columns=cols,
        )

        metadata: TableMetadata = region.to_table_metadata()

        assert metadata.sheet_name == "Sheet1"
        assert metadata.header_row == 2
        assert metadata.is_list_object is True
        assert metadata.list_object_name == "RevenueTable"
        assert len(metadata.columns) == 2
        assert metadata.columns[0].index == 1
        assert metadata.columns[0].header_name == "ID"
        assert metadata.columns[0].inferred_type == ColumnType.INTEGER
        assert metadata.columns[0].type_confidence == 0.99
        assert metadata.columns[1].index == 2
        assert metadata.columns[1].header_name == "Revenue"
        assert metadata.columns[1].inferred_type == ColumnType.DECIMAL
        assert metadata.columns[1].type_confidence == 0.95
        assert metadata.bounding_box.start_row == 2
        assert metadata.bounding_box.end_row == 20
        assert metadata.bounding_box.start_col == 1
        assert metadata.bounding_box.end_col == 2
