"""Comprehensive Test Suite for Hierarchical Header Resolution (M04 Prompt 3).

Verifies:
- Single-row and multi-row stacked headers
- Horizontal and vertical OpenXML merged-cell overlays
- Compound header paths with configurable delimiters
- Duplicate label disambiguation
- Title banner and summary row exclusions
- Ambiguous and no-header scenarios
- Lossless M01 ColumnMetadata conversion
- Streaming bounded lookahead
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from excel_intel.core.types import ColumnMetadata, ColumnType
from excel_intel.inspection.models import (
    BoundingBox,
    DeclaredListObject,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
    SheetVisibility,
)
from excel_intel.spatial.header_resolver import HeaderResolver
from excel_intel.spatial.models import (
    HeaderHierarchyLevel,
    HeaderResolutionReport,
    HeaderResolutionStatus,
    ResolvedHeaderColumn,
    SpatialEvidenceType,
    SpatialRegionType,
    SpatialTableRegion,
)


def create_row_dict(row: int, cells: list[tuple[int, Any, Optional[str]]]) -> dict[str, Any]:
    """Helper to create row record with (col_idx, value, formula)."""
    return {
        "row": row,
        "cells": [{"col": c, "value": v, "formula": f} for c, v, f in cells],
    }


def make_region(
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    region_id: str = "reg_test",
    sheet_name: str = "Sheet1",
    is_declared: bool = False,
) -> SpatialTableRegion:
    box = BoundingBox(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)
    cell_count = box.cell_count
    return SpatialTableRegion(
        region_id=region_id,
        sheet_name=sheet_name,
        bounding_box=box,
        region_type=SpatialRegionType.DECLARED_TABLE if is_declared else SpatialRegionType.INFERRED_TABLE,
        is_declared=is_declared,
        heuristic_confidence=1.0 if is_declared else 0.85,
        cell_count=cell_count,
        populated_cell_count=cell_count,
        density=1.0,
    )


class TestHeaderResolver:
    """Test suite for generic evidence-driven HeaderResolver."""

    def test_single_row_header_detection(self) -> None:
        """Verify conventional single-row header detection with high confidence."""
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, "EmployeeID", None), (2, "Name", None), (3, "Department", None)]),
            create_row_dict(2, [(1, 101, None), (2, "Alice", None), (3, "Engineering", None)]),
            create_row_dict(3, [(1, 102, None), (2, "Bob", None), (3, "Sales", None)]),
        ]

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.HIGH_CONFIDENCE
        assert report.heuristic_confidence >= 0.90
        assert report.header_row_start == 1
        assert report.header_row_end == 1
        assert report.header_row_count == 1
        assert len(report.columns) == 3
        assert [c.resolved_name for c in report.columns] == ["EmployeeID", "Name", "Department"]
        assert all(c.depth == 1 for c in report.columns)
        assert any(e.evidence_type == SpatialEvidenceType.SINGLE_ROW_HEADER for e in report.evidence)

    def test_multi_row_hierarchical_headers_compound_resolution(self) -> None:
        """Verify multi-row stacked header resolving into compound names with delimiter."""
        # Row 1: Financials | Financials | Operations
        # Row 2: Revenue    | Expenses   | Headcount
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Financials", None), (2, "Financials", None), (3, "Operations", None)]),
            create_row_dict(2, [(1, "Revenue", None), (2, "Expenses", None), (3, "Headcount", None)]),
            create_row_dict(3, [(1, 500000, None), (2, 350000, None), (3, 42, None)]),
        ]

        resolver = HeaderResolver(delimiter=" -> ")
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.HIGH_CONFIDENCE
        assert report.header_row_start == 1
        assert report.header_row_end == 2
        assert report.header_row_count == 2
        assert len(report.columns) == 3

        col_names = [c.resolved_name for c in report.columns]
        assert col_names == [
            "Financials -> Revenue",
            "Financials -> Expenses",
            "Operations -> Headcount",
        ]
        assert report.columns[0].raw_name == "Revenue"
        assert report.columns[0].depth == 2
        assert report.columns[0].hierarchy_levels[0].raw_value == "Financials"
        assert report.columns[0].hierarchy_levels[1].raw_value == "Revenue"
        assert any(e.evidence_type == SpatialEvidenceType.HIERARCHICAL_STACKED_HEADER for e in report.evidence)

    def test_horizontal_merged_header_ranges(self) -> None:
        """Verify horizontal merged cell overlays propagate anchor label across spanned columns."""
        # A1:B1 merged with text 'Financials'. Row 1 cell B1 is physically empty in XML.
        # C1 has 'Operations'
        # Row 2: A2='Revenue', B2='Expenses', C2='Headcount'
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Financials", None), (3, "Operations", None)]),  # col 2 is empty in XML
            create_row_dict(2, [(1, "Revenue", None), (2, "Expenses", None), (3, "Headcount", None)]),
            create_row_dict(3, [(1, 1000, None), (2, 500, None), (3, 10, None)]),
        ]
        merges = [DeclaredMergeCell.from_ref("A1:B1")]

        resolver = HeaderResolver(delimiter=" -> ")
        report = resolver.resolve_region(region, rows, merge_cells=merges)

        assert report.status == HeaderResolutionStatus.HIGH_CONFIDENCE
        assert report.header_row_count == 2
        assert [c.resolved_name for c in report.columns] == [
            "Financials -> Revenue",
            "Financials -> Expenses",
            "Operations -> Headcount",
        ]
        # Column 2 level 0 must be flagged as merged
        assert report.columns[1].hierarchy_levels[0].is_merged is True
        assert report.columns[1].hierarchy_levels[0].merge_range_ref == "A1:B1"
        assert any(e.evidence_type == SpatialEvidenceType.MERGED_HEADER_OVERLAY for e in report.evidence)

    def test_vertical_merged_header_ranges(self) -> None:
        """Verify vertical merged cell across header rows deduplicates to single depth."""
        # Row 1: A1='Q1' (merged A1:B1), C1='Status' (merged C1:C2)
        # Row 2: A2='Revenue', B2='Cost' (C2 is empty in XML due to vertical merge)
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Q1", None), (3, "Status", None)]),
            create_row_dict(2, [(1, "Revenue", None), (2, "Cost", None)]),
            create_row_dict(3, [(1, 200, None), (2, 100, None), (3, "Active", None)]),
        ]
        merges = [
            DeclaredMergeCell.from_ref("A1:B1"),
            DeclaredMergeCell.from_ref("C1:C2"),
        ]

        resolver = HeaderResolver(delimiter=" -> ")
        report = resolver.resolve_region(region, rows, merge_cells=merges)

        assert [c.resolved_name for c in report.columns] == [
            "Q1 -> Revenue",
            "Q1 -> Cost",
            "Status",
        ]
        assert report.columns[2].depth == 1
        assert report.columns[2].resolved_name == "Status"

    def test_merged_header_with_blank_child_cell_no_fabrication(self) -> None:
        """Verify that blank child cells do not fabricate placeholder text."""
        # Row 1: Operations (spans A1:B1)
        # Row 2: A2='Headcount', B2 is blank and not in vertical merge
        region = make_region(1, 10, 1, 2)
        rows = [
            create_row_dict(1, [(1, "Operations", None)]),
            create_row_dict(2, [(1, "Headcount", None)]),
            create_row_dict(3, [(1, 15, None), (2, 20, None)]),
        ]
        merges = [DeclaredMergeCell.from_ref("A1:B1")]

        resolver = HeaderResolver(delimiter=" -> ")
        report = resolver.resolve_region(region, rows, merge_cells=merges)

        assert report.columns[0].resolved_name == "Operations -> Headcount"
        # Column 2 must use parent label without fabricating dummy child text
        assert report.columns[1].resolved_name == "Operations"

    def test_duplicate_labels_disambiguation(self) -> None:
        """Verify identical header names are preserved in raw form and disambiguated uniquely."""
        region = make_region(1, 10, 1, 4)
        rows = [
            create_row_dict(1, [(1, "Score", None), (2, "Score", None), (3, "Total", None), (4, "Total", None)]),
            create_row_dict(2, [(1, 95, None), (2, 88, None), (3, 100, None), (4, 100, None)]),
        ]

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.columns[0].is_duplicate is True
        assert report.columns[0].resolved_name == "Score"
        assert report.columns[0].disambiguated_name == "Score_1"

        assert report.columns[1].is_duplicate is True
        assert report.columns[1].resolved_name == "Score"
        assert report.columns[1].disambiguated_name == "Score_2"

        assert report.columns[2].disambiguated_name == "Total_1"
        assert report.columns[3].disambiguated_name == "Total_2"

    def test_title_banner_exclusion(self) -> None:
        """Verify single-cell title banner at top of region is excluded from headers."""
        # Row 1: A1='Quarterly Earnings 2024' (single cell, cols B..C empty)
        # Row 2: A2='Quarter', B2='Revenue', C2='Profit' (real header)
        # Row 3: A3='Q1', B3=1000, C3=200
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Quarterly Earnings 2024", None)]),
            create_row_dict(2, [(1, "Quarter", None), (2, "Revenue", None), (3, "Profit", None)]),
            create_row_dict(3, [(1, "Q1", None), (2, 1000, None), (3, 200, None)]),
        ]

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.header_row_start == 2
        assert report.header_row_end == 2
        assert [c.resolved_name for c in report.columns] == ["Quarter", "Revenue", "Profit"]
        assert any(e.evidence_type == SpatialEvidenceType.TITLE_BANNER_EXCLUDED for e in report.evidence)

    def test_summary_formula_row_excluded(self) -> None:
        """Verify row with aggregation formulas is excluded from headers."""
        # Row 1 has headers; row 2 has =SUM
        region = make_region(1, 5, 1, 2)
        rows = [
            create_row_dict(1, [(1, "Metric", None), (2, "Amount", None)]),
            create_row_dict(2, [(1, "Total", None), (2, 100, "=SUM(B3:B10)")]),
        ]

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.header_row_start == 1
        assert report.header_row_end == 1
        assert any(e.evidence_type == SpatialEvidenceType.SUMMARY_ROW_EXCLUDED for e in report.evidence)

    def test_no_header_detected_for_numeric_matrix(self) -> None:
        """Verify region starting directly with numeric data yields NO_HEADER_DETECTED."""
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, 10.5, None), (2, 20.3, None), (3, 30.1, None)]),
            create_row_dict(2, [(1, 11.2, None), (2, 22.4, None), (3, 31.8, None)]),
        ]

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.NO_HEADER_DETECTED
        assert len(report.columns) == 0
        assert any(e.evidence_type == SpatialEvidenceType.NO_HEADER_DETECTED for e in report.evidence)

    def test_ambiguous_header_detection(self) -> None:
        """Verify mixed type or sparse rows are flagged as AMBIGUOUS with confidence degradation."""
        # Row 1: 1 text label, 2 numeric cells in a 3-column table
        region = make_region(1, 5, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Label", None), (2, 45, None), (3, 99, None)]),
            create_row_dict(2, [(1, "Val1", None), (2, 50, None), (3, 102, None)]),
        ]

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.AMBIGUOUS
        assert report.is_ambiguous is True
        assert report.heuristic_confidence <= 0.70
        assert report.ambiguity_details is not None

    def test_configurable_delimiter(self) -> None:
        """Verify compound header delimiter can be customized."""
        region = make_region(1, 5, 1, 2)
        rows = [
            create_row_dict(1, [(1, "Sales", None), (2, "Sales", None)]),
            create_row_dict(2, [(1, "Domestic", None), (2, "Export", None)]),
            create_row_dict(3, [(1, 100, None), (2, 200, None)]),
        ]

        resolver = HeaderResolver(delimiter="::")
        report = resolver.resolve_region(region, rows)

        assert [c.resolved_name for c in report.columns] == ["Sales::Domestic", "Sales::Export"]
        assert report.delimiter_used == "::"

    def test_declared_openxml_list_object_headers(self) -> None:
        """Verify OpenXML declared table column names are prioritized with 1.0 confidence."""
        box = BoundingBox(min_row=2, max_row=20, min_col=1, max_col=3)
        region = make_region(2, 20, 1, 3, is_declared=True)
        decl_lo = DeclaredListObject(
            id=1,
            name="SalesTable",
            display_name="SalesTable",
            ref="A2:C20",
            box=box,
            header_row_count=1,
            column_names=["Region", "Quarter", "Revenue"],
        )

        resolver = HeaderResolver()
        report = resolver.resolve_region(region, [], list_objects=[decl_lo])

        assert report.status == HeaderResolutionStatus.HIGH_CONFIDENCE
        assert report.heuristic_confidence == 1.0
        assert [c.resolved_name for c in report.columns] == ["Region", "Quarter", "Revenue"]

    def test_m01_column_metadata_conversion_lossless(self) -> None:
        """Verify lossless conversion from ResolvedHeaderColumn to M01 ColumnMetadata."""
        col = ResolvedHeaderColumn(
            col_index=2,
            resolved_name="Financials -> Revenue",
            raw_name="Revenue",
            depth=2,
            source_coordinate="B2",
        )

        col_meta: ColumnMetadata = col.to_column_metadata(
            inferred_type=ColumnType.DECIMAL,
            type_confidence=0.98,
            nullable=False,
        )

        assert col_meta.index == 2
        assert col_meta.header_name == "Financials -> Revenue"
        assert col_meta.inferred_type == ColumnType.DECIMAL
        assert col_meta.type_confidence == 0.98
        assert col_meta.nullable is False

    def test_m01_column_metadata_conversion_refuses_fabrication(self) -> None:
        """Verify HeaderResolutionReport refuses conversion without verified column types."""
        region = make_region(1, 5, 1, 2)
        rows = [
            create_row_dict(1, [(1, "A", None), (2, "B", None)]),
            create_row_dict(2, [(1, 10, None), (2, 20, None)]),
        ]
        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        # Calling without verified types must raise NotImplementedError
        with pytest.raises(NotImplementedError) as exc_info:
            report.to_column_metadata_list(inferred_types=None)
        assert "refuses to fabricate unverified types" in str(exc_info.value)

    def test_streaming_resolve_sheet_multi_region(self) -> None:
        """Verify resolve_sheet processes multiple regions via streaming reader interface."""
        class MockReader:
            sheet_names = ["DataSheet"]
            def stream_sheet(self, sheet: str, chunk_size: int = 1000):
                yield [
                    create_row_dict(1, [(1, "ColA", None), (2, "ColB", None), (5, "ColX", None), (6, "ColY", None)]),
                    create_row_dict(2, [(1, 10, None), (2, 20, None), (5, 100, None), (6, 200, None)]),
                ]

        reg1 = make_region(1, 10, 1, 2, region_id="r1", sheet_name="DataSheet")
        reg2 = make_region(1, 10, 5, 6, region_id="r2", sheet_name="DataSheet")

        resolver = HeaderResolver()
        reports = resolver.resolve_sheet(MockReader(), "DataSheet", [reg1, reg2])

        assert len(reports) == 2
        assert [c.resolved_name for c in reports[0].columns] == ["ColA", "ColB"]
        assert [c.resolved_name for c in reports[1].columns] == ["ColX", "ColY"]

    def test_partially_populated_headers(self) -> None:
        """Verify partially populated header rows yield TENTATIVE resolution status."""
        region = make_region(1, 10, 1, 3)
        # Column 2 has empty header
        rows = [
            create_row_dict(1, [(1, "Region", None), (3, "Revenue", None)]),
            create_row_dict(2, [(1, "North", None), (2, "Active", None), (3, 1000, None)]),
        ]
        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.TENTATIVE
        assert report.heuristic_confidence <= 0.80
        assert report.columns[0].resolved_name == "Region"
        assert report.columns[1].resolved_name == ""
        assert report.columns[2].resolved_name == "Revenue"

    def test_large_row_and_column_coordinates(self) -> None:
        """Verify header resolution functions correctly at extreme row and column coordinates."""
        # Row 50,000, cols 16,380..16,384 (XFA..XFD)
        region = make_region(50000, 50050, 16380, 16384)
        rows = [
            create_row_dict(50000, [(16380, "ExtA", None), (16381, "ExtB", None), (16384, "ExtE", None)]),
            create_row_dict(50001, [(16380, 10, None), (16381, 20, None), (16384, 50, None)]),
        ]
        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.header_row_start == 50000
        assert len(report.columns) == 5
        assert report.columns[0].col_index == 16380
        assert report.columns[4].col_index == 16384
        assert report.columns[0].resolved_name == "ExtA"
        assert report.columns[4].resolved_name == "ExtE"

    def test_resource_limit_overflow_and_incomplete_status(self) -> None:
        """Verify lookahead ceiling truncation raises INCOMPLETE_RESOURCE_LIMIT status."""
        # Region spans rows 1..100.
        # First 4 rows are all text: row 1, 2, 3, 4
        # Configure max_header_scan_rows = 2
        region = make_region(1, 100, 1, 2)
        rows = [
            create_row_dict(1, [(1, "A1", None), (2, "B1", None)]),
            create_row_dict(2, [(1, "A2", None), (2, "B2", None)]),
            create_row_dict(3, [(1, "A3", None), (2, "B3", None)]),
        ]
        resolver = HeaderResolver(max_header_scan_rows=2)
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.INCOMPLETE_RESOURCE_LIMIT
        assert report.is_truncated is True
        assert report.truncation_details is not None
        assert "reached lookahead limit of 2 rows" in report.truncation_details
        assert report.heuristic_confidence == 0.50

    def test_deterministic_output_across_repeated_runs(self) -> None:
        """Verify identical input produces strictly identical HeaderResolutionReport across runs."""
        region = make_region(1, 10, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Dept", None), (2, "Role", None), (3, "Salary", None)]),
            create_row_dict(2, [(1, "Eng", None), (2, "Dev", None), (3, 100000, None)]),
        ]
        resolver = HeaderResolver()
        rep1 = resolver.resolve_region(region, rows)
        rep2 = resolver.resolve_region(region, rows)

        assert rep1.model_dump() == rep2.model_dump()

    def test_multi_sheet_and_hidden_sheet_streaming(self) -> None:
        """Verify resolve_sheet functions across both visible and hidden sheets."""
        class MockMultiSheetReader:
            sheet_names = ["VisibleData", "HiddenRef"]
            def stream_sheet(self, sheet: str, chunk_size: int = 1000):
                if sheet == "VisibleData":
                    yield [
                        create_row_dict(1, [(1, "Item", None), (2, "Qty", None)]),
                        create_row_dict(2, [(1, "Apples", None), (2, 10, None)]),
                    ]
                elif sheet == "HiddenRef":
                    yield [
                        create_row_dict(1, [(1, "Code", None), (2, "Factor", None)]),
                        create_row_dict(2, [(1, "A1", None), (2, 1.5, None)]),
                    ]

        reader = MockMultiSheetReader()
        resolver = HeaderResolver()
        reg_vis = make_region(1, 5, 1, 2, region_id="r_vis", sheet_name="VisibleData")
        reg_hid = make_region(1, 5, 1, 2, region_id="r_hid", sheet_name="HiddenRef")

        rep_vis = resolver.resolve_sheet(reader, "VisibleData", [reg_vis])
        rep_hid = resolver.resolve_sheet(reader, "HiddenRef", [reg_hid])

        assert len(rep_vis) == 1
        assert [c.resolved_name for c in rep_vis[0].columns] == ["Item", "Qty"]

        assert len(rep_hid) == 1
        assert [c.resolved_name for c in rep_hid[0].columns] == ["Code", "Factor"]

    def test_concurrent_independent_workbook_processing(self) -> None:
        """Verify HeaderResolver operates safely across concurrent worker threads."""
        import concurrent.futures

        def worker(idx: int) -> tuple[int, list[str]]:
            resolver = HeaderResolver()
            reg = make_region(1, 10, 1, 2, region_id=f"r_{idx}", sheet_name=f"Sheet_{idx}")
            rows = [
                create_row_dict(1, [(1, f"Col_{idx}_A", None), (2, f"Col_{idx}_B", None)]),
                create_row_dict(2, [(1, 10, None), (2, 20, None)]),
            ]
            report = resolver.resolve_region(reg, rows)
            return idx, [c.resolved_name for c in report.columns]

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker, i) for i in range(1, 9)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 8
        for idx, cols in results:
            assert cols == [f"Col_{idx}_A", f"Col_{idx}_B"]

    def test_source_workbook_sha_unchanged(self, tmp_path: Path) -> None:
        """Verify workbook bytes remain immutable before and after header resolution."""
        import hashlib
        from excel_intel.core.parser import StreamingWorkbookReader
        from tests.test_m04_grid_segmenter import build_synthetic_workbook

        test_rows = [(1, [1, 2]), (2, [1, 2])]
        wb_path = build_synthetic_workbook(tmp_path, "sha_check.xlsx", test_rows)

        sha_before = hashlib.sha256(wb_path.read_bytes()).hexdigest()

        reader = StreamingWorkbookReader(wb_path)
        reg = make_region(1, 2, 1, 2, sheet_name="Sheet1")
        resolver = HeaderResolver()
        reports = resolver.resolve_sheet(reader, "Sheet1", [reg])

        sha_after = hashlib.sha256(wb_path.read_bytes()).hexdigest()

        assert sha_before == sha_after
        assert len(reports) == 1

    def test_formula_in_text_header_not_mistaken_for_summary(self) -> None:
        """Verify row with dynamic text formula and zero numeric cells is accepted as valid header."""
        region = make_region(1, 5, 1, 2)
        # Row 1 has text header cells, but one uses a formula to compute string
        rows = [
            create_row_dict(1, [(1, "Region", None), (2, "Quarter 1", '="Quarter " & 1')]),
            create_row_dict(2, [(1, "EMEA", None), (2, 500, None)]),
        ]
        resolver = HeaderResolver()
        report = resolver.resolve_region(region, rows)

        assert report.status == HeaderResolutionStatus.HIGH_CONFIDENCE
        assert report.header_row_start == 1
        assert report.header_row_end == 1
        assert [c.resolved_name for c in report.columns] == ["Region", "Quarter 1"]
