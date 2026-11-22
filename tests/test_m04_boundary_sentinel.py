"""Comprehensive Test Suite for ADR-005 Append Boundary Sentinel (M04 Prompt 4).

Verifies:
- Zero-space collision detection on ordinary ranges (halts append execution)
- Spare margin row calculation below table boundary
- Trailing formula proximity detection (=SUM, =AVERAGE referencing table)
- Declared OpenXML ListObject exemption (native expansion allowed)
- Adjacent table collision below table boundary
"""

from __future__ import annotations

from typing import Any, Optional
import pytest

from excel_intel.inspection.models import BoundingBox
from excel_intel.spatial.boundary_sentinel import BoundarySentinel
from excel_intel.spatial.models import (
    MarginClearance,
    SpatialEvidenceType,
    SpatialRegionType,
    SpatialTableRegion,
)


def make_region(
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    region_id: str = "reg_test",
    is_declared: bool = False,
    declared_name: Optional[str] = None,
) -> SpatialTableRegion:
    box = BoundingBox(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)
    cell_count = box.cell_count
    return SpatialTableRegion(
        region_id=region_id,
        sheet_name="Sheet1",
        bounding_box=box,
        region_type=SpatialRegionType.DECLARED_TABLE if is_declared else SpatialRegionType.INFERRED_TABLE,
        is_declared=is_declared,
        declared_name=declared_name,
        heuristic_confidence=1.0 if is_declared else 0.90,
        cell_count=cell_count,
        populated_cell_count=cell_count,
        density=1.0,
    )


def create_row_dict(row: int, cells: list[tuple[int, Any, Optional[str]]]) -> dict[str, Any]:
    return {
        "row": row,
        "cells": [{"col": c, "value": v, "formula": f} for c, v, f in cells],
    }


class TestBoundarySentinel:
    """Test suite for ADR-005 boundary clearance and collision detection."""

    def test_ordinary_range_zero_space_collision(self) -> None:
        """Verify ordinary range with 0 spare rows below triggers zero-space collision and halts append."""
        # Table spans rows 1..10, cols 1..3
        # Row 11 contains data cells (spare_rows_below = 0)
        region = make_region(1, 10, 1, 3, is_declared=False)
        stream_rows = [
            create_row_dict(11, [(1, "CollidingData", None), (2, 999, None)]),
        ]

        sentinel = BoundarySentinel(scan_depth=5)
        clearance = sentinel.evaluate_margin(region, stream_rows)

        assert clearance.spare_rows_below == 0
        assert clearance.has_zero_space_collision is True
        assert clearance.safe_for_append is False
        assert clearance.collision_reason is not None
        assert "ADR-005 Collision: Ordinary range has 0 spare rows" in clearance.collision_reason
        assert any(e.evidence_type == SpatialEvidenceType.BOUNDARY_COLLISION_DETECTED for e in clearance.evidence)

    def test_ordinary_range_sufficient_spare_rows(self) -> None:
        """Verify ordinary range with 3 spare blank rows below is evaluated as safe for append."""
        # Table spans rows 1..10
        # Row 14 contains data (rows 11, 12, 13 are empty -> spare_rows_below = 3)
        region = make_region(1, 10, 1, 3, is_declared=False)
        stream_rows = [
            create_row_dict(14, [(1, "FarAwayData", None)]),
        ]

        sentinel = BoundarySentinel(scan_depth=5)
        clearance = sentinel.evaluate_margin(region, stream_rows)

        assert clearance.spare_rows_below == 3
        assert clearance.has_zero_space_collision is False
        assert clearance.has_trailing_formulas is False
        assert clearance.safe_for_append is True
        assert any(e.evidence_type == SpatialEvidenceType.BOUNDARY_SAFE_CLEARANCE for e in clearance.evidence)

    def test_trailing_summary_formula_proximity_blocks_append(self) -> None:
        """Verify formula immediately following table blocks automated append under ADR-005."""
        # Table at rows 1..20
        # Row 21 contains '=SUM(B2:B20)'
        region = make_region(1, 20, 1, 3, is_declared=False)
        stream_rows = [
            create_row_dict(21, [(1, "Total", None), (2, 5000, "=SUM(B2:B20)")]),
        ]

        sentinel = BoundarySentinel(scan_depth=5)
        clearance = sentinel.evaluate_margin(region, stream_rows)

        assert clearance.spare_rows_below == 0
        assert clearance.has_trailing_formulas is True
        assert "=SUM(B2:B20)" in clearance.adjacent_formulas
        assert clearance.safe_for_append is False
        assert any(e.evidence_type == SpatialEvidenceType.TRAILING_FORMULA_COLLISION for e in clearance.evidence)

    def test_declared_list_object_exemption(self) -> None:
        """Verify declared OpenXML ListObject is safe for append despite zero space due to native expansion."""
        # Declared table at rows 1..10
        # Row 11 is occupied
        region = make_region(1, 10, 1, 3, is_declared=True, declared_name="SalesTable")
        stream_rows = [
            create_row_dict(11, [(1, "NextBlock", None)]),
        ]

        sentinel = BoundarySentinel(scan_depth=5)
        clearance = sentinel.evaluate_margin(region, stream_rows)

        # For ListObject, Excel handles table expansion natively
        assert clearance.safe_for_append is True
        assert clearance.collision_reason is None
        assert any("native table expansion enabled" in e.description for e in clearance.evidence)

    def test_adjacent_table_boundary_collision(self) -> None:
        """Verify another table starting at max_row + 1 triggers zero-space collision."""
        reg1 = make_region(1, 10, 1, 3, region_id="tbl_1")
        reg2 = make_region(11, 20, 1, 3, region_id="tbl_2")

        sentinel = BoundarySentinel(scan_depth=5)
        clearance = sentinel.evaluate_margin(reg1, [], other_regions=[reg1, reg2])

        assert clearance.spare_rows_below == 0
        assert clearance.has_zero_space_collision is True
        assert clearance.safe_for_append is False

    def test_err_boundary_collision_code_and_hidden_rows(self) -> None:
        """Verify ERR_BOUNDARY_COLLISION code prefix and hidden row collision annotation."""
        from excel_intel.inspection.models import DeclaredOpenXmlFacts, DeclaredSheetProperties, HiddenInterval

        reg = make_region(1, 10, 1, 3, is_declared=False)
        stream_rows = [
            create_row_dict(11, [(1, "HiddenFormula", "=SUM(A2:A10)")]),
        ]
        facts = DeclaredOpenXmlFacts(
            properties=DeclaredSheetProperties(sheet_id=1, name="Sheet1"),
            hidden_rows=[HiddenInterval(dimension="row", start=11, end=11)],
        )

        sentinel = BoundarySentinel(scan_depth=5)
        clearance = sentinel.evaluate_margin(reg, stream_rows, facts=facts)

        assert clearance.safe_for_append is False
        assert clearance.collision_reason is not None
        assert "ERR_BOUNDARY_COLLISION" in clearance.collision_reason
        assert "Row 11 is hidden in worksheet view" in clearance.collision_reason
