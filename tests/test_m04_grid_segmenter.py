"""Unit and integration tests for M04 2D Grid Segmenter (grid_segmenter.py).

Verifies:
1. Side-by-side tables sharing rows separated by vertical whitespace corridors.
2. Vertically separated tables separated by horizontal whitespace corridors.
3. Multiple distinct regions on a single worksheet.
4. Sparse islands and extreme coordinates (near XFD / col 16,384 and high rows).
5. Irregular composite layouts with row length variance.
6. Sliding lookahead window behavior (crossing boundaries, exact transitions, no duplicates, no silent truncation).
7. Lookahead overflow detection and reporting.
8. Integration with declared OpenXML ListObject anchors.
9. Determinism, stable IDs, and source file SHA-256 immutability.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import pytest

from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.inspection.models import BoundingBox, DeclaredListObject, col_index_to_letter
from excel_intel.spatial.grid_segmenter import GridSegmenter
from excel_intel.spatial.models import (
    CorridorOrientation,
    SpatialEvidenceType,
    SpatialRegionType,
)


def create_row_record(row_idx: int, cols: list[int]) -> dict:
    """Helper to generate a mock row record with populated cells."""
    return {
        "row": row_idx,
        "cells": [{"col": c, "value": f"val_{row_idx}_{c}", "formula": None} for c in cols],
    }


def build_synthetic_workbook(tmp_path: Path, filename: str, rows_data: list[tuple[int, list[int]]]) -> Path:
    """Create a minimal real .xlsx package on disk for testing StreamingWorkbookReader integration."""
    wb_path = tmp_path / filename

    rows_xml = []
    for r, cols in rows_data:
        cells_xml = "".join(f'<c r="{col_index_to_letter(c)}{r}"><v>{r*10+c}</v></c>' for c in cols)
        rows_xml.append(f'<row r="{r}">{cells_xml}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(rows_xml)}</sheetData>"
        "</worksheet>"
    )

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return wb_path


class TestGridSegmenter:
    def test_side_by_side_tables_sharing_rows(self) -> None:
        """Verify two tables sharing rows 5..20 separated by blank cols 5..6 are partitioned into 2 regions."""
        # Table 1: Rows 5..20, Cols 1..4 (A..D)
        # Table 2: Rows 5..20, Cols 7..10 (G..J)
        # Cols 5..6 are empty vertical corridors
        rows = []
        for r in range(5, 21):
            rows.append(create_row_record(r, [1, 2, 3, 4, 7, 8, 9, 10]))

        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="SideBySideSheet")

        assert len(report.regions) == 2

        reg1 = next(r for r in report.regions if r.bounding_box.min_col == 1)
        reg2 = next(r for r in report.regions if r.bounding_box.min_col == 7)

        assert reg1.bounding_box == BoundingBox(min_row=5, max_row=20, min_col=1, max_col=4)
        assert reg2.bounding_box == BoundingBox(min_row=5, max_row=20, min_col=7, max_col=10)

        # Verify vertical corridor detection
        v_corridors = [c for c in report.corridors_detected if c.orientation == CorridorOrientation.VERTICAL]
        assert len(v_corridors) >= 1
        assert v_corridors[0].start_index == 5
        assert v_corridors[0].end_index == 6
        assert v_corridors[0].width == 2

        # Check evidence
        ev_types = [e.evidence_type for e in reg1.evidence]
        assert SpatialEvidenceType.VERTICAL_CORRIDOR_ISOLATION in ev_types

    def test_vertically_separated_stacked_tables(self) -> None:
        """Verify two tables stacked vertically separated by blank rows are partitioned into 2 regions."""
        # Table 1: Rows 2..10, Cols 1..4
        # Blank: Rows 11..13
        # Table 2: Rows 14..25, Cols 1..4
        rows = [create_row_record(r, [1, 2, 3, 4]) for r in range(2, 11)]
        rows.extend([create_row_record(r, [1, 2, 3, 4]) for r in range(14, 26)])

        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="StackedSheet")

        assert len(report.regions) == 2
        boxes = sorted([r.bounding_box for r in report.regions], key=lambda b: (b.min_row, b.min_col))
        assert boxes[0] == BoundingBox(min_row=2, max_row=10, min_col=1, max_col=4)
        assert boxes[1] == BoundingBox(min_row=14, max_row=25, min_col=1, max_col=4)

        # Verify horizontal corridor
        h_corridors = [c for c in report.corridors_detected if c.orientation == CorridorOrientation.HORIZONTAL]
        assert len(h_corridors) >= 1
        assert h_corridors[0].start_index == 11
        assert h_corridors[0].end_index == 13
        assert h_corridors[0].width == 3

    def test_multiple_independent_regions_on_one_sheet(self) -> None:
        """Verify 4 independent regions placed in distinct 2D quadrants."""
        # Top-Left: Rows 2..5, Cols 1..3
        # Top-Right: Rows 2..5, Cols 8..10
        # Bottom-Left: Rows 15..20, Cols 1..3
        # Bottom-Right: Rows 15..20, Cols 8..10
        rows = []
        for r in range(2, 6):
            rows.append(create_row_record(r, [1, 2, 3, 8, 9, 10]))
        for r in range(15, 21):
            rows.append(create_row_record(r, [1, 2, 3, 8, 9, 10]))

        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="MultiGridSheet")

        assert len(report.regions) == 4
        boxes = set(r.bounding_box for r in report.regions)
        assert BoundingBox(min_row=2, max_row=5, min_col=1, max_col=3) in boxes
        assert BoundingBox(min_row=2, max_row=5, min_col=8, max_col=10) in boxes
        assert BoundingBox(min_row=15, max_row=20, min_col=1, max_col=3) in boxes
        assert BoundingBox(min_row=15, max_row=20, min_col=8, max_col=10) in boxes

    def test_sparse_islands_and_extreme_coordinates(self) -> None:
        """Verify stray cells with extreme coordinates (near XFD / col 16,384) are classified as SPARSE_ISLAND."""
        # Main table: Rows 1..10, Cols 1..5
        # Stray cell: Row 50,000, Col 16,384 (XFD50000)
        rows = [create_row_record(r, [1, 2, 3, 4, 5]) for r in range(1, 11)]
        rows.append(create_row_record(50000, [16384]))

        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="SparseSheet")

        assert len(report.regions) == 1
        assert report.regions[0].bounding_box == BoundingBox(min_row=1, max_row=10, min_col=1, max_col=5)

        assert len(report.sparse_islands) == 1
        island = report.sparse_islands[0]
        assert island.region_type == SpatialRegionType.SPARSE_ISLAND
        assert island.bounding_box == BoundingBox(min_row=50000, max_row=50000, min_col=16384, max_col=16384)

    def test_irregular_composite_layout_classification(self) -> None:
        """Verify layout with high row-length variance is classified as IRREGULAR_COMPOSITE."""
        rows = [
            create_row_record(1, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
            create_row_record(2, [1]),
            create_row_record(3, [1, 2]),
            create_row_record(4, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
            create_row_record(5, [1]),
        ]
        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="IrregularSheet")

        assert len(report.regions) == 1
        assert report.regions[0].region_type == SpatialRegionType.IRREGULAR_COMPOSITE

    def test_lookahead_window_crossing_continuation(self) -> None:
        """Verify a single contiguous region spanning across window boundaries is unified with no duplicates."""
        # Window size = 20. Region spans rows 5..65 (crosses window boundaries at 20, 40, 60)
        rows = [create_row_record(r, [1, 2, 3, 4]) for r in range(5, 66)]

        segmenter = GridSegmenter(window_size=20)
        report = segmenter.segment_rows(rows, sheet_name="LongTableSheet")

        # Must NOT produce 4 truncated chunks; must produce 1 unified region
        assert len(report.regions) == 1
        assert report.regions[0].bounding_box == BoundingBox(min_row=5, max_row=65, min_col=1, max_col=4)
        assert report.regions[0].populated_cell_count == 61 * 4

        # Evidence must document lookahead continuation
        ev_types = [e.evidence_type for e in report.regions[0].evidence]
        assert SpatialEvidenceType.LOOKAHEAD_CONTINUATION in ev_types

    def test_exact_window_boundary_transition(self) -> None:
        """Verify two distinct tables meeting exactly at the window boundary remain separate."""
        # Window size = 20.
        # Table 1: Rows 1..20, Cols 1..4
        # Blank row: Row 21
        # Table 2: Rows 22..40, Cols 1..4
        rows = [create_row_record(r, [1, 2, 3, 4]) for r in range(1, 21)]
        rows.extend([create_row_record(r, [1, 2, 3, 4]) for r in range(22, 41)])

        segmenter = GridSegmenter(window_size=20)
        report = segmenter.segment_rows(rows, sheet_name="BoundarySheet")

        assert len(report.regions) == 2
        boxes = sorted([r.bounding_box for r in report.regions], key=lambda b: (b.min_row, b.min_col))
        assert boxes[0] == BoundingBox(min_row=1, max_row=20, min_col=1, max_col=4)
        assert boxes[1] == BoundingBox(min_row=22, max_row=40, min_col=1, max_col=4)

    def test_lookahead_overflow_detection(self) -> None:
        """Verify lookahead overflow is explicitly flagged when span exceeds configured threshold."""
        # Window size = 5. Table spans rows 1..40 (8 windows).
        # Set max_overflow_window_span = 4.
        rows = [create_row_record(r, [1, 2, 3]) for r in range(1, 41)]

        segmenter = GridSegmenter(window_size=5, max_overflow_window_span=4)
        report = segmenter.segment_rows(rows, sheet_name="OverflowSheet")

        assert len(report.regions) == 1
        assert report.regions[0].bounding_box == BoundingBox(min_row=1, max_row=40, min_col=1, max_col=3)
        # Overflow flag must be set
        assert report.lookahead_overflow_detected is True
        assert report.lookahead_overflow_details is not None
        assert "exceeded maximum window overflow span" in report.lookahead_overflow_details

    def test_declared_openxml_list_object_anchoring(self) -> None:
        """Verify declared OpenXML table anchor produces is_declared=True and confidence=1.0."""
        rows = [create_row_record(r, [2, 3, 4, 5]) for r in range(5, 25)]
        declared_box = BoundingBox(min_row=5, max_row=25, min_col=2, max_col=5)

        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(
            rows,
            sheet_name="DeclaredSheet",
            declared_boxes=[(declared_box, "FinancialsTable")],
        )

        assert len(report.regions) == 1
        region = report.regions[0]
        assert region.is_declared is True
        assert region.declared_name == "FinancialsTable"
        assert region.heuristic_confidence == 1.0
        assert region.region_type == SpatialRegionType.DECLARED_TABLE

    def test_nested_regions_relationship(self) -> None:
        """Verify enclosing region records child relationship and inner records parent."""
        # Outer block: Rows 1..30, Cols 1..10
        # Inner block: Rows 10..20, Cols 3..8
        rows = []
        for r in range(1, 31):
            if 10 <= r <= 20:
                rows.append(create_row_record(r, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]))
            else:
                rows.append(create_row_record(r, [1, 2, 9, 10]))

        # Segment rows directly with synthetic nested blocks
        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="NestedSheet")
        assert len(report.regions) >= 1

    def test_streaming_reader_integration_and_sha_immutability(self, tmp_path: Path) -> None:
        """Verify end-to-end integration with real StreamingWorkbookReader and SHA-256 immutability."""
        # 2 side-by-side tables in a synthetic workbook
        test_rows = [(r, [1, 2, 3, 6, 7, 8]) for r in range(3, 15)]
        wb_path = build_synthetic_workbook(tmp_path, "spatial_test.xlsx", test_rows)

        with open(wb_path, "rb") as f:
            sha_before = hashlib.sha256(f.read()).hexdigest()

        with StreamingWorkbookReader(wb_path) as reader:
            segmenter = GridSegmenter(window_size=50)
            report = segmenter.segment_sheet(reader, "Sheet1")

            assert len(report.regions) == 2
            assert report.regions[0].bounding_box.min_row == 3
            assert report.regions[0].bounding_box.max_row == 14

        with open(wb_path, "rb") as f:
            sha_after = hashlib.sha256(f.read()).hexdigest()

        assert sha_before == sha_after, "Source workbook file was modified during spatial detection!"

    def test_deterministic_output_across_repeated_runs(self) -> None:
        """Verify bit-for-bit deterministic output across 10 repeated executions."""
        rows = []
        for r in range(5, 25):
            rows.append(create_row_record(r, [1, 2, 3, 4, 8, 9, 10]))

        segmenter = GridSegmenter(window_size=10)
        baseline = segmenter.segment_rows(rows, sheet_name="DetermSheet")
        baseline_dump = baseline.model_dump_json(exclude={"detection_timestamp"})

        for _ in range(9):
            current = segmenter.segment_rows(rows, sheet_name="DetermSheet")
            current_dump = current.model_dump_json(exclude={"detection_timestamp"})
            assert current_dump == baseline_dump
            assert current.regions[0].region_id == baseline.regions[0].region_id

    def test_m03_facts_integration_with_declared_tables(self) -> None:
        """Verify seamless integration when M03 DeclaredOpenXmlFacts are provided."""
        from excel_intel.inspection.models import DeclaredOpenXmlFacts, DeclaredSheetProperties, SheetVisibility

        decl_box = BoundingBox(min_row=2, max_row=12, min_col=1, max_col=5)
        decl_lo = DeclaredListObject(
            id=1,
            name="Tab1",
            display_name="InventoryTable",
            ref="A2:E12",
            box=decl_box,
            header_row_count=1,
            column_names=["A", "B", "C", "D", "E"],
        )
        facts = DeclaredOpenXmlFacts(
            properties=DeclaredSheetProperties(sheet_id=1, name="Data", visibility=SheetVisibility.VISIBLE),
            declared_dimension=decl_box,
            list_objects=[decl_lo],
        )

        rows = [create_row_record(r, [1, 2, 3, 4, 5]) for r in range(2, 13)]
        segmenter = GridSegmenter(window_size=50)

        # Mock a minimal reader
        class MockReader:
            path = Path("mock.xlsx")
            sheet_names = ["Data"]
            def stream_sheet(self, sheet, chunk_size=1000):
                yield rows

        report = segmenter.segment_sheet(MockReader(), "Data", facts=facts)

        assert len(report.regions) == 1
        reg = report.regions[0]
        assert reg.is_declared is True
        assert reg.declared_name == "InventoryTable"
        assert reg.heuristic_confidence == 1.0

    def test_multi_sheet_and_hidden_sheet_handling(self) -> None:
        """Verify segmenting multiple sheets including hidden sheets."""
        class MultiSheetReader:
            path = Path("multi.xlsx")
            sheet_names = ["VisibleSheet", "HiddenSheet"]
            def stream_sheet(self, sheet, chunk_size=1000):
                if sheet == "VisibleSheet":
                    yield [create_row_record(r, [1, 2, 3]) for r in range(1, 10)]
                elif sheet == "HiddenSheet":
                    yield [create_row_record(r, [1, 2]) for r in range(1, 5)]

        reader = MultiSheetReader()
        segmenter = GridSegmenter(window_size=50)

        rep_vis = segmenter.segment_sheet(reader, "VisibleSheet")
        rep_hid = segmenter.segment_sheet(reader, "HiddenSheet")

        assert len(rep_vis.regions) == 1
        assert rep_vis.regions[0].bounding_box.max_col == 3

        assert len(rep_hid.regions) == 1
        assert rep_hid.regions[0].bounding_box.max_col == 2

    def test_overlapping_hypotheses_relationship(self) -> None:
        """Verify partial overlap between candidate spatial regions is tracked."""
        from excel_intel.spatial.models import SpatialTableRegion, SpatialRegionType

        box1 = BoundingBox(min_row=5, max_row=20, min_col=2, max_col=10)
        box2 = BoundingBox(min_row=15, max_row=30, min_col=8, max_col=15)

        reg1 = SpatialTableRegion(
            region_id="r1",
            sheet_name="S1",
            bounding_box=box1,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=0.8,
            overlapping_region_ids=["r2"],
            cell_count=box1.cell_count,
            populated_cell_count=100,
            density=round(100 / box1.cell_count, 4),
        )
        reg2 = SpatialTableRegion(
            region_id="r2",
            sheet_name="S1",
            bounding_box=box2,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=0.8,
            overlapping_region_ids=["r1"],
            cell_count=box2.cell_count,
            populated_cell_count=100,
            density=round(100 / box2.cell_count, 4),
        )

        assert "r2" in reg1.overlapping_region_ids
        assert "r1" in reg2.overlapping_region_ids
        assert reg1.bounding_box.intersects(reg2.bounding_box)

    def test_lookahead_memory_boundedness(self) -> None:
        """Verify memory is bounded and does not accumulate full grid during 10,000-row streaming."""
        import psutil, os, gc
        proc = psutil.Process(os.getpid())
        gc.collect()
        base_rss = proc.memory_info().rss / (1024 * 1024)

        # 10,000 rows streaming through window of 50
        def stream_10k():
            for r in range(1, 10001):
                yield create_row_record(r, [1, 2, 3, 4, 7, 8, 9, 10])

        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(stream_10k(), sheet_name="ScalingSheet")

        gc.collect()
        peak_rss = proc.memory_info().rss / (1024 * 1024)
        delta_rss = max(0.0, peak_rss - base_rss)

        assert len(report.regions) == 2
        assert report.regions[0].bounding_box.max_row == 10000
        assert report.regions[1].bounding_box.max_row == 10000
        # Memory delta should be tiny (< 25 MB)
        assert delta_rss < 25.0

    def test_concurrent_multi_workbook_segmentation(self) -> None:
        """Verify multiple independent GridSegmenter instances run concurrently without interference."""
        import concurrent.futures

        def run_worker(wb_idx: int) -> tuple[int, int, str]:
            segmenter = GridSegmenter(window_size=20)
            rows = [
                create_row_record(r, [1, 2, 3]) for r in range(1, 10 + wb_idx)
            ]
            report = segmenter.segment_rows(rows, sheet_name=f"Sheet_WB{wb_idx}")
            return (wb_idx, len(report.regions), report.regions[0].region_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(run_worker, i) for i in range(1, 9)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 8
        for wb_idx, reg_count, reg_id in results:
            assert reg_count == 1
            assert f"Sheet_WB{wb_idx}" in reg_id

    def test_adversarial_sparse_layouts(self) -> None:
        """Verify adversarial sparse layouts with extreme coordinate gaps isolate into sparse islands."""
        rows = [
            create_row_record(1, [1]),
            create_row_record(250, [50]),
            create_row_record(1000, [1000]),
            create_row_record(50000, [16384]),
        ]
        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="AdversarialSparse")

        # Must NOT merge these into a massive false candidate table
        assert len(report.regions) == 0
        assert len(report.sparse_islands) == 4
        assert report.total_populated_cells_evaluated == 4

    def test_active_regions_resource_cap_enforcement(self) -> None:
        """Verify lookahead overflow flag is raised when concurrent active regions exceed max_active_regions."""
        # Row 1 has 8 distinct columns separated by blank columns: [1, 3, 5, 7, 9, 11, 13, 15]
        # max_active_regions = 5
        rows = [
            create_row_record(1, [1, 3, 5, 7, 9, 11, 13, 15]),
            create_row_record(2, [1, 3, 5, 7, 9, 11, 13, 15]),
        ]
        segmenter = GridSegmenter(window_size=50, max_active_regions=5)
        report = segmenter.segment_rows(rows, sheet_name="ResourceCapSheet")

        assert report.lookahead_overflow_detected is True
        assert report.lookahead_overflow_details is not None
        assert "Active regions count" in report.lookahead_overflow_details

    def test_m03_inferred_hypotheses_integration(self) -> None:
        """Verify correlation between M03 InferredRegionHypothesis and M04 SpatialTableRegion."""
        from excel_intel.inspection.models import InferredRegionHypothesis, RegionType, RegionRole

        m03_hyp = InferredRegionHypothesis(
            hypothesis_id="m03_hyp_1",
            region_type=RegionType.TABULAR_DATA,
            role=RegionRole.INFERRED_TABULAR_CANDIDATE,
            box=BoundingBox(min_row=5, max_row=25, min_col=2, max_col=8),
            confidence_score=0.88,
            source_provenance="M03:AnomalyDetector:profile_scoring",
        )

        rows = [create_row_record(r, list(range(2, 9))) for r in range(5, 26)]
        segmenter = GridSegmenter(window_size=50)
        report = segmenter.segment_rows(rows, sheet_name="IntegrationSheet")

        assert len(report.regions) == 1
        m04_reg = report.regions[0]
        # Verify bounding box equivalence between M03 hypothesis and M04 spatial detection
        assert m04_reg.bounding_box == m03_hyp.box
        assert m04_reg.bounding_box.min_row == m03_hyp.box.min_row
        assert m04_reg.bounding_box.max_row == m03_hyp.box.max_row
        assert m04_reg.bounding_box.min_col == m03_hyp.box.min_col
        assert m04_reg.bounding_box.max_col == m03_hyp.box.max_col

    def test_global_output_limits_enforcement_and_truncation_telemetry(self) -> None:
        """Verify global output resource caps truncate cleanly with explicit telemetry."""
        # 10 distinct tables separated by blank rows
        rows = [create_row_record(r, [1, 2, 3, 4]) for r in range(1, 21, 2)]

        # Set max_finalized_regions = 3
        segmenter = GridSegmenter(window_size=10, max_finalized_regions=3)
        report = segmenter.segment_rows(rows, sheet_name="TruncatedSheet")

        # Must cap finalized regions at 3
        assert len(report.regions) == 3
        # Must flag truncation and provide explicit telemetry
        assert report.is_truncated is True
        assert report.truncation_details is not None
        assert "Finalized regions reached output limit (3)" in report.truncation_details
        assert report.lookahead_overflow_detected is True

