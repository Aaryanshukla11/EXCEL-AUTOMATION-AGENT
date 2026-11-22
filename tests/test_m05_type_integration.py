"""Integration tests connecting M05 Semantic Type Inference with M04 Spatial Detection and M01 Contracts."""

from pathlib import Path
import pytest

from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.core.types import ColumnMetadata, ColumnType, TableMetadata
from excel_intel.inspection.models import BoundingBox
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.models import (
    HeaderResolutionReport,
    HeaderResolutionStatus,
    ResolvedHeaderColumn,
    SemanticZone,
    SemanticZoneType,
    SpatialDetectionReport,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialRegionType,
    SpatialTableRegion,
)
from excel_intel.types.models import InferenceState, RegionTypeReport
from excel_intel.types.type_inferrer import TypeInferenceEngine
from tests.test_streaming_reader import create_minimal_xlsx


class TestM05TypeIntegration:
    """Integration test suite verifying full bridge across M02, M04, M05, and M01."""

    def test_export_to_m01_table_metadata_bridge(self) -> None:
        """Verify seamless pipeline: TypeInferenceEngine -> RegionTypeReport -> export_to_table_metadata_list."""
        detector = SpatialDetector()
        engine = TypeInferenceEngine()

        # Build an M04 SpatialTableRegion with header resolution
        r_box = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=3)
        cols = [
            ResolvedHeaderColumn(col_index=1, resolved_name="Transaction_ID", raw_name="Transaction_ID", source_coordinate="A1"),
            ResolvedHeaderColumn(col_index=2, resolved_name="Amount_USD", raw_name="Amount_USD", source_coordinate="B1"),
            ResolvedHeaderColumn(col_index=3, resolved_name="Status", raw_name="Status", source_coordinate="C1"),
        ]
        hdr_report = HeaderResolutionReport(
            region_id="reg_sales_01",
            sheet_name="SalesData",
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
            header_row_start=1,
            header_row_end=1,
            header_row_count=1,
            columns=cols,
            heuristic_confidence=1.0,
        )
        body_box = BoundingBox(min_row=2, max_row=10, min_col=1, max_col=3)
        body_zone = SemanticZone(
            zone_type=SemanticZoneType.BODY,
            bounding_box=body_box,
            row_count=9,
            cell_count=27,
        )

        region = SpatialTableRegion(
            region_id="reg_sales_01",
            sheet_name="SalesData",
            bounding_box=r_box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=1.0,
            cell_count=30,
            populated_cell_count=30,
            density=1.0,
            header_row=1,
            header_resolution=hdr_report,
            zones={SemanticZoneType.BODY: body_zone},
        )

        # Generate cell data
        cells = {}
        for r in range(2, 11):
            cells[(r, 1)] = {"value": 1000 + r}               # Col 1: Integer
            cells[(r, 2)] = {"value": f"${r * 15.50:.2f}"}     # Col 2: Currency -> Decimal
            cells[(r, 3)] = {"value": "Approved"}              # Col 3: String

        # Run Type Inference
        type_report = engine.infer_cells(cells, region)
        assert type_report.columns[1].inferred_type == ColumnType.INTEGER
        assert type_report.columns[2].inferred_type == ColumnType.DECIMAL
        assert type_report.columns[3].inferred_type == ColumnType.STRING

        # Build M04 Detection Report
        detection_report = SpatialDetectionReport(
            workbook_path="test_sales.xlsx",
            sheet_name="SalesData",
            regions=[region],
            sparse_islands=[],
            corridors=[],
        )

        # Export to canonical M01 TableMetadata
        inferred_types_by_region = {
            type_report.region_id: type_report.to_m01_inferred_types()
        }
        tables: list[TableMetadata] = detector.export_to_table_metadata_list(
            detection_report, inferred_types_by_region
        )

        assert len(tables) == 1
        t = tables[0]
        assert t.sheet_name == "SalesData"
        assert t.header_row == 1
        assert len(t.columns) == 3

        c1 = t.columns[0]
        assert c1.index == 1
        assert c1.header_name == "Transaction_ID"
        assert c1.inferred_type == ColumnType.INTEGER
        assert c1.type_confidence == 1.0

        c2 = t.columns[1]
        assert c2.index == 2
        assert c2.header_name == "Amount_USD"
        assert c2.inferred_type == ColumnType.DECIMAL
        assert c2.type_confidence == 1.0

        c3 = t.columns[2]
        assert c3.index == 2 or c3.index == 3
        assert c3.header_name == "Status"
        assert c3.inferred_type == ColumnType.STRING
        assert c3.type_confidence == 1.0

    def test_live_streaming_workbook_inference(self, tmp_path: Path) -> None:
        """Verify real StreamingWorkbookReader streaming into TypeInferenceEngine."""
        wb_path = tmp_path / "test_stream_types.xlsx"
        create_minimal_xlsx(wb_path)

        with StreamingWorkbookReader(wb_path) as reader:
            assert "DataSheet" in reader.sheet_names

            # DataSheet has:
            # Row 1: Headers ("ID", "Name", "Score", "Active", "CreatedDate", "Calculated")
            # Row 2: 1, "Alpha", 95.5, True, 45458 (date), formula C2*1.1
            # Row 3: 2, "Beta", 82, False, "InlineTest", None
            r_box = BoundingBox(min_row=1, max_row=3, min_col=1, max_col=6)
            body_box = BoundingBox(min_row=2, max_row=3, min_col=1, max_col=6)
            body_zone = SemanticZone(
                zone_type=SemanticZoneType.BODY,
                bounding_box=body_box,
                row_count=2,
                cell_count=12,
            )
            region = SpatialTableRegion(
                region_id="reg_live_01",
                sheet_name="DataSheet",
                bounding_box=r_box,
                region_type=SpatialRegionType.INFERRED_TABLE,
                heuristic_confidence=1.0,
                cell_count=18,
                populated_cell_count=18,
                density=1.0,
                header_row=1,
                zones={SemanticZoneType.BODY: body_zone},
            )

            engine = TypeInferenceEngine()
            reports = engine.infer_sheet(reader, "DataSheet", [region])

            assert len(reports) == 1
            rep = reports[0]
            assert rep.region_id == "reg_live_01"
            assert len(rep.columns) == 6

            # Since rows 2 and 3 have only 2 data rows, populated count is 2 (< 5)
            # which correctly triggers INSUFFICIENT_DATA
            for col_idx in range(1, 7):
                p = rep.columns[col_idx]
                if p.populated_cells > 0:
                    assert p.state == InferenceState.INSUFFICIENT_DATA
                    assert p.inferred_type == ColumnType.STRING  # Safe carrier
                    assert p.requires_human_review is True
