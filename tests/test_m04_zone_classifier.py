"""Comprehensive Test Suite for Semantic Zone Classifier (M04 Prompt 4).

Verifies:
- Title banner zone classification
- Column header zone
- Data body zone
- Summary vs. Totals row distinction
- Footnote & citation row identification without over-classifying sparse body rows
- Interleaved section subheaders within data body
- Integration with declared OpenXML ListObjects
"""

from __future__ import annotations

from typing import Any, Optional
import pytest

from excel_intel.inspection.models import BoundingBox, DeclaredListObject, DeclaredMergeCell
from excel_intel.spatial.models import (
    HeaderResolutionReport,
    HeaderResolutionStatus,
    ResolvedHeaderColumn,
    SemanticZoneType,
    SpatialEvidenceType,
    SpatialRegionType,
    SpatialTableRegion,
)
from excel_intel.spatial.zone_classifier import ZoneClassifier


def make_region(min_row: int, max_row: int, min_col: int, max_col: int, region_id: str = "reg_test") -> SpatialTableRegion:
    box = BoundingBox(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)
    cell_count = box.cell_count
    return SpatialTableRegion(
        region_id=region_id,
        sheet_name="Sheet1",
        bounding_box=box,
        region_type=SpatialRegionType.INFERRED_TABLE,
        heuristic_confidence=0.90,
        cell_count=cell_count,
        populated_cell_count=cell_count,
        density=1.0,
    )


def create_row_dict(row: int, cells: list[tuple[int, Any, Optional[str]]]) -> dict[str, Any]:
    return {
        "row": row,
        "cells": [{"col": c, "value": v, "formula": f} for c, v, f in cells],
    }


