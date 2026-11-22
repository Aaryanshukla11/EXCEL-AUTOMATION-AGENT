"""ADR-005 Append Boundary Sentinel (M04).

Evaluates boundary clearance and collision safety for record append operations.
Enforces ADR-005: automated row shifting into ordinary ranges is strictly prohibited
to prevent silent formula corruption. Detects trailing aggregation formulas, zero-space
collisions, and adjacent table bounds.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

from excel_intel.inspection.models import BoundingBox
from excel_intel.spatial.models import (
    MarginClearance,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialTableRegion,
)

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader


def _is_summary_or_referencing_formula(formula: Optional[str], table_box: BoundingBox) -> bool:
    """Return True if formula references table columns/rows or contains aggregation functions."""
    if not formula:
        return False
    f_upper = formula.upper().strip()
    # Check aggregation functions
    if any(func in f_upper for func in ("SUM(", "AVERAGE(", "COUNT(", "COUNTA(", "SUBTOTAL(", "AGGREGATE(")):
        return True
    # Check if formula references row numbers within table_box
    for r in range(table_box.min_row, table_box.max_row + 1):
        if re.search(rf"\b[A-Z]+{r}\b", f_upper):
            return True
    return False


class BoundarySentinel:
    """Sentinel evaluating ADR-005 boundary clearance and append safety."""

    def __init__(self, *, scan_depth: int = 10) -> None:
        """Initialize BoundarySentinel.

        Args:
            scan_depth: Maximum number of rows below table boundary to inspect for clearance.
        """
        if scan_depth < 1:
            raise ValueError(f"scan_depth must be >= 1, got {scan_depth}")
        self.scan_depth = scan_depth

    def evaluate_margin(
        self,
        region: SpatialTableRegion,
        row_stream: Union[Iterator[dict[str, Any]], Iterator[list[dict[str, Any]]], list[dict[str, Any]]],
        *,
        facts: Optional[DeclaredOpenXmlFacts] = None,
        other_regions: Optional[list[SpatialTableRegion]] = None,
    ) -> MarginClearance:
        """Evaluate ADR-005 append margin clearance for a detected table region.

        Args:
            region: SpatialTableRegion to evaluate.
            row_stream: Stream or list of row records containing row indices and cells.
            facts: Optional DeclaredOpenXmlFacts from M03 inspection (e.g. hidden rows).
            other_regions: Optional list of other detected regions on the same worksheet.

        Returns:
            MarginClearance object specifying spare rows, collisions, and append safety.
        """
        box = region.bounding_box
        bottom_row = box.max_row
        min_col, max_col = box.min_col, box.max_col
        scan_max_row = bottom_row + self.scan_depth

        # Buffer rows in the boundary scan zone [bottom_row + 1 .. scan_max_row]
        boundary_rows: dict[int, dict[int, tuple[Any, Optional[str]]]] = {}

        def _process_row(r_dict: dict[str, Any]) -> None:
            r_idx = r_dict.get("row")
            if r_idx is None or r_idx <= bottom_row or r_idx > scan_max_row:
                return
            cells_map: dict[int, tuple[Any, Optional[str]]] = {}
            for c in r_dict.get("cells", []):
                c_idx = c.get("col")
                if c_idx is not None and min_col <= c_idx <= max_col:
                    cells_map[c_idx] = (c.get("value"), c.get("formula"))
            if cells_map:
                boundary_rows[r_idx] = cells_map

        if isinstance(row_stream, list):
            for item in row_stream:
                if isinstance(item, list):
                    for r in item:
                        _process_row(r)
                else:
                    _process_row(item)
        else:
            for item in row_stream:
                if isinstance(item, list):
                    for r in item:
                        _process_row(r)
                else:
                    _process_row(item)

        # Check for adjacent regions immediately below
        region_collision_row: Optional[int] = None
        if other_regions:
            for other in other_regions:
                if other.region_id == region.region_id:
                    continue
                o_box = other.bounding_box
                # Check if other region is below and overlaps column span
                if o_box.min_row > bottom_row and o_box.min_row <= scan_max_row:
                    col_overlap = max(min_col, o_box.min_col) <= min(max_col, o_box.max_col)
                    if col_overlap:
                        if region_collision_row is None or o_box.min_row < region_collision_row:
                            region_collision_row = o_box.min_row

        # Calculate spare rows below
        spare_rows = 0
        first_collision_row: Optional[int] = None
        adjacent_formulas: list[str] = []
        has_trailing_formulas = False
        colliding_rows: list[int] = []

        for r in range(bottom_row + 1, scan_max_row + 1):
            if region_collision_row is not None and r == region_collision_row:
                first_collision_row = r
                colliding_rows.append(r)
                break

            if r in boundary_rows:
                first_collision_row = r
                colliding_rows.append(r)
                # Check for formulas in this colliding row
                for col_idx, (val, formula) in boundary_rows[r].items():
                    if formula:
                        adjacent_formulas.append(formula)
                        if _is_summary_or_referencing_formula(formula, box):
                            has_trailing_formulas = True
                break
            else:
                spare_rows += 1

        # Check zero-space collision: occurs when row bottom_row + 1 is populated or starts another table
        has_zero_space_collision = (spare_rows == 0)

        # Evaluate safety under ADR-005:
        # Declared ListObjects have native table expansion mechanics managed by Excel -> safe
        # Inferred / Ordinary ranges: zero-space collision or trailing formulas make append unsafe
        evidence_list: list[SpatialEvidence] = []
        safe_for_append = True
        collision_reason: Optional[str] = None

        if region.is_declared:
            safe_for_append = True
            collision_reason = None
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.BOUNDARY_SAFE_CLEARANCE,
                    description=f"Declared ListObject '{region.declared_name}': native table expansion enabled.",
                    heuristic_score=1.0,
                    provenance="excel_intel.spatial.boundary_sentinel",
                )
            )
        else:
            # Check if any colliding row is hidden in worksheet
            hidden_note = ""
            if facts and facts.hidden_rows and first_collision_row:
                for hr in facts.hidden_rows:
                    hr_start = getattr(hr, "start", getattr(hr, "start_index", 0))
                    hr_end = getattr(hr, "end", getattr(hr, "end_index", 0))
                    if hr_start <= first_collision_row <= hr_end:
                        hidden_note = f" (Note: Row {first_collision_row} is hidden in worksheet view)"
                        break

            if has_zero_space_collision:
                safe_for_append = False
                collision_reason = (
                    f"ERR_BOUNDARY_COLLISION: ADR-005 Collision: Ordinary range has 0 spare rows below row {bottom_row}. "
                    f"Occupied row {first_collision_row} prevents automated append without row shifting.{hidden_note}"
                )
                evidence_list.append(
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.BOUNDARY_COLLISION_DETECTED,
                        description=collision_reason,
                        heuristic_score=1.0,
                        provenance="excel_intel.spatial.boundary_sentinel",
                        coordinates=BoundingBox(
                            min_row=bottom_row + 1,
                            max_row=bottom_row + 1,
                            min_col=min_col,
                            max_col=max_col,
                        ),
                    )
                )
            if has_trailing_formulas:
                safe_for_append = False
                formula_reason = (
                    f"ADR-005 Proximity Warning: Trailing formulas detected at row {first_collision_row} "
                    f"({', '.join(adjacent_formulas[:3])}). Append requires conversion to ListObject.{hidden_note}"
                )
                if collision_reason:
                    collision_reason += f" {formula_reason}"
                else:
                    collision_reason = formula_reason
                evidence_list.append(
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.TRAILING_FORMULA_COLLISION,
                        description=formula_reason,
                        heuristic_score=1.0,
                        provenance="excel_intel.spatial.boundary_sentinel",
                        coordinates=BoundingBox(
                            min_row=first_collision_row or bottom_row + 1,
                            max_row=first_collision_row or bottom_row + 1,
                            min_col=min_col,
                            max_col=max_col,
                        ),
                    )
                )
            if not has_zero_space_collision and not has_trailing_formulas:
                safe_for_append = True
                collision_reason = None
                evidence_list.append(
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.BOUNDARY_SAFE_CLEARANCE,
                        description=f"Clearance verified: {spare_rows} spare rows below row {bottom_row}.",
                        heuristic_score=0.95,
                        provenance="excel_intel.spatial.boundary_sentinel",
                    )
                )

        return MarginClearance(
            spare_rows_below=spare_rows,
            has_zero_space_collision=has_zero_space_collision,
            has_trailing_formulas=has_trailing_formulas,
            adjacent_formulas=adjacent_formulas,
            colliding_row_indices=colliding_rows,
            safe_for_append=safe_for_append,
            collision_reason=collision_reason,
            evidence=evidence_list,
        )

    def attach_margin_clearance(
        self,
        region: SpatialTableRegion,
        row_stream: Union[Iterator[dict[str, Any]], Iterator[list[dict[str, Any]]], list[dict[str, Any]]],
        *,
        facts: Optional[DeclaredOpenXmlFacts] = None,
        other_regions: Optional[list[SpatialTableRegion]] = None,
    ) -> SpatialTableRegion:
        """Evaluate margin clearance and return updated SpatialTableRegion with `margin` populated."""
        clearance = self.evaluate_margin(region, row_stream, facts=facts, other_regions=other_regions)
        updated_evidence = list(region.evidence) + clearance.evidence
        return region.model_copy(
            update={
                "margin": clearance,
                "evidence": updated_evidence,
            }
        )
