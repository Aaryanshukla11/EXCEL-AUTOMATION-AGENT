"""Hierarchical Header Resolution Engine (M04).

Identifies and resolves single-row and multi-row hierarchical header structures
inside spatial regions. Supports stacked headers, merged-cell overlays, compound
header names, and duplicate disambiguation with strictly bounded lookahead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

from excel_intel.inspection.models import BoundingBox, DeclaredMergeCell, DeclaredListObject, DeclaredOpenXmlFacts
from excel_intel.spatial.models import (
    HeaderHierarchyLevel,
    HeaderResolutionReport,
    HeaderResolutionStatus,
    ResolvedHeaderColumn,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialTableRegion,
)

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader


def _is_numeric(val: Any) -> bool:
    """Return True if val represents a numeric value (int, float) or numeric string."""
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        v = val.strip().replace(",", "")
        if not v:
            return False
        try:
            float(v)
            return True
        except ValueError:
            return False
    return False


def _is_summary_formula(formula: Optional[str]) -> bool:
    """Return True if formula contains common aggregation/summary functions."""
    if not formula:
        return False
    f_upper = formula.upper().strip()
    return any(
        func in f_upper
        for func in ("SUM(", "AVERAGE(", "COUNT(", "COUNTA(", "SUBTOTAL(", "AGGREGATE(")
    )


class HeaderResolver:
    """Generic, evidence-driven hierarchical header resolution engine."""

    def __init__(
        self,
        *,
        delimiter: str = " -> ",
        max_header_scan_rows: int = 10,
        numeric_threshold_ratio: float = 0.60,
        title_banner_max_width_ratio: float = 0.50,
    ) -> None:
        """Initialize HeaderResolver with configurable heuristics.

        Args:
            delimiter: String delimiter used to join multi-level compound headers (default ' -> ').
            max_header_scan_rows: Maximum rows scanned from top of region (lookahead bound).
            numeric_threshold_ratio: Ratio of numeric cells in a row to classify it as data body.
            title_banner_max_width_ratio: Width ratio below which single-text rows are excluded as title banners.
        """
        if max_header_scan_rows < 1:
            raise ValueError(f"max_header_scan_rows must be >= 1, got {max_header_scan_rows}")

        self.delimiter = delimiter
        self.max_scan_rows = max_header_scan_rows
        self.numeric_threshold = numeric_threshold_ratio
        self.title_banner_max_width_ratio = title_banner_max_width_ratio

    def resolve_region(
        self,
        region: SpatialTableRegion,
        row_stream: Union[Iterator[dict[str, Any]], Iterator[list[dict[str, Any]]], list[dict[str, Any]]],
        *,
        merge_cells: Optional[list[DeclaredMergeCell]] = None,
        list_objects: Optional[list[DeclaredListObject]] = None,
    ) -> HeaderResolutionReport:
        """Resolve header hierarchy for a candidate spatial table region.

        Args:
            region: SpatialTableRegion identified by grid segmentation.
            row_stream: Stream yielding row records or chunks of row records.
            merge_cells: Optional list of declared OpenXML merge cells from M03.
            list_objects: Optional list of declared OpenXML ListObjects from M03.

        Returns:
            HeaderResolutionReport detailing resolved columns, hierarchy, evidence, and confidence.
        """
        box = region.bounding_box
        sheet_name = region.sheet_name
        evidence_list: list[SpatialEvidence] = []

        # 1. Check for Declared OpenXML Table (ListObject)
        if list_objects:
            for lo in list_objects:
                if lo.box == box or (lo.box.min_row == box.min_row and lo.box.min_col == box.min_col):
                    if lo.column_names:
                        cols: list[ResolvedHeaderColumn] = []
                        for i, name in enumerate(lo.column_names, start=lo.box.min_col):
                            coord = f"{box.min_row}_{i}"
                            cols.append(
                                ResolvedHeaderColumn(
                                    col_index=i,
                                    resolved_name=name,
                                    raw_name=name,
                                    hierarchy_levels=[
                                        HeaderHierarchyLevel(
                                            row_index=lo.box.min_row,
                                            col_index=i,
                                            raw_value=name,
                                            is_merged=False,
                                        )
                                    ],
                                    depth=1,
                                    source_coordinate=coord,
                                )
                            )
                        evidence_list.append(
                            SpatialEvidence(
                                evidence_type=SpatialEvidenceType.DECLARED_OPENXML,
                                description=f"Resolved headers directly from OpenXML ListObject '{lo.name}'",
                                heuristic_score=1.0,
                                provenance="M04:HeaderResolver:openxml_list_object",
                                coordinates=lo.box,
                            )
                        )
                        return HeaderResolutionReport(
                            region_id=region.region_id,
                            sheet_name=sheet_name,
                            status=HeaderResolutionStatus.HIGH_CONFIDENCE,
                            header_row_start=lo.box.min_row,
                            header_row_end=lo.box.min_row + max(1, lo.header_row_count) - 1,
                            header_row_count=max(1, lo.header_row_count),
                            columns=cols,
                            heuristic_confidence=1.0,
                            evidence=evidence_list,
                            delimiter_used=self.delimiter,
                        )

        # 2. Buffer Bounded Top Rows (Lookahead constraint)
        max_scan_r = min(box.max_row, box.min_row + self.max_scan_rows - 1)
        grid_rows: dict[int, dict[int, Any]] = {}
        formula_rows: dict[int, dict[int, str]] = {}

        def flatten() -> Iterator[dict[str, Any]]:
            for item in row_stream:
                if isinstance(item, list):
                    for r in item:
                        yield r
                elif isinstance(item, dict):
                    yield item

        for row_rec in flatten():
            r = row_rec.get("row")
            if r is None or r < box.min_row:
                continue
            if r > max_scan_r:
                break

            cells = row_rec.get("cells", [])
            row_map: dict[int, Any] = {}
            f_map: dict[int, str] = {}
            for c in cells:
                c_idx = c.get("col")
                if c_idx is not None and box.min_col <= c_idx <= box.max_col:
                    val = c.get("value")
                    row_map[c_idx] = val
                    formula = c.get("formula")
                    if formula:
                        f_map[c_idx] = formula

            grid_rows[r] = row_map
            if f_map:
                formula_rows[r] = f_map

        if not grid_rows:
            return HeaderResolutionReport(
                region_id=region.region_id,
                sheet_name=sheet_name,
                status=HeaderResolutionStatus.NO_HEADER_DETECTED,
                heuristic_confidence=0.90,
                evidence=[
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.NO_HEADER_DETECTED,
                        description="No rows available in region header scan range",
                        heuristic_score=0.90,
                        provenance="M04:HeaderResolver:empty_scan",
                        coordinates=box,
                    )
                ],
                delimiter_used=self.delimiter,
            )

        sorted_rows = sorted(grid_rows.keys())
        current_start_idx = 0

        # 3. Title Banner Detection & Exclusion
        first_r = sorted_rows[0]
        first_row_cells = grid_rows[first_r]
        non_empty_first = [c for c, val in first_row_cells.items() if val is not None and str(val).strip() != ""]

        is_title_banner = False
        if len(sorted_rows) > 1 and len(non_empty_first) == 1 and box.col_count >= 2:
            next_r = sorted_rows[1]
            next_row_cells = grid_rows[next_r]
            non_empty_next = [c for c, val in next_row_cells.items() if val is not None and str(val).strip() != ""]
            if len(non_empty_next) >= 2 or (next_r - first_r > 1):
                is_title_banner = True
        elif len(sorted_rows) > 1 and merge_cells:
            # Check wide merge banner spanning all columns on first row
            for mc in merge_cells:
                if mc.box.min_row == first_r and mc.box.min_col == box.min_col and mc.box.max_col == box.max_col:
                    is_title_banner = True
                    break

        if is_title_banner:
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.TITLE_BANNER_EXCLUDED,
                    description=f"Excluded row {first_r} as title banner (text: '{first_row_cells.get(non_empty_first[0], '')}')",
                    heuristic_score=0.95,
                    provenance="M04:HeaderResolver:title_banner_filter",
                    coordinates=BoundingBox(min_row=first_r, max_row=first_r, min_col=box.min_col, max_col=box.max_col),
                )
            )
            current_start_idx = 1

        if current_start_idx >= len(sorted_rows):
            return HeaderResolutionReport(
                region_id=region.region_id,
                sheet_name=sheet_name,
                status=HeaderResolutionStatus.NO_HEADER_DETECTED,
                heuristic_confidence=0.85,
                evidence=evidence_list,
                delimiter_used=self.delimiter,
            )

        # 4. Type Entropy & Label Transition Detection
        candidate_header_rows: list[int] = []
        is_ambiguous = False
        ambiguity_reasons: list[str] = []

        for r in sorted_rows[current_start_idx:]:
            row_map = grid_rows[r]
            f_map = formula_rows.get(r, {})

            total_non_empty = 0
            num_count = 0
            text_count = 0

            for c in range(box.min_col, box.max_col + 1):
                val = row_map.get(c)
                if val is not None and str(val).strip() != "":
                    total_non_empty += 1
                    if _is_numeric(val):
                        num_count += 1
                    else:
                        text_count += 1

            if total_non_empty == 0:
                # Blank row breaks header continuity
                if candidate_header_rows:
                    break
                continue

            # Check for summary formulas on numeric rows
            has_summary_f = any(_is_summary_formula(f) for f in f_map.values())
            if has_summary_f and num_count > 0:
                evidence_list.append(
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.SUMMARY_ROW_EXCLUDED,
                        description=f"Row {r} contains numeric summary formula; excluded from headers",
                        heuristic_score=0.95,
                        provenance="M04:HeaderResolver:summary_filter",
                        coordinates=BoundingBox(min_row=r, max_row=r, min_col=box.min_col, max_col=box.max_col),
                    )
                )
                break

            if not candidate_header_rows:
                if text_count > 0 and num_count > 0:
                    is_ambiguous = True
                    ambiguity_reasons.append(
                        f"First row {r} has mixed text ({text_count}) and numeric ({num_count}) values"
                    )
                    candidate_header_rows.append(r)
                    break
                elif text_count > 0 and num_count == 0:
                    candidate_header_rows.append(r)
                else:
                    # Pure data row
                    break
            else:
                # Subsequent row: if numeric cells appear, data body has begun
                if num_count > 0:
                    break
                elif text_count > 0:
                    candidate_header_rows.append(r)
                else:
                    break

        if not candidate_header_rows:
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.NO_HEADER_DETECTED,
                    description="No text-dominant header rows found; region begins with data",
                    heuristic_score=0.90,
                    provenance="M04:HeaderResolver:type_transition",
                    coordinates=box,
                )
            )
            return HeaderResolutionReport(
                region_id=region.region_id,
                sheet_name=sheet_name,
                status=HeaderResolutionStatus.NO_HEADER_DETECTED,
                heuristic_confidence=0.90,
                evidence=evidence_list,
                delimiter_used=self.delimiter,
            )

        # Check if lookahead resource ceiling was reached
        is_resource_truncated = False
        truncation_detail: Optional[str] = None
        if len(candidate_header_rows) == self.max_scan_rows and box.max_row > max_scan_r:
            is_resource_truncated = True
            truncation_detail = (
                f"Header scan reached lookahead limit of {self.max_scan_rows} rows before data transition"
            )
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.HEADER_RESOURCE_LIMIT,
                    description=truncation_detail,
                    heuristic_score=0.50,
                    provenance="M04:HeaderResolver:lookahead_ceiling",
                    coordinates=box,
                )
            )

        header_start_row = candidate_header_rows[0]
        header_end_row = candidate_header_rows[-1]
        header_row_count = len(candidate_header_rows)

        # 5. Overlay Declared Merged Cells
        # grid_overlay[r][c] = (value, is_merged, merge_ref)
        grid_overlay: dict[int, dict[int, tuple[str, bool, Optional[str]]]] = {}
        for r in candidate_header_rows:
            grid_overlay[r] = {}
            for c in range(box.min_col, box.max_col + 1):
                val = grid_rows[r].get(c)
                val_str = str(val).strip() if val is not None else ""
                grid_overlay[r][c] = (val_str, False, None)

        if merge_cells:
            for mc in merge_cells:
                m_box = mc.box
                # Check intersection with candidate headers
                r_min = max(header_start_row, m_box.min_row)
                r_max = min(header_end_row, m_box.max_row)
                c_min = max(box.min_col, m_box.min_col)
                c_max = min(box.max_col, m_box.max_col)

                if r_min <= r_max and c_min <= c_max:
                    # Anchor value is at top-left
                    anchor_val = grid_rows.get(m_box.min_row, {}).get(m_box.min_col)
                    anchor_str = str(anchor_val).strip() if anchor_val is not None else ""

                    evidence_list.append(
                        SpatialEvidence(
                            evidence_type=SpatialEvidenceType.MERGED_HEADER_OVERLAY,
                            description=f"Merged range {mc.ref} overlays header cells with anchor '{anchor_str}'",
                            heuristic_score=0.95,
                            provenance="M04:HeaderResolver:merge_cell_overlay",
                            coordinates=mc.box,
                        )
                    )

                    for mr in range(r_min, r_max + 1):
                        if mr not in grid_overlay:
                            continue
                        for mc_idx in range(c_min, c_max + 1):
                            curr_val, _, _ = grid_overlay[mr][mc_idx]
                            # If empty or part of merged block, propagate anchor
                            if not curr_val or (mr, mc_idx) != (m_box.min_row, m_box.min_col):
                                grid_overlay[mr][mc_idx] = (anchor_str, True, mc.ref)

        # 6. Multi-Row Hierarchical Header Resolution
        raw_columns: list[ResolvedHeaderColumn] = []

        for c in range(box.min_col, box.max_col + 1):
            levels: list[HeaderHierarchyLevel] = []
            level_strings: list[str] = []

            for r in candidate_header_rows:
                val_str, is_m, m_ref = grid_overlay[r][c]
                levels.append(
                    HeaderHierarchyLevel(
                        row_index=r,
                        col_index=c,
                        raw_value=val_str,
                        is_merged=is_m,
                        merge_range_ref=m_ref,
                    )
                )
                if val_str:
                    # Deduplicate vertically identical consecutive merged labels
                    if not level_strings or val_str != level_strings[-1] or not is_m:
                        level_strings.append(val_str)

            leaf_val = levels[-1].raw_value if levels else ""
            if not level_strings:
                # Completely blank header column: retain empty without fabricating
                resolved_name = ""
                raw_name = ""
            else:
                resolved_name = self.delimiter.join(level_strings)
                raw_name = level_strings[-1]

            coord = f"{candidate_header_rows[-1]}_{c}"
            raw_columns.append(
                ResolvedHeaderColumn(
                    col_index=c,
                    resolved_name=resolved_name,
                    raw_name=raw_name,
                    hierarchy_levels=levels,
                    depth=max(1, len(level_strings)),
                    source_coordinate=coord,
                )
            )

        # 7. Duplicate Label Disambiguation
        name_counts: dict[str, int] = {}
        for col in raw_columns:
            if col.resolved_name:
                name_counts[col.resolved_name] = name_counts.get(col.resolved_name, 0) + 1

        final_columns: list[ResolvedHeaderColumn] = []
        name_seen: dict[str, int] = {}

        for col in raw_columns:
            if col.resolved_name and name_counts[col.resolved_name] > 1:
                name_seen[col.resolved_name] = name_seen.get(col.resolved_name, 0) + 1
                suffix_idx = name_seen[col.resolved_name]
                disambiguated = f"{col.resolved_name}_{suffix_idx}"
                col_obj = ResolvedHeaderColumn(
                    col_index=col.col_index,
                    resolved_name=col.resolved_name,
                    raw_name=col.raw_name,
                    hierarchy_levels=col.hierarchy_levels,
                    depth=col.depth,
                    is_duplicate=True,
                    disambiguated_name=disambiguated,
                    source_coordinate=col.source_coordinate,
                )
            else:
                col_obj = col
            final_columns.append(col_obj)

        # 8. Ambiguity & Confidence Classification
        if header_row_count == 1:
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.SINGLE_ROW_HEADER,
                    description=f"Single-row column header identified at row {header_start_row}",
                    heuristic_score=0.95 if not is_ambiguous else 0.70,
                    provenance="M04:HeaderResolver:single_row_detection",
                    coordinates=BoundingBox(
                        min_row=header_start_row,
                        max_row=header_start_row,
                        min_col=box.min_col,
                        max_col=box.max_col,
                    ),
                )
            )
        else:
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.HIERARCHICAL_STACKED_HEADER,
                    description=(
                        f"Multi-row hierarchical header spanning {header_row_count} rows "
                        f"({header_start_row}..{header_end_row}) with delimiter '{self.delimiter}'"
                    ),
                    heuristic_score=0.92 if not is_ambiguous else 0.65,
                    provenance="M04:HeaderResolver:stacked_hierarchy",
                    coordinates=BoundingBox(
                        min_row=header_start_row,
                        max_row=header_end_row,
                        min_col=box.min_col,
                        max_col=box.max_col,
                    ),
                )
            )

        if is_resource_truncated:
            status = HeaderResolutionStatus.INCOMPLETE_RESOURCE_LIMIT
            conf = 0.50
        elif is_ambiguous:
            status = HeaderResolutionStatus.AMBIGUOUS
            conf = 0.65
            evidence_list.append(
                SpatialEvidence(
                    evidence_type=SpatialEvidenceType.AMBIGUOUS_HEADER_STRUCTURE,
                    description="; ".join(ambiguity_reasons),
                    heuristic_score=0.60,
                    provenance="M04:HeaderResolver:ambiguity_check",
                    coordinates=BoundingBox(
                        min_row=header_start_row,
                        max_row=header_end_row,
                        min_col=box.min_col,
                        max_col=box.max_col,
                    ),
                )
            )
        elif all(c.resolved_name for c in final_columns):
            status = HeaderResolutionStatus.HIGH_CONFIDENCE
            conf = 0.95 if header_row_count == 1 else 0.92
        else:
            status = HeaderResolutionStatus.TENTATIVE
            conf = 0.75

        return HeaderResolutionReport(
            region_id=region.region_id,
            sheet_name=sheet_name,
            status=status,
            header_row_start=header_start_row,
            header_row_end=header_end_row,
            header_row_count=header_row_count,
            columns=final_columns,
            heuristic_confidence=conf,
            evidence=evidence_list,
            is_ambiguous=is_ambiguous,
            ambiguity_details="; ".join(ambiguity_reasons) if ambiguity_reasons else None,
            delimiter_used=self.delimiter,
            is_truncated=is_resource_truncated,
            truncation_details=truncation_detail,
        )

    def resolve_sheet(
        self,
        reader: StreamingWorkbookReader,
        sheet: Union[str, int],
        regions: list[SpatialTableRegion],
        *,
        facts: Optional[DeclaredOpenXmlFacts] = None,
        merge_cells: Optional[list[DeclaredMergeCell]] = None,
        list_objects: Optional[list[DeclaredListObject]] = None,
    ) -> list[HeaderResolutionReport]:
        """Resolve headers across all spatial regions in a worksheet via streaming.

        Buffers only the needed top rows per region without materializing the sheet.
        """
        if isinstance(sheet, int):
            names = reader.sheet_names
            if sheet < 0 or sheet >= len(names):
                raise ValueError(f"Sheet index {sheet} out of range (0..{len(names)-1})")
            sheet_name = names[sheet]
        else:
            sheet_name = str(sheet)

        if not regions:
            return []

        # Find maximum scan row across all candidate regions
        max_scan_target = max(
            min(r.bounding_box.max_row, r.bounding_box.min_row + self.max_scan_rows - 1)
            for r in regions
        )

        # Stream chunks up to max_scan_target
        buffered_rows: list[dict[str, Any]] = []
        for chunk in reader.stream_sheet(sheet_name, chunk_size=1000):
            for row_rec in chunk:
                r_num = row_rec.get("row", 0)
                if r_num <= max_scan_target:
                    buffered_rows.append(row_rec)
                else:
                    break
            if buffered_rows and buffered_rows[-1].get("row", 0) > max_scan_target:
                break

        if merge_cells is None and facts is not None:
            merge_cells = facts.merge_cells
        if list_objects is None and facts is not None:
            list_objects = facts.list_objects

        reports: list[HeaderResolutionReport] = []
        for reg in regions:
            rep = self.resolve_region(
                reg,
                buffered_rows,
                merge_cells=merge_cells,
                list_objects=list_objects,
            )
            reports.append(rep)

        return reports