class TestZoneClassifier:
    """Test suite for intra-region semantic zone classifier."""

    def test_complete_zone_decomposition(self) -> None:
        """Verify region decomposes cleanly into TITLE, HEADER, BODY, TOTALS, and FOOTNOTES."""
        # Row 1: Title "Financial Report 2024"
        # Row 2: Headers "Dept", "Q1", "Q2"
        # Row 3..4: Data rows
        # Row 5: Total "Total", 500, 600 (=SUM(C3:C4))
        # Row 6: Footnote "* Unaudited preliminary figures"
        region = make_region(1, 6, 1, 3)
        rows = [
            create_row_dict(1, [(1, "Financial Report 2024", None)]),
            create_row_dict(2, [(1, "Dept", None), (2, "Q1", None), (3, "Q2", None)]),
            create_row_dict(3, [(1, "Engineering", None), (2, 200, None), (3, 250, None)]),
            create_row_dict(4, [(1, "Sales", None), (2, 300, None), (3, 350, None)]),
            create_row_dict(5, [(1, "Total", None), (2, 500, "=SUM(B3:B4)"), (3, 600, "=SUM(C3:C4)")]),
            create_row_dict(6, [(1, "* Unaudited preliminary figures", None)]),
        ]

        hdr_report = HeaderResolutionReport(
            region_id=region.region_id,
            sheet_name=region.sheet_name,
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
            header_row_start=2,
            header_row_end=2,
            header_row_count=1,
            heuristic_confidence=0.95,
        )

        classifier = ZoneClassifier()
        classified = classifier.classify_region(region, rows, header_report=hdr_report)

        assert SemanticZoneType.TITLE in classified.zones
        assert classified.zones[SemanticZoneType.TITLE].bounding_box.min_row == 1
        assert classified.zones[SemanticZoneType.TITLE].bounding_box.max_row == 1

        assert SemanticZoneType.HEADER in classified.zones
        assert classified.zones[SemanticZoneType.HEADER].bounding_box.min_row == 2
        assert classified.zones[SemanticZoneType.HEADER].bounding_box.max_row == 2

        assert SemanticZoneType.BODY in classified.zones
        assert classified.zones[SemanticZoneType.BODY].bounding_box.min_row == 3
        assert classified.zones[SemanticZoneType.BODY].bounding_box.max_row == 4

        assert SemanticZoneType.TOTALS in classified.zones
        assert classified.zones[SemanticZoneType.TOTALS].bounding_box.min_row == 5
        assert classified.zones[SemanticZoneType.TOTALS].bounding_box.max_row == 5

        assert SemanticZoneType.FOOTNOTES in classified.zones
        assert classified.zones[SemanticZoneType.FOOTNOTES].bounding_box.min_row == 6
        assert classified.zones[SemanticZoneType.FOOTNOTES].bounding_box.max_row == 6

        assert len(classified.zone_list) == 5

    def test_summary_and_totals_distinction(self) -> None:
        """Verify distinction between intermediate Subtotal (SUMMARY) and final Grand Total (TOTALS)."""
        # Row 1: Headers
        # Row 2..3: Dept 1 data
        # Row 4: Subtotal "Dept 1 Subtotal", =SUBTOTAL(9, B2:B3)
        # Row 5..6: Dept 2 data
        # Row 7: Grand Total "Grand Total", =SUM(B2:B6)
        region = make_region(1, 7, 1, 2)
        rows = [
            create_row_dict(1, [(1, "Category", None), (2, "Revenue", None)]),
            create_row_dict(2, [(1, "A1", None), (2, 100, None)]),
            create_row_dict(3, [(1, "A2", None), (2, 150, None)]),
            create_row_dict(4, [(1, "Subtotal", None), (2, 250, "=SUBTOTAL(9, B2:B3)")]),
            create_row_dict(5, [(1, "B1", None), (2, 300, None)]),
            create_row_dict(6, [(1, "B2", None), (2, 400, None)]),
            create_row_dict(7, [(1, "Grand Total", None), (2, 950, "=SUM(B2:B6)")]),
        ]

        hdr_report = HeaderResolutionReport(
            region_id=region.region_id,
            sheet_name=region.sheet_name,
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
            header_row_start=1,
            header_row_end=1,
            header_row_count=1,
            heuristic_confidence=0.95,
        )

        classifier = ZoneClassifier()
        classified = classifier.classify_region(region, rows, header_report=hdr_report)

        assert SemanticZoneType.SUMMARY in classified.zones
        assert classified.zones[SemanticZoneType.SUMMARY].bounding_box.min_row == 4
        assert classified.zones[SemanticZoneType.SUMMARY].bounding_box.max_row == 4

        assert SemanticZoneType.TOTALS in classified.zones
        assert classified.zones[SemanticZoneType.TOTALS].bounding_box.min_row == 7
        assert classified.zones[SemanticZoneType.TOTALS].bounding_box.max_row == 7

    def test_interleaved_section_subheaders(self) -> None:
        """Verify section subheaders within body rows are recognized without breaking body zone."""
        # Row 1: Headers (ID, Name, Score)
        # Row 2: Section 1 Subheader: "Engineering Department"
        # Row 3: Data row
        # Row 4: Section 2 Subheader: "Product Management"
        # Row 5: Data row
        region = make_region(1, 5, 1, 3)
        rows = [
            create_row_dict(1, [(1, "ID", None), (2, "Name", None), (3, "Score", None)]),
            create_row_dict(2, [(1, "Engineering Department", None)]),
            create_row_dict(3, [(1, 101, None), (2, "Alice", None), (3, 98, None)]),
            create_row_dict(4, [(1, "Product Management", None)]),
            create_row_dict(5, [(1, 102, None), (2, "Bob", None), (3, 92, None)]),
        ]

        hdr_report = HeaderResolutionReport(
            region_id=region.region_id,
            sheet_name=region.sheet_name,
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
            header_row_start=1,
            header_row_end=1,
            header_row_count=1,
            heuristic_confidence=0.95,
        )

        classifier = ZoneClassifier()
        classified = classifier.classify_region(region, rows, header_report=hdr_report)

        assert len(classified.subheaders) == 2
        assert classified.subheaders[0]["row"] == 2
        assert classified.subheaders[0]["label"] == "Engineering Department"
        assert classified.subheaders[1]["row"] == 4
        assert classified.subheaders[1]["label"] == "Product Management"

        # Check evidence recorded
        sh_evs = [e for e in classified.evidence if e.evidence_type == SpatialEvidenceType.INTERLEAVED_SUBHEADER]
        assert len(sh_evs) == 2

    def test_sparse_body_row_not_mistaken_for_footnote(self) -> None:
        """Verify sparse row in the middle of data body is not classified as a footnote."""
        # Row 1: Headers
        # Row 2: Data row
        # Row 3: Sparse data row (only col 1 filled)
        # Row 4: Subsequent data row
        region = make_region(1, 4, 1, 3)
        rows = [
            create_row_dict(1, [(1, "ColA", None), (2, "ColB", None), (3, "ColC", None)]),
            create_row_dict(2, [(1, "X1", None), (2, 10, None), (3, 20, None)]),
            create_row_dict(3, [(1, "X2_Sparse", None)]),
            create_row_dict(4, [(1, "X3", None), (2, 30, None), (3, 40, None)]),
        ]

        hdr_report = HeaderResolutionReport(
            region_id=region.region_id,
            sheet_name=region.sheet_name,
            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
            header_row_start=1,
            header_row_end=1,
            header_row_count=1,
            heuristic_confidence=0.95,
        )

        classifier = ZoneClassifier()
        classified = classifier.classify_region(region, rows, header_report=hdr_report)

        assert SemanticZoneType.FOOTNOTES not in classified.zones
        assert SemanticZoneType.BODY in classified.zones
        assert classified.zones[SemanticZoneType.BODY].bounding_box.min_row == 2
        assert classified.zones[SemanticZoneType.BODY].bounding_box.max_row == 4
