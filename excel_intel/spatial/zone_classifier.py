"""Semantic Zone Classifier for Spatial Table Regions (M04).

Decomposes spatial regions into discrete semantic zones:
- TITLE: Top title banners, sheet headings, or metadata key-value rows.
- HEADER: Single-row or multi-row hierarchical column headers.
- BODY: Primary tabular data rows, including interleaved section subheaders.
- SUMMARY: Intermediate category subtotals or aggregation rows.
- TOTALS: Final grand total row(s) at table bottom.
- FOOTNOTES: Trailing disclaimers, explanatory notes, or source citations.
- UNKNOWN: Unclassified non-empty cells within the bounding box.

Maintains strict bounded memory complexity O(W * C) and immutable Pydantic contracts.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

from excel_intel.inspection.models import BoundingBox, DeclaredMergeCell, DeclaredListObject
from excel_intel.spatial.models import (
    HeaderResolutionReport,
    SemanticZone,
    SemanticZoneType,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialTableRegion,
)

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader


_SUMMARY_KEYWORDS = {
    "total",
    "totals",
    "subtotal",
    "subtotals",
    "sum",
    "average",
    "avg",
    "count",
    "grand total",
    "overall total",
}

_GRAND_TOTAL_KEYWORDS = {
    "grand total",
    "overall total",
    "total",
    "totals",
    "final total",
}

_SUBTOTAL_KEYWORDS = {
    "subtotal",
    "subtotals",
    "category total",
    "section total",
    "group total",
}

_FOOTNOTE_PATTERNS = [
    re.compile(r"^\s*[*†‡#]+"),
    re.compile(r"^\s*note[s]?\s*[:\-]", re.IGNORECASE),
    re.compile(r"^\s*source\s*[:\-]", re.IGNORECASE),
    re.compile(r"^\s*disclaimer\s*[:\-]", re.IGNORECASE),
    re.compile(r"^\s*confidential", re.IGNORECASE),
    re.compile(r"^\s*see\s+page\b", re.IGNORECASE),
]


def _is_summary_formula(formula: Optional[str]) -> bool:
    """Return True if formula contains aggregation or summary functions."""
    if not formula:
        return False
    f_upper = formula.upper().strip()
    return any(
        func in f_upper
        for func in ("SUM(", "AVERAGE(", "COUNT(", "COUNTA(", "SUBTOTAL(", "AGGREGATE(")
    )


def _is_subtotal_formula(formula: Optional[str]) -> bool:
    """Return True if formula specifically invokes SUBTOTAL or AGGREGATE."""
    if not formula:
        return False
    f_upper = formula.upper().strip()
    return "SUBTOTAL(" in f_upper or "AGGREGATE(" in f_upper


def _is_footnote_text(val: Any) -> bool:
    """Return True if cell text matches standard footnote or citation patterns."""
    if not isinstance(val, str):
        return False
    v = val.strip()
    if not v:
        return False
    return any(pat.search(v) for pat in _FOOTNOTE_PATTERNS)


class ZoneClassifier:
    """Evidence-driven intra-region semantic zone classifier."""

    def __init__(
        self,
        *,
        footnote_max_cells_ratio: float = 0.50,
        title_banner_max_width_ratio: float = 0.50,
    ) -> None:
        """Initialize ZoneClassifier.

        Args:
            footnote_max_cells_ratio: Max populated column ratio for trailing footnote rows.
            title_banner_max_width_ratio: Max populated column ratio for top title banner rows.
        """
        self.footnote_max_cells_ratio = footnote_max_cells_ratio
        self.title_banner_max_width_ratio = title_banner_max_width_ratio

    def classify_region(
        self,
        region: SpatialTableRegion,
        row_stream: Union[Iterator[dict[str, Any]], Iterator[list[dict[str, Any]]], list[dict[str, Any]]],
        *,
        header_report: Optional[HeaderResolutionReport] = None,
        merge_cells: Optional[list[DeclaredMergeCell]] = None,
        list_objects: Optional[list[DeclaredListObject]] = None,
    ) -> SpatialTableRegion:
        """Classify a spatial table region into discrete semantic zones.

        Args:
            region: Detected SpatialTableRegion.
            row_stream: Stream or list of row records with cell dictionaries.
            header_report: Optional resolved header report from HeaderResolver.
            merge_cells: Optional M03 DeclaredMergeCell facts.
            list_objects: Optional M03 DeclaredListObject facts.

        Returns:
            Updated SpatialTableRegion populated with `zones`, `zone_list`, `subheaders`, and evidence.
        """
        box = region.bounding_box
        min_row, max_row = box.min_row, box.max_row
        min_col, max_col = box.min_col, box.max_col
        total_cols = box.col_count

        # 1. Buffer region rows into in-memory row map
        # Only rows within the region's bounding box are buffered
        grid_rows: dict[int, dict[int, tuple[Any, Optional[str]]]] = {}

        def _process_row(r_dict: dict[str, Any]) -> None:
            r_idx = r_dict.get("row")
            if r_idx is None or r_idx < min_row or r_idx > max_row:
                return
            cells_map: dict[int, tuple[Any, Optional[str]]] = {}
            for c in r_dict.get("cells", []):
                c_idx = c.get("col")
                if c_idx is not None and min_col <= c_idx <= max_col:
                    cells_map[c_idx] = (c.get("value"), c.get("formula"))
            if cells_map:
                grid_rows[r_idx] = cells_map

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

        # 2. Determine Header Row Bounds from HeaderResolutionReport or Region
        hdr_start: Optional[int] = None
        hdr_end: Optional[int] = None

        if header_report is not None and header_report.header_row_start is not None:
            hdr_start = header_report.header_row_start
            hdr_end = header_report.header_row_end or hdr_start
        elif region.header_row is not None:
            hdr_start = region.header_row
            hdr_end = region.header_row
        elif region.is_declared and list_objects:
            for lo in list_objects:
                if lo.box.intersects(box) and lo.header_row_count > 0:
                    hdr_start = lo.box.min_row
                    hdr_end = lo.box.min_row + lo.header_row_count - 1
                    break

        # 3. Detect Title Banner Rows
        title_rows: list[int] = []
        if hdr_start is not None and hdr_start > min_row:
            for r in range(min_row, hdr_start):
                if r in grid_rows:
                    title_rows.append(r)
        elif hdr_start is None:
            # Check if row min_row is a title banner
            if min_row in grid_rows and min_row + 1 <= max_row:
                cells_1 = grid_rows[min_row]
                text_count = sum(1 for v, _ in cells_1.values() if isinstance(v, str) and str(v).strip())
                num_count = sum(1 for v, _ in cells_1.values() if isinstance(v, (int, float)))
                if num_count == 0 and 0 < text_count <= max(1, int(total_cols * self.title_banner_max_width_ratio)):
                    title_rows.append(min_row)

        # 4. Scan Bottom Rows for Footnotes, Totals, and Summary Rows
        footnote_rows: list[int] = []
        totals_rows: list[int] = []
        summary_rows: list[int] = []

        # Find last populated row in grid_rows
        populated_row_indices = sorted(grid_rows.keys())
        if not populated_row_indices:
            # Empty region
            return region

        # Scan upwards from bottom for Footnotes
        curr_idx = len(populated_row_indices) - 1
        while curr_idx >= 0:
            r = populated_row_indices[curr_idx]
            if hdr_end is not None and r <= hdr_end:
                break
            cells = grid_rows[r]
            vals = [v for v, _ in cells.values() if v is not None and str(v).strip()]
            forms = [f for _, f in cells.values() if f is not None]

            # Check explicit footnote pattern
            has_fn_pattern = any(_is_footnote_text(v) for v in vals)
            # Check sparse trailing text note
            is_trailing_note = (
                len(vals) <= max(1, int(total_cols * self.footnote_max_cells_ratio))
                and len(forms) == 0
                and all(isinstance(v, str) for v in vals)
                and not any(str(v).lower().strip() in _SUMMARY_KEYWORDS for v in vals)
            )

            if has_fn_pattern or (is_trailing_note and (not totals_rows and not summary_rows)):
                footnote_rows.append(r)
                curr_idx -= 1
            else:
                break

        # Scan upwards from before footnotes for Totals and Summary rows
        while curr_idx >= 0:
            r = populated_row_indices[curr_idx]
            if hdr_end is not None and r <= hdr_end:
                break
            cells = grid_rows[r]
            vals = [v for v, _ in cells.values() if v is not None]
            forms = [f for _, f in cells.values() if f is not None]

            has_summary_f = any(_is_summary_formula(f) for f in forms)
            has_subtotal_f = any(_is_subtotal_formula(f) for f in forms)
            text_vals = [str(v).lower().strip() for v in vals if isinstance(v, str)]

            is_grand_total = any(k in text_vals for k in _GRAND_TOTAL_KEYWORDS)
            is_subtotal = any(k in text_vals for k in _SUBTOTAL_KEYWORDS)

            if is_grand_total or (has_summary_f and not totals_rows and not summary_rows and not is_subtotal):
                totals_rows.append(r)
                curr_idx -= 1
            elif is_subtotal or has_subtotal_f or (has_summary_f and (totals_rows or summary_rows)):
                summary_rows.append(r)
                curr_idx -= 1
            else:
                break

        # Check for intermediate subheaders / summary rows within the data body
        data_body_rows: list[int] = []
        interleaved_subheaders: list[dict[str, Any]] = []

        special_rows = set(title_rows) | set(footnote_rows) | set(totals_rows) | set(summary_rows)
        if hdr_start is not None and hdr_end is not None:
            special_rows.update(range(hdr_start, hdr_end + 1))

        # Check remaining rows for Data Body and Interleaved Subheaders
        for r in populated_row_indices:
            if r in special_rows:
                continue
            cells = grid_rows[r]
            vals = [v for v, _ in cells.values() if v is not None and str(v).strip()]
            forms = [f for _, f in cells.values() if f is not None]

            # Intermediate subtotal / summary row in the middle of body
            has_sub_f = any(_is_subtotal_formula(f) for f in forms)
            has_sum_f = any(_is_summary_formula(f) for f in forms)
            text_vals = [str(v).lower().strip() for v in vals if isinstance(v, str)]
            if has_sub_f or any(k in text_vals for k in _SUBTOTAL_KEYWORDS):
                summary_rows.append(r)
                continue

            # Check if this row is an interleaved section subheader:
            # - No numeric cells
            # - Has text label(s)
            # - Spans across columns or single category label
            num_cells = sum(1 for v in vals if isinstance(v, (int, float)))
            if num_cells == 0 and len(vals) > 0 and all(isinstance(v, str) for v in vals):
                # If row r is followed by subsequent data rows with numbers, it's an interleaved subheader
                has_subsequent_data = any(
                    any(isinstance(v2, (int, float)) for v2, _ in grid_rows[r2].values())
                    for r2 in populated_row_indices
                    if r2 > r and r2 not in special_rows
                )
                if has_subsequent_data:
                    subhdr_label = " | ".join(str(v).strip() for v in vals)
                    interleaved_subheaders.append({
                        "row": r,
                        "label": subhdr_label,
                        "col_count": len(vals),
                    })
                    # Subheaders remain structurally inside the body zone
                    data_body_rows.append(r)
                    continue

            data_body_rows.append(r)

        # 5. Build SemanticZone objects
        zones: dict[SemanticZoneType, SemanticZone] = {}
        zone_list: list[SemanticZone] = []
        new_evidence: list[SpatialEvidence] = list(region.evidence)

        def _make_zone(
            ztype: SemanticZoneType,
            rows: list[int],
            desc: str,
            ev_type: SpatialEvidenceType,
        ) -> None:
            if not rows:
                return
            z_min_r = min(rows)
            z_max_r = max(rows)
            z_box = BoundingBox(
                min_row=z_min_r,
                max_row=z_max_r,
                min_col=min_col,
                max_col=max_col,
            )
            pop_cells = sum(len(grid_rows.get(r, {})) for r in range(z_min_r, z_max_r + 1))
            ev = SpatialEvidence(
                evidence_type=ev_type,
                description=desc,
                heuristic_score=0.95,
                provenance="excel_intel.spatial.zone_classifier",
                coordinates=z_box,
            )
            zone_obj = SemanticZone(
                zone_type=ztype,
                bounding_box=z_box,
                row_count=z_max_r - z_min_r + 1,
                cell_count=(z_max_r - z_min_r + 1) * total_cols,
                populated_cell_count=pop_cells,
                heuristic_confidence=0.95,
                evidence=[ev],
                details=desc,
            )
            zones[ztype] = zone_obj
            zone_list.append(zone_obj)
            new_evidence.append(ev)

        # Title
        if title_rows:
            _make_zone(
                SemanticZoneType.TITLE,
                title_rows,
                f"Title banner rows {min(title_rows)}..{max(title_rows)}",
                SpatialEvidenceType.ZONE_TITLE_DETECTED,
            )

        # Header
        if hdr_start is not None and hdr_end is not None:
            hdr_rows = list(range(hdr_start, hdr_end + 1))
            _make_zone(
                SemanticZoneType.HEADER,
                hdr_rows,
                f"Column header rows {hdr_start}..{hdr_end}",
                SpatialEvidenceType.ZONE_HEADER_DETECTED,
            )

        # Body
        if data_body_rows:
            _make_zone(
                SemanticZoneType.BODY,
                data_body_rows,
                f"Data body rows {min(data_body_rows)}..{max(data_body_rows)}",
                SpatialEvidenceType.ZONE_BODY_DETECTED,
            )

        # Summary
        if summary_rows:
            _make_zone(
                SemanticZoneType.SUMMARY,
                summary_rows,
                f"Intermediate summary/subtotal rows: {sorted(summary_rows)}",
                SpatialEvidenceType.ZONE_SUMMARY_DETECTED,
            )

        # Totals
        if totals_rows:
            _make_zone(
                SemanticZoneType.TOTALS,
                totals_rows,
                f"Final grand totals rows {min(totals_rows)}..{max(totals_rows)}",
                SpatialEvidenceType.ZONE_TOTALS_DETECTED,
            )

        # Footnotes
        if footnote_rows:
            _make_zone(
                SemanticZoneType.FOOTNOTES,
                footnote_rows,
                f"Trailing footnotes/citations rows {min(footnote_rows)}..{max(footnote_rows)}",
                SpatialEvidenceType.ZONE_FOOTNOTES_DETECTED,
            )

        # Record interleaved subheader evidence
        for sh in interleaved_subheaders:
            sh_box = BoundingBox(
                min_row=sh["row"],
                max_row=sh["row"],
                min_col=min_col,
                max_col=max_col,
            )
            new_evidence.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.INTERLEAVED_SUBHEADER,
                    description=f"Interleaved subheader row {sh['row']}: '{sh['label']}'",
                    heuristic_score=0.90,
                    provenance="excel_intel.spatial.zone_classifier",
                    coordinates=sh_box,
                )
            )

        # Sort zone_list by min_row for clean top-down spatial ordering
        zone_list.sort(key=lambda z: z.bounding_box.min_row)

        return region.model_copy(
            update={
                "zones": zones,
                "zone_list": zone_list,
                "subheaders": interleaved_subheaders,
                "evidence": new_evidence,
            }
        )
