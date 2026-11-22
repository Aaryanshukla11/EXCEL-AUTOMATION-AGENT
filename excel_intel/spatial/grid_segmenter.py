"""Generic Two-Dimensional Grid Segmentation Engine (M04).

Identifies spatially distinct tabular regions and sparse islands across worksheets
using sliding lookahead horizontal bands and orthogonal vertical whitespace corridor scanning.
Operates with strictly bounded memory complexity O(W * C).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterator, Optional, Union

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

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader
    from excel_intel.inspection.models import DeclaredOpenXmlFacts


def _box_contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    """Return True if outer completely encloses inner."""
    return (
        outer.min_row <= inner.min_row
        and outer.max_row >= inner.max_row
        and outer.min_col <= inner.min_col
        and outer.max_col >= inner.max_col
    )


class _ActiveBlock:
    """Internal lightweight representation of a candidate spatial block."""

    def __init__(
        self,
        min_row: int,
        max_row: int,
        min_col: int,
        max_col: int,
        populated_cells: int,
        row_widths: list[int],
        window_count: int = 1,
    ) -> None:
        self.min_row = min_row
        self.max_row = max_row
        self.min_col = min_col
        self.max_col = max_col
        self.populated_cells = populated_cells
        self.row_widths = row_widths
        self.window_count = window_count
        self.corridor_evidence: list[SpatialEvidence] = []
        self.has_vertical_cut = False
        self.has_horizontal_cut = False

    @property
    def box(self) -> BoundingBox:
        return BoundingBox(
            min_row=self.min_row,
            max_row=self.max_row,
            min_col=self.min_col,
            max_col=self.max_col,
        )

    def extend_with(
        self,
        max_row: int,
        min_col: int,
        max_col: int,
        added_cells: int,
        added_widths: list[int],
    ) -> None:
        self.max_row = max(self.max_row, max_row)
        self.min_col = min(self.min_col, min_col)
        self.max_col = max(self.max_col, max_col)
        self.populated_cells += added_cells
        if len(self.row_widths) < 100:
            self.row_widths.extend(added_widths[: 100 - len(self.row_widths)])
        self.window_count += 1


class GridSegmenter:
    """Two-dimensional grid segmentation engine for generic Excel worksheets."""

    def __init__(
        self,
        *,
        window_size: int = 50,
        min_blank_rows_for_cut: int = 1,
        min_blank_cols_for_cut: int = 1,
        sparse_island_threshold_cells: int = 3,
        sparse_island_threshold_density: float = 0.10,
        max_active_regions: int = 1000,
        max_overflow_window_span: int = 500,
        max_finalized_regions: int = 5000,
        max_sparse_islands: int = 2000,
        max_corridors: int = 5000,
    ) -> None:
        """Initialize segmenter with lookahead window and corridor thresholds.

        Args:
            window_size: Sliding lookahead window row depth (default W=50).
            min_blank_rows_for_cut: Minimum empty rows required to split horizontal regions.
            min_blank_cols_for_cut: Minimum empty columns required to split vertical regions.
            sparse_island_threshold_cells: Cell count ceiling for sparse island classification.
            sparse_island_threshold_density: Maximum density for sparse island classification.
            max_active_regions: Maximum concurrent active regions before overflow is flagged.
            max_overflow_window_span: Maximum consecutive window span before overflow is flagged.
            max_finalized_regions: Global maximum for finalized candidate table regions.
            max_sparse_islands: Global maximum for isolated sparse islands.
            max_corridors: Global maximum for detected whitespace separation corridors.
        """
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")
        if min_blank_rows_for_cut < 1:
            raise ValueError(f"min_blank_rows_for_cut must be >= 1, got {min_blank_rows_for_cut}")
        if min_blank_cols_for_cut < 1:
            raise ValueError(f"min_blank_cols_for_cut must be >= 1, got {min_blank_cols_for_cut}")

        self.window_size = window_size
        self.min_blank_rows = min_blank_rows_for_cut
        self.min_blank_cols = min_blank_cols_for_cut
        self.sparse_cell_thresh = sparse_island_threshold_cells
        self.sparse_density_thresh = sparse_island_threshold_density
        self.max_active_regions = max_active_regions
        self.max_overflow_window_span = max_overflow_window_span
        self.max_finalized_regions = max_finalized_regions
        self.max_sparse_islands = max_sparse_islands
        self.max_corridors = max_corridors

    def segment_sheet(
        self,
        reader: StreamingWorkbookReader,
        sheet: Union[str, int],
        *,
        facts: Optional[DeclaredOpenXmlFacts] = None,
    ) -> SpatialDetectionReport:
        """Segment a worksheet streamed via StreamingWorkbookReader.

        Args:
            reader: StreamingWorkbookReader instance.
            sheet: Sheet name (str) or 0-indexed position (int).
            facts: Optional M03 DeclaredOpenXmlFacts for anchoring declared tables.

        Returns:
            SpatialDetectionReport containing detected regions, corridors, and islands.
        """
        if isinstance(sheet, int):
            names = reader.sheet_names
            if sheet < 0 or sheet >= len(names):
                raise ValueError(f"Sheet index {sheet} out of range (0..{len(names)-1})")
            sheet_name = names[sheet]
        else:
            sheet_name = str(sheet)
            if sheet_name not in reader.sheet_names:
                raise ValueError(f"Sheet '{sheet_name}' not found in workbook")

        declared_tables: list[tuple[BoundingBox, str]] = []
        if facts and facts.list_objects:
            for lo in facts.list_objects:
                box = getattr(lo, "box", getattr(lo, "range_box", None))
                if box:
                    declared_tables.append((box, lo.display_name or lo.name))

        chunks_iter = reader.stream_sheet(sheet_name, chunk_size=1000)
        return self.segment_rows(
            chunks_iter,
            sheet_name=sheet_name,
            workbook_path=str(reader.path),
            declared_boxes=declared_tables,
        )

    def segment_rows(
        self,
        row_stream: Union[Iterator[dict[str, Any]], Iterator[list[dict[str, Any]]]],
        sheet_name: str,
        *,
        workbook_path: str = "",
        declared_boxes: Optional[list[tuple[BoundingBox, str]]] = None,
    ) -> SpatialDetectionReport:
        """Segment rows provided as a streaming iterator.

        Args:
            row_stream: Iterator yielding row records or chunks of row records.
            sheet_name: Name of the worksheet.
            workbook_path: Path of source workbook (optional).
            declared_boxes: Optional list of (BoundingBox, name) tuples for declared OpenXML tables.

        Returns:
            SpatialDetectionReport containing detected regions, corridors, and islands.
        """
        declared_boxes = declared_boxes or []
        detected_corridors: list[SeparationCorridor] = []
        finalized_blocks: list[_ActiveBlock] = []
        active_blocks: list[_ActiveBlock] = []

        total_cells_evaluated = 0
        overflow_detected = False
        overflow_details: Optional[str] = None
        is_truncated = False
        truncation_reasons: list[str] = []

        # Lightweight window buffer: row_idx -> set of populated col_idx
        window_row_cols: dict[int, set[int]] = {}
        window_start_row = 1

        def flatten_rows() -> Iterator[dict[str, Any]]:
            for item in row_stream:
                if isinstance(item, list):
                    for r in item:
                        yield r
                elif isinstance(item, dict):
                    yield item

        def process_window(is_last: bool = False) -> None:
            nonlocal window_start_row, total_cells_evaluated, overflow_detected, overflow_details, is_truncated
            if not window_row_cols:
                if is_last and active_blocks:
                    for blk in active_blocks:
                        if len(finalized_blocks) < (self.max_finalized_regions + self.max_sparse_islands):
                            finalized_blocks.append(blk)
                        else:
                            is_truncated = True
                            truncation_reasons.append(
                                f"Finalized blocks reached limit ({self.max_finalized_regions + self.max_sparse_islands})"
                            )
                            overflow_detected = True
                    active_blocks.clear()
                return

            window_end_row = max(window_row_cols.keys())
            sorted_rows = sorted(window_row_cols.keys())

            # 1. Horizontal row band segmentation
            row_bands: list[list[int]] = []
            current_band: list[int] = [sorted_rows[0]]

            for r in sorted_rows[1:]:
                prev_r = current_band[-1]
                gap = r - prev_r - 1
                if gap >= self.min_blank_rows:
                    row_bands.append(current_band)
                    if len(detected_corridors) < self.max_corridors:
                        detected_corridors.append(
                            SeparationCorridor(
                                orientation=CorridorOrientation.HORIZONTAL,
                                start_index=prev_r + 1,
                                end_index=r - 1,
                                width=gap,
                                span_min=min(min(window_row_cols[row]) for row in current_band),
                                span_max=max(max(window_row_cols[row]) for row in current_band),
                            )
                        )
                    else:
                        is_truncated = True
                        truncation_reasons.append(f"Corridors reached limit of {self.max_corridors}")
                    current_band = [r]
                else:
                    current_band.append(r)

            if current_band:
                row_bands.append(current_band)

            # 2. Vertical corridor scanning within each row band
            window_candidate_blocks: list[_ActiveBlock] = []

            for band in row_bands:
                band_min_row = band[0]
                band_max_row = band[-1]
                all_band_cols: set[int] = set.union(*(window_row_cols[r] for r in band))

                if not all_band_cols:
                    continue

                sorted_cols = sorted(all_band_cols)
                c_min_total = sorted_cols[0]
                c_max_total = sorted_cols[-1]

                # Identify vertical separation corridors across this row band
                col_sub_bands: list[tuple[int, int]] = []
                current_col_start = sorted_cols[0]
                current_col_end = sorted_cols[0]

                for c in sorted_cols[1:]:
                    gap = c - current_col_end - 1
                    if gap >= self.min_blank_cols:
                        col_sub_bands.append((current_col_start, current_col_end))
                        if len(detected_corridors) < self.max_corridors:
                            detected_corridors.append(
                                SeparationCorridor(
                                    orientation=CorridorOrientation.VERTICAL,
                                    start_index=current_col_end + 1,
                                    end_index=c - 1,
                                    width=gap,
                                    span_min=band_min_row,
                                    span_max=band_max_row,
                                )
                            )
                        else:
                            is_truncated = True
                            truncation_reasons.append(f"Corridors reached limit of {self.max_corridors}")
                        current_col_start = c
                        current_col_end = c
                    else:
                        current_col_end = c

                col_sub_bands.append((current_col_start, current_col_end))

                # For each 2D candidate block, compute populated cells and widths
                for sub_c_min, sub_c_max in col_sub_bands:
                    block_cells = 0
                    block_widths: list[int] = []
                    for r in band:
                        r_cols_in_sub = [
                            c for c in window_row_cols[r] if sub_c_min <= c <= sub_c_max
                        ]
                        w = len(r_cols_in_sub)
                        if w > 0:
                            block_cells += w
                            if len(block_widths) < 100:
                                block_widths.append(w)

                    if block_cells > 0:
                        cand = _ActiveBlock(
                            min_row=band_min_row,
                            max_row=band_max_row,
                            min_col=sub_c_min,
                            max_col=sub_c_max,
                            populated_cells=block_cells,
                            row_widths=block_widths,
                        )
                        if len(col_sub_bands) > 1:
                            cand.has_vertical_cut = True
                            cand.corridor_evidence.append(
                                SpatialEvidence(
                                    evidence_type=SpatialEvidenceType.VERTICAL_CORRIDOR_ISOLATION,
                                    description=(
                                        f"Isolated horizontally from adjacent regions in cols {sub_c_min}..{sub_c_max} "
                                        f"across rows {band_min_row}..{band_max_row}"
                                    ),
                                    heuristic_score=0.90,
                                    provenance="M04:GridSegmenter:vertical_corridor_cut",
                                    coordinates=cand.box,
                                )
                            )
                        if len(row_bands) > 1:
                            cand.has_horizontal_cut = True
                            cand.corridor_evidence.append(
                                SpatialEvidence(
                                    evidence_type=SpatialEvidenceType.HORIZONTAL_CORRIDOR_ISOLATION,
                                    description=(
                                        f"Separated vertically by blank rows at {band_min_row}..{band_max_row}"
                                    ),
                                    heuristic_score=0.85,
                                    provenance="M04:GridSegmenter:horizontal_corridor_cut",
                                    coordinates=cand.box,
                                )
                            )
                        window_candidate_blocks.append(cand)

            # 3. Stitch across window boundaries
            next_active: list[_ActiveBlock] = []

            for cand in window_candidate_blocks:
                matched_prev: Optional[_ActiveBlock] = None
                # Check if cand extends any block from active_blocks
                for prev in active_blocks:
                    # Row adjacency: cand starts immediately or within min_blank_rows of prev.max_row
                    row_adjacent = (cand.min_row - prev.max_row - 1) < self.min_blank_rows
                    # Column alignment: column bounds overlap or match
                    cols_overlap = not (
                        cand.max_col < prev.min_col or cand.min_col > prev.max_col
                    )
                    if row_adjacent and cols_overlap:
                        matched_prev = prev
                        break

                if matched_prev is not None:
                    matched_prev.extend_with(
                        max_row=cand.max_row,
                        min_col=cand.min_col,
                        max_col=cand.max_col,
                        added_cells=cand.populated_cells,
                        added_widths=cand.row_widths,
                    )
                    if len(matched_prev.corridor_evidence) < 5:
                        matched_prev.corridor_evidence.append(
                            SpatialEvidence(
                                evidence_type=SpatialEvidenceType.LOOKAHEAD_CONTINUATION,
                                description=(
                                    f"Region boundary continued across lookahead window boundary at row {cand.min_row}"
                                ),
                                heuristic_score=0.95,
                                provenance=f"M04:GridSegmenter:window_span_{matched_prev.window_count}",
                                coordinates=matched_prev.box,
                            )
                        )
                    # Check overflow threshold
                    if matched_prev.window_count > self.max_overflow_window_span:
                        overflow_detected = True
                        overflow_details = (
                            f"Region {matched_prev.box.to_a1_ref()} exceeded maximum window "
                            f"overflow span ({self.max_overflow_window_span} windows, {matched_prev.window_count} active)"
                        )
                    next_active.append(matched_prev)
                    active_blocks.remove(matched_prev)
                else:
                    next_active.append(cand)

            # Any remaining active blocks that were not continued in this window are closed
            for uncontinued in active_blocks:
                if len(finalized_blocks) < (self.max_finalized_regions + self.max_sparse_islands):
                    finalized_blocks.append(uncontinued)
                else:
                    is_truncated = True
                    truncation_reasons.append(
                        f"Finalized blocks reached limit ({self.max_finalized_regions + self.max_sparse_islands})"
                    )
                    overflow_detected = True

            if len(next_active) > self.max_active_regions:
                overflow_detected = True
                overflow_details = (
                    f"Active regions count ({len(next_active)}) exceeded configured limit ({self.max_active_regions})"
                )

            active_blocks.clear()
            if is_last:
                for blk in next_active:
                    if len(finalized_blocks) < (self.max_finalized_regions + self.max_sparse_islands):
                        finalized_blocks.append(blk)
                    else:
                        is_truncated = True
                        truncation_reasons.append(
                            f"Finalized blocks reached limit ({self.max_finalized_regions + self.max_sparse_islands})"
                        )
                        overflow_detected = True
            else:
                active_blocks.extend(next_active)

            window_row_cols.clear()
            window_start_row = window_end_row + 1

        # Stream rows
        for row_record in flatten_rows():
            r_idx = row_record.get("row")
            if r_idx is None:
                continue

            cells = row_record.get("cells", [])
            populated_cols = set()
            for c in cells:
                val = c.get("value")
                col_idx = c.get("col")
                if col_idx is not None and val is not None and val != "":
                    populated_cols.add(col_idx)
                    total_cells_evaluated += 1

            if populated_cols:
                window_row_cols[r_idx] = populated_cols

            # Window flush check
            if len(window_row_cols) >= self.window_size:
                process_window(is_last=False)

        # Flush final window
        process_window(is_last=True)

        # 4. Classify finalized regions and detect relationships
        regions: list[SpatialTableRegion] = []
        sparse_islands: list[SpatialTableRegion] = []

        for block in finalized_blocks:
            box = block.box
            cell_count = box.cell_count
            pop_cells = block.populated_cells
            density = round(pop_cells / max(1, cell_count), 4)

            # Check declared table match
            is_declared = False
            decl_name: Optional[str] = None
            for d_box, d_name in declared_boxes:
                if box == d_box or (box.min_row == d_box.min_row and box.min_col == d_box.min_col):
                    is_declared = True
                    decl_name = d_name
                    break

            # Classification
            if is_declared:
                region_type = SpatialRegionType.DECLARED_TABLE
                confidence = 1.0
            elif (
                pop_cells <= self.sparse_cell_thresh
                and (
                    density < self.sparse_density_thresh
                    or cell_count <= self.sparse_cell_thresh
                    or cell_count > 100
                )
            ):
                region_type = SpatialRegionType.SPARSE_ISLAND
                confidence = 0.90
            elif box.col_count == 2 and box.row_count >= 3:
                region_type = SpatialRegionType.KEY_VALUE_GRID
                confidence = round(0.70 + 0.30 * density, 4)
            elif len(block.row_widths) >= 4:
                avg_w = sum(block.row_widths) / len(block.row_widths)
                variance = sum((w - avg_w) ** 2 for w in block.row_widths) / len(block.row_widths)
                if avg_w > 0 and (variance ** 0.5) / avg_w > 0.5:
                    region_type = SpatialRegionType.IRREGULAR_COMPOSITE
                    confidence = round(max(0.20, 0.60 * density), 4)
                else:
                    region_type = SpatialRegionType.INFERRED_TABLE
                    confidence = round(min(1.0, 0.40 * density + 0.30 * (1.0 if block.has_vertical_cut else 0.7) + 0.30), 4)
            else:
                region_type = SpatialRegionType.INFERRED_TABLE
                confidence = round(min(1.0, 0.50 * density + 0.50), 4)

            # Evidence assembly
            evidence_list: list[SpatialEvidence] = list(block.corridor_evidence)
            if is_declared:
                evidence_list.append(
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.DECLARED_OPENXML,
                        description=f"Directly declared OpenXML ListObject '{decl_name}'",
                        heuristic_score=1.0,
                        provenance="M04:OpenXML:ListObjectDeclaration",
                        coordinates=box,
                    )
                )
            else:
                evidence_list.append(
                    SpatialEvidence(
                        evidence_type=SpatialEvidenceType.DENSE_CELL_CLUSTER,
                        description=(
                            f"Populated cell cluster: {pop_cells} cells across {box.row_count} rows, "
                            f"{box.col_count} cols (density {density*100:.1f}%)"
                        ),
                        heuristic_score=round(min(1.0, density + 0.2), 4),
                        provenance="M04:GridSegmenter:density_evaluation",
                        coordinates=box,
                    )
                )

            stable_id = (
                f"spat_{sheet_name}_r{box.min_row}_{box.max_row}_c{box.min_col}_{box.max_col}"
            )

            region_obj = SpatialTableRegion(
                region_id=stable_id,
                sheet_name=sheet_name,
                bounding_box=box,
                region_type=region_type,
                is_declared=is_declared,
                declared_name=decl_name,
                heuristic_confidence=confidence,
                evidence=evidence_list,
                cell_count=cell_count,
                populated_cell_count=pop_cells,
                density=density,
            )

            if region_type == SpatialRegionType.SPARSE_ISLAND:
                if len(sparse_islands) < self.max_sparse_islands:
                    sparse_islands.append(region_obj)
                else:
                    is_truncated = True
                    truncation_reasons.append(f"Sparse islands reached output limit ({self.max_sparse_islands})")
            else:
                if len(regions) < self.max_finalized_regions:
                    regions.append(region_obj)
                else:
                    is_truncated = True
                    truncation_reasons.append(f"Finalized regions reached output limit ({self.max_finalized_regions})")

        # 5. Relationship Resolution (Nested & Overlapping Regions)
        # Relationship resolution operates over candidate table regions
        candidate_regions = regions
        parent_map: dict[str, str] = {}
        child_map: dict[str, list[str]] = {r.region_id: [] for r in candidate_regions}
        overlap_map: dict[str, list[str]] = {r.region_id: [] for r in candidate_regions}

        for i, reg_a in enumerate(candidate_regions):
            box_a = reg_a.bounding_box
            for j, reg_b in enumerate(candidate_regions):
                if i == j:
                    continue
                box_b = reg_b.bounding_box

                # Strict enclosure check (Nested)
                if _box_contains(box_a, box_b) and box_a != box_b:
                    parent_map[reg_b.region_id] = reg_a.region_id
                    child_map[reg_a.region_id].append(reg_b.region_id)
                # Partial intersection check (Overlapping)
                elif box_a.intersects(box_b) and not _box_contains(box_b, box_a):
                    overlap_map[reg_a.region_id].append(reg_b.region_id)

        # Re-instantiate with relationship fields populated if relationships exist
        updated_regions: list[SpatialTableRegion] = []
        for reg in regions:
            p_id = parent_map.get(reg.region_id)
            c_ids = child_map.get(reg.region_id, [])
            o_ids = overlap_map.get(reg.region_id, [])

            if p_id or c_ids or o_ids:
                extra_ev: list[SpatialEvidence] = list(reg.evidence)
                if p_id:
                    extra_ev.append(
                        SpatialEvidence(
                            evidence_type=SpatialEvidenceType.NESTED_PARENT,
                            description=f"Enclosed within parent spatial region '{p_id}'",
                            heuristic_score=0.90,
                            provenance="M04:GridSegmenter:nested_enclosure",
                            coordinates=reg.bounding_box,
                        )
                    )
                if o_ids:
                    extra_ev.append(
                        SpatialEvidence(
                            evidence_type=SpatialEvidenceType.OVERLAPPING_INTERSECTION,
                            description=f"Partially overlaps with candidate regions: {o_ids}",
                            heuristic_score=0.75,
                            provenance="M04:GridSegmenter:partial_overlap",
                            coordinates=reg.bounding_box,
                        )
                    )

                reg = SpatialTableRegion(
                    region_id=reg.region_id,
                    sheet_name=reg.sheet_name,
                    bounding_box=reg.bounding_box,
                    region_type=reg.region_type,
                    is_declared=reg.is_declared,
                    declared_name=reg.declared_name,
                    heuristic_confidence=reg.heuristic_confidence,
                    evidence=extra_ev,
                    parent_region_id=p_id,
                    child_region_ids=c_ids,
                    overlapping_region_ids=o_ids,
                    cell_count=reg.cell_count,
                    populated_cell_count=reg.populated_cell_count,
                    density=reg.density,
                    header_row=reg.header_row,
                    columns=reg.columns,
                )
            updated_regions.append(reg)

        truncation_details_str = "; ".join(dict.fromkeys(truncation_reasons)) if truncation_reasons else None
        return SpatialDetectionReport(
            workbook_path=workbook_path,
            sheet_name=sheet_name,
            regions=updated_regions,
            sparse_islands=sparse_islands,
            corridors_detected=detected_corridors,
            lookahead_window_size=self.window_size,
            lookahead_overflow_detected=overflow_detected or is_truncated,
            lookahead_overflow_details=overflow_details or truncation_details_str,
            is_truncated=is_truncated,
            truncation_details=truncation_details_str,
            total_populated_cells_evaluated=total_cells_evaluated,
            detection_timestamp=datetime.now(timezone.utc).isoformat(),
        )
