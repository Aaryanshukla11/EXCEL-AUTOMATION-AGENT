"""Semantic Data Type Inference Engine (M05).

Evaluates cell values strictly within the SemanticZoneType.BODY zone of detected
spatial table regions, computing fine-grained semantic categories, statistical
metrics, explicit inference states, heuristic support scores, and safe projections
to canonical M01 ColumnMetadata contracts.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence, Union

from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.core.types import ColumnType
from excel_intel.inspection.models import BoundingBox, DeclaredOpenXmlFacts
from excel_intel.spatial.models import (
    SemanticZoneType,
    SpatialDetectionReport,
    SpatialTableRegion,
)
from excel_intel.types.models import (
    ColumnTypeProfile,
    InferenceState,
    NormalizedValue,
    RegionTypeReport,
    SamplingDiagnostics,
    ValueCategory,
)
from excel_intel.types.pattern_detector import PatternDetector
from excel_intel.types.sampling import MAX_CELL_BUDGET, sample_body_coordinates

_CELL_REF_REGEX = re.compile(r"^([A-Za-z]+)([0-9]+)$")


def col_letter_to_index(col_str: str) -> int:
    """Convert an Excel column letter (e.g. 'A', 'Z', 'AA') to 1-indexed column integer."""
    result = 0
    for ch in col_str.upper():
        if "A" <= ch <= "Z":
            result = result * 26 + (ord(ch) - ord("A") + 1)
    return result


def extract_col_from_coord(coord: Optional[str]) -> Optional[int]:
    """Extract 1-indexed column number from an A1-style coordinate string."""
    if not coord:
        return None
    match = _CELL_REF_REGEX.match(coord)
    if match:
        return col_letter_to_index(match.group(1))
    return None


class TypeInferenceEngine:
    """High-performance semantic type inference engine.

    Enforces:
    - Zone-constrained sampling strictly within SemanticZoneType.BODY.
    - Deterministic 2D sampling budget (<= 10,000 cells per region).
    - Discrete architectural states (INFERRED, UNKNOWN, AMBIGUOUS, INSUFFICIENT_DATA).
    - Mathematically bounded heuristic support scores in [0.0, 1.0].
    - Safe carrier projection to M01 ColumnType.STRING for non-inferred states.
    """

    def __init__(self, *, cell_budget: int = MAX_CELL_BUDGET) -> None:
        self.cell_budget = cell_budget

    def infer_sheet(
        self,
        reader: StreamingWorkbookReader,
        sheet_name: str,
        table_regions: Sequence[SpatialTableRegion],
        facts: Optional[DeclaredOpenXmlFacts] = None,
    ) -> list[RegionTypeReport]:
        """Infer column semantic types for all detected regions on a worksheet.

        Args:
            reader: Active StreamingWorkbookReader instance.
            sheet_name: Name of worksheet to stream.
            table_regions: Sequence of SpatialTableRegion entities discovered in M04.
            facts: Optional declared OpenXML facts for the worksheet.

        Returns:
            List of RegionTypeReport containing column profiles for each region.
        """
        reports: list[RegionTypeReport] = []
        for region in table_regions:
            report = self.infer_region(reader, sheet_name, region, facts=facts)
            reports.append(report)
        return reports

    def infer_region(
        self,
        reader: StreamingWorkbookReader,
        sheet_name: str,
        region: SpatialTableRegion,
        facts: Optional[DeclaredOpenXmlFacts] = None,
    ) -> RegionTypeReport:
        """Infer column semantic types for a single SpatialTableRegion.

        Args:
            reader: Active StreamingWorkbookReader instance.
            sheet_name: Name of worksheet.
            region: Detected SpatialTableRegion.
            facts: Optional declared facts from M03 inspection.

        Returns:
            RegionTypeReport containing type profiles for all columns in region.
        """
        body_box = self._extract_body_bounding_box(region)
        if body_box is None:
            return self._build_empty_region_report(region, sheet_name)

        # Extract hidden lines and merges from facts if available
        hidden_rows: set[int] = set()
        hidden_cols: set[int] = set()
        merge_cells: list[Any] = []
        if facts is not None:
            merge_cells = facts.merge_cells
            for interval in getattr(facts, "hidden_row_intervals", []):
                for r in range(interval.start, interval.end + 1):
                    hidden_rows.add(r)
            for interval in getattr(facts, "hidden_col_intervals", []):
                for c in range(interval.start, interval.end + 1):
                    hidden_cols.add(c)

        # Compute deterministic 2D sampling
        sampled_row_indices, sampled_col_indices, sampling_diag = sample_body_coordinates(
            body_box,
            cell_budget=self.cell_budget,
            hidden_rows=hidden_rows,
            hidden_cols=hidden_cols,
            merge_cells=merge_cells,
        )

        sampled_rows_set = set(sampled_row_indices)
        sampled_cols_set = set(sampled_col_indices)

        # Prepare merge anchor lookup
        merge_lookup = self._build_merge_lookup(merge_cells, body_box)

        # Stream rows and collect sampled cells: (row, col) -> cell_dict
        sampled_cells_by_coord: dict[tuple[int, int], dict[str, Any]] = {}
        for chunk in reader.stream_sheet(sheet_name, chunk_size=1000):
            for row_record in chunk:
                r_idx = row_record.get("row")
                if r_idx is None:
                    continue
                if r_idx < body_box.min_row:
                    continue
                if r_idx > body_box.max_row:
                    # Rows are ordered in OpenXML; can safely terminate early
                    break
                if r_idx not in sampled_rows_set:
                    continue

                for cell in row_record.get("cells", []):
                    c_idx = cell.get("col")
                    if c_idx is None:
                        c_idx = extract_col_from_coord(cell.get("coordinate"))
                    if c_idx is not None and c_idx in sampled_cols_set:
                        sampled_cells_by_coord[(r_idx, c_idx)] = cell

        return self._profile_region_data(
            region=region,
            sheet_name=sheet_name,
            body_box=body_box,
            sampled_row_indices=sampled_row_indices,
            sampled_col_indices=sampled_col_indices,
            sampled_cells_by_coord=sampled_cells_by_coord,
            sampling_diag=sampling_diag,
            merge_lookup=merge_lookup,
        )

    def infer_cells(
        self,
        sampled_cells_by_coord: dict[tuple[int, int], dict[str, Any]],
        region: SpatialTableRegion,
        *,
        sheet_name: Optional[str] = None,
        facts: Optional[DeclaredOpenXmlFacts] = None,
        sampling_diag: Optional[SamplingDiagnostics] = None,
    ) -> RegionTypeReport:
        """Infer column profiles from pre-loaded cell dictionary (in-memory evaluation).

        Args:
            sampled_cells_by_coord: Mapping of (row, col) -> cell dict.
            region: SpatialTableRegion.
            sheet_name: Optional sheet name override.
            facts: Optional declared facts.
            sampling_diag: Optional pre-computed sampling diagnostics.
        """
        s_name = sheet_name or region.sheet_name
        body_box = self._extract_body_bounding_box(region)
        if body_box is None:
            return self._build_empty_region_report(region, s_name)

        merge_cells = facts.merge_cells if facts else []
        hidden_rows: set[int] = set()
        hidden_cols: set[int] = set()
        if facts is not None:
            for interval in getattr(facts, "hidden_row_intervals", []):
                for r in range(interval.start, interval.end + 1):
                    hidden_rows.add(r)
            for interval in getattr(facts, "hidden_col_intervals", []):
                for c in range(interval.start, interval.end + 1):
                    hidden_cols.add(c)

        if sampling_diag is None:
            sampled_rows, sampled_cols, sampling_diag = sample_body_coordinates(
                body_box,
                cell_budget=self.cell_budget,
                hidden_rows=hidden_rows,
                hidden_cols=hidden_cols,
                merge_cells=merge_cells,
            )
        else:
            sampled_rows = sampling_diag.sampled_row_indices
            sampled_cols = sampling_diag.sampled_col_indices

        merge_lookup = self._build_merge_lookup(merge_cells, body_box)

        return self._profile_region_data(
            region=region,
            sheet_name=s_name,
            body_box=body_box,
            sampled_row_indices=sampled_rows,
            sampled_col_indices=sampled_cols,
            sampled_cells_by_coord=sampled_cells_by_coord,
            sampling_diag=sampling_diag,
            merge_lookup=merge_lookup,
        )

    # -------------------------------------------------------------------------
    # Internal Inference & Profiling Helpers
    # -------------------------------------------------------------------------

    def _extract_body_bounding_box(
        self, region: SpatialTableRegion
    ) -> Optional[BoundingBox]:
        """Extract or derive the bounding box for the BODY zone of a region."""
        # 1. Prefer explicit SemanticZoneType.BODY
        body_zone = region.zones.get(SemanticZoneType.BODY)
        if body_zone is not None:
            return body_zone.bounding_box

        # 2. Check for string key "BODY"
        for z_key, z_val in region.zones.items():
            if str(z_key).upper() in ("BODY", "SEMANTICZONETYPE.BODY"):
                return z_val.bounding_box

        # 3. Derive from header resolution or header_row
        r_box = region.bounding_box
        header_end = None
        if region.header_resolution and region.header_resolution.header_row_end:
            header_end = region.header_resolution.header_row_end
        elif region.header_row is not None:
            header_end = region.header_row

        if header_end is not None:
            body_min_row = header_end + 1
        else:
            body_min_row = r_box.min_row

        if body_min_row > r_box.max_row:
            return None

        return BoundingBox(
            min_row=body_min_row,
            max_row=r_box.max_row,
            min_col=r_box.min_col,
            max_col=r_box.max_col,
        )

    def _build_empty_region_report(
        self, region: SpatialTableRegion, sheet_name: str
    ) -> RegionTypeReport:
        """Construct a report for a region with zero body rows."""
        r_box = region.bounding_box
        columns: dict[int, ColumnTypeProfile] = {}
        for c in range(r_box.min_col, r_box.max_col + 1):
            columns[c] = ColumnTypeProfile(
                col_index=c,
                state=InferenceState.UNKNOWN,
                candidate_type=None,
                total_cells=0,
                effective_cells=0,
                populated_cells=0,
                null_cells=0,
                nullability_ratio=1.0,
                null_marker_count=0,
                merged_non_anchor_cells=0,
                category_counts={},
                inferred_type=ColumnType.STRING,
                heuristic_support_score=0.0,
                is_ambiguous=False,
                ambiguity_reason="Zero body rows detected in region",
                competing_types=[],
                requires_human_review=True,
                sample_values=[],
                formula_pattern=None,
            )

        diag = SamplingDiagnostics(
            total_rows=0,
            total_cols=r_box.max_col - r_box.min_col + 1,
            sampled_rows=0,
            sampled_cols=0,
            sampled_cells=0,
            is_truncated=False,
            truncation_details=None,
            sampled_row_indices=[],
            sampled_col_indices=[],
            hidden_row_count=0,
            hidden_col_count=0,
            merged_cell_count=0,
        )

        return RegionTypeReport(
            region_id=region.region_id,
            sheet_name=sheet_name,
            body_row_start=r_box.min_row,
            body_row_end=r_box.min_row,
            body_col_start=r_box.min_col,
            body_col_end=r_box.max_col,
            columns=columns,
            has_ambiguous_columns=False,
            sampling=diag,
            is_tentative=False,
        )

    def _build_merge_lookup(
        self, merge_cells: Sequence[Any], body_box: BoundingBox
    ) -> dict[tuple[int, int], tuple[int, int]]:
        """Map non-anchor cells inside merged ranges to their top-left anchor coordinate."""
        lookup: dict[tuple[int, int], tuple[int, int]] = {}
        for m in merge_cells:
            box = getattr(m, "box", None)
            if box is None:
                continue
            # Check intersection with body_box
            if (
                box.min_row <= body_box.max_row
                and box.max_row >= body_box.min_row
                and box.min_col <= body_box.max_col
                and box.max_col >= body_box.min_col
            ):
                anchor = (box.min_row, box.min_col)
                for r in range(box.min_row, box.max_row + 1):
                    for c in range(box.min_col, box.max_col + 1):
                        if (r, c) != anchor:
                            lookup[(r, c)] = anchor
        return lookup

    def _profile_region_data(
        self,
        *,
        region: SpatialTableRegion,
        sheet_name: str,
        body_box: BoundingBox,
        sampled_row_indices: list[int],
        sampled_col_indices: list[int],
        sampled_cells_by_coord: dict[tuple[int, int], dict[str, Any]],
        sampling_diag: SamplingDiagnostics,
        merge_lookup: dict[tuple[int, int], tuple[int, int]],
    ) -> RegionTypeReport:
        """Profile sampled column data and compute column type profiles."""
        columns: dict[int, ColumnTypeProfile] = {}
        has_ambiguous_columns = False

        # Profile all columns across the region bounding box
        all_cols = range(region.bounding_box.min_col, region.bounding_box.max_col + 1)
        sampled_cols_set = set(sampled_col_indices)

        for col_idx in all_cols:
            if col_idx not in sampled_cols_set:
                # Column was omitted due to 2D column sampling cap (> 1000 cols)
                profile = ColumnTypeProfile(
                    col_index=col_idx,
                    state=InferenceState.UNKNOWN,
                    candidate_type=None,
                    total_cells=len(sampled_row_indices),
                    effective_cells=len(sampled_row_indices),
                    populated_cells=0,
                    null_cells=len(sampled_row_indices),
                    nullability_ratio=1.0,
                    null_marker_count=0,
                    merged_non_anchor_cells=0,
                    category_counts={},
                    inferred_type=ColumnType.STRING,
                    heuristic_support_score=0.0,
                    is_ambiguous=True,
                    ambiguity_reason="Column unvisited due to 2D sampling column cap",
                    competing_types=[],
                    requires_human_review=True,
                    sample_values=[],
                    formula_pattern=None,
                )
                columns[col_idx] = profile
                has_ambiguous_columns = True
                continue

            profile = self._profile_single_column(
                col_idx=col_idx,
                sampled_row_indices=sampled_row_indices,
                sampled_cells_by_coord=sampled_cells_by_coord,
                merge_lookup=merge_lookup,
            )
            columns[col_idx] = profile
            if profile.state in (InferenceState.AMBIGUOUS, InferenceState.INSUFFICIENT_DATA):
                has_ambiguous_columns = True

        total_semantic_obs = sum(p.populated_cells for p in columns.values())
        final_sampling_diag = sampling_diag.model_copy(
            update={"semantic_observation_count": total_semantic_obs}
        )

        return RegionTypeReport(
            region_id=region.region_id,
            sheet_name=sheet_name,
            body_row_start=body_box.min_row,
            body_row_end=body_box.max_row,
            body_col_start=region.bounding_box.min_col,
            body_col_end=region.bounding_box.max_col,
            columns=columns,
            has_ambiguous_columns=has_ambiguous_columns,
            sampling=final_sampling_diag,
            is_tentative=final_sampling_diag.is_truncated,
        )

    def _profile_single_column(
        self,
        *,
        col_idx: int,
        sampled_row_indices: list[int],
        sampled_cells_by_coord: dict[tuple[int, int], dict[str, Any]],
        merge_lookup: dict[tuple[int, int], tuple[int, int]],
    ) -> ColumnTypeProfile:
        """Statistically profile values in a single column."""
        total_cells = len(sampled_row_indices)
        category_counts: dict[str, int] = {}
        sample_values: list[Any] = []
        formula_patterns: list[str] = []

        date_order_ambiguity_count = 0
        boolean_candidate_count = 0
        populated_count = 0
        merged_non_anchor_cells = 0
        definite_null_count = 0
        null_marker_count = 0
        seen_merge_anchors_in_col: set[tuple[int, int]] = set()

        for r_idx in sampled_row_indices:
            coord = (r_idx, col_idx)

            # Check if this cell is covered by a multi-cell merge
            if coord in merge_lookup:
                anchor_r, anchor_c = merge_lookup[coord]
                if anchor_c != col_idx:
                    # Horizontal merge: this coordinate belongs to anchor column anchor_c.
                    # Do not evaluate in col_idx, and do not treat as an independent null.
                    merged_non_anchor_cells += 1
                    continue
                else:
                    # Vertical merge in the same column:
                    # A merged anchor is one semantic observation. Continuation coordinates
                    # must not become duplicate observations.
                    if (anchor_r, anchor_c) in seen_merge_anchors_in_col:
                        merged_non_anchor_cells += 1
                        continue
                    seen_merge_anchors_in_col.add((anchor_r, anchor_c))
                    cell = sampled_cells_by_coord.get((anchor_r, anchor_c))
            else:
                cell = sampled_cells_by_coord.get(coord)
                if coord in merge_lookup.values():
                    seen_merge_anchors_in_col.add(coord)

            raw_val = cell.get("value") if cell else None
            formula = cell.get("formula") if cell else None
            format_code = cell.get("format_code") if cell else None

            if formula:
                formula_patterns.append(str(formula))

            # Run pattern detector
            norm: NormalizedValue = PatternDetector.detect_value(raw_val, format_code=format_code)

            if norm.category == ValueCategory.NULL:
                if norm.is_null_marker:
                    null_marker_count += 1
                    if len(sample_values) < 5 and raw_val is not None:
                        sample_values.append(raw_val)
                else:
                    definite_null_count += 1
                continue

            populated_count += 1
            cat_name = norm.category.value
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1

            if len(sample_values) < 5 and raw_val is not None:
                sample_values.append(raw_val)

            if norm.has_date_order_ambiguity:
                date_order_ambiguity_count += 1
            if norm.is_boolean_candidate:
                boolean_candidate_count += 1

        effective_total = max(0, total_cells - merged_non_anchor_cells)
        null_cells = max(0, effective_total - populated_count)
        nullability_ratio = round(null_cells / effective_total, 4) if effective_total > 0 else 0.0

        # Most frequent formula pattern if present
        formula_pattern = formula_patterns[0] if formula_patterns else None

        # Precedence Rule 1: No Populated Values
        if populated_count == 0:
            if null_marker_count > 0:
                # Column contains exclusively textual null markers ('-', 'N/A')
                # Ambiguous whether values represent legitimate text or missing data
                return ColumnTypeProfile(
                    col_index=col_idx,
                    state=InferenceState.AMBIGUOUS,
                    candidate_type=None,
                    total_cells=total_cells,
                    effective_cells=effective_total,
                    populated_cells=0,
                    null_cells=null_cells,
                    nullability_ratio=nullability_ratio,
                    null_marker_count=null_marker_count,
                    merged_non_anchor_cells=merged_non_anchor_cells,
                    category_counts=category_counts,
                    inferred_type=ColumnType.STRING,
                    heuristic_support_score=0.50,
                    is_ambiguous=True,
                    ambiguity_reason=f"Column contains exclusively textual null markers ({null_marker_count} cells); ambiguous whether values represent legitimate text or missing data",
                    competing_types=[ValueCategory.STRING],
                    requires_human_review=True,
                    sample_values=sample_values,
                    formula_pattern=formula_pattern,
                )

            # Pure blank / empty column -> UNKNOWN
            return ColumnTypeProfile(
                col_index=col_idx,
                state=InferenceState.UNKNOWN,
                candidate_type=None,
                total_cells=total_cells,
                effective_cells=effective_total,
                populated_cells=0,
                null_cells=null_cells,
                nullability_ratio=nullability_ratio,
                null_marker_count=0,
                merged_non_anchor_cells=merged_non_anchor_cells,
                category_counts=category_counts,
                inferred_type=ColumnType.STRING,
                heuristic_support_score=0.0,
                is_ambiguous=False,
                ambiguity_reason=None,
                competing_types=[],
                requires_human_review=True,
                sample_values=[],
                formula_pattern=formula_pattern,
            )

        # Predominant candidate type determination
        best_cat_str, best_count = max(category_counts.items(), key=lambda item: item[1])
        t_pred_cat = ValueCategory(best_cat_str)
        t_pred_type = t_pred_cat.to_column_type()

        # Homogeneity and Support Score Formulation
        h_ratio = best_count / populated_count
        if h_ratio >= 0.95:
            penalty = 0.0
        elif h_ratio >= 0.80:
            penalty = 0.10
        else:
            penalty = 0.25

        support_score = round(max(0.0, min(1.0, h_ratio * (1.0 - penalty))), 4)

        # Detect competing types for telemetry
        competing: list[ValueCategory] = [
            ValueCategory(k)
            for k, cnt in category_counts.items()
            if k != best_cat_str and cnt > 0
        ]

        # Precedence Rule 2: Insufficient Sample Count (1 <= N_pop < 5) -> INSUFFICIENT_DATA
        if populated_count < 5:
            return ColumnTypeProfile(
                col_index=col_idx,
                state=InferenceState.INSUFFICIENT_DATA,
                candidate_type=t_pred_type,
                total_cells=total_cells,
                effective_cells=effective_total,
                populated_cells=populated_count,
                null_cells=null_cells,
                nullability_ratio=nullability_ratio,
                null_marker_count=null_marker_count,
                merged_non_anchor_cells=merged_non_anchor_cells,
                category_counts=category_counts,
                inferred_type=ColumnType.STRING,
                heuristic_support_score=support_score,
                is_ambiguous=False,
                ambiguity_reason=f"Insufficient sample count ({populated_count} < 5)",
                competing_types=competing,
                requires_human_review=True,
                sample_values=sample_values,
                formula_pattern=formula_pattern,
            )

        # Precedence Rule 3: Unresolved Semantic Ambiguity
        # Case A: Date order ambiguity
        if t_pred_cat == ValueCategory.DATE and date_order_ambiguity_count > 0:
            return ColumnTypeProfile(
                col_index=col_idx,
                state=InferenceState.AMBIGUOUS,
                candidate_type=None,
                total_cells=total_cells,
                effective_cells=effective_total,
                populated_cells=populated_count,
                null_cells=null_cells,
                nullability_ratio=nullability_ratio,
                null_marker_count=null_marker_count,
                merged_non_anchor_cells=merged_non_anchor_cells,
                category_counts=category_counts,
                inferred_type=ColumnType.STRING,
                heuristic_support_score=support_score,
                is_ambiguous=True,
                ambiguity_reason="Date format order ambiguity (day/month unresolvable)",
                competing_types=competing,
                requires_human_review=True,
                sample_values=sample_values,
                formula_pattern=formula_pattern,
            )

        # Case B: Boolean candidate ambiguity (100% 0/1 integers with no explicit boolean style)
        if (
            t_pred_cat == ValueCategory.INTEGER
            and boolean_candidate_count == populated_count
            and boolean_candidate_count > 0
        ):
            return ColumnTypeProfile(
                col_index=col_idx,
                state=InferenceState.AMBIGUOUS,
                candidate_type=None,
                total_cells=total_cells,
                effective_cells=effective_total,
                populated_cells=populated_count,
                null_cells=null_cells,
                nullability_ratio=nullability_ratio,
                null_marker_count=null_marker_count,
                merged_non_anchor_cells=merged_non_anchor_cells,
                category_counts=category_counts,
                inferred_type=ColumnType.STRING,
                heuristic_support_score=support_score,
                is_ambiguous=True,
                ambiguity_reason="Integer vs Boolean ambiguity (all values are 0 or 1)",
                competing_types=[ValueCategory.BOOLEAN],
                requires_human_review=True,
                sample_values=sample_values,
                formula_pattern=formula_pattern,
            )

        # Precedence Rule 4: Low Homogeneity (H < 0.80) -> AMBIGUOUS
        if h_ratio < 0.80:
            return ColumnTypeProfile(
                col_index=col_idx,
                state=InferenceState.AMBIGUOUS,
                candidate_type=None,
                total_cells=total_cells,
                effective_cells=effective_total,
                populated_cells=populated_count,
                null_cells=null_cells,
                nullability_ratio=nullability_ratio,
                null_marker_count=null_marker_count,
                merged_non_anchor_cells=merged_non_anchor_cells,
                category_counts=category_counts,
                inferred_type=ColumnType.STRING,
                heuristic_support_score=support_score,
                is_ambiguous=True,
                ambiguity_reason=f"Low type homogeneity ({h_ratio:.2%} < 80.00%)",
                competing_types=competing,
                requires_human_review=True,
                sample_values=sample_values,
                formula_pattern=formula_pattern,
            )

        # Precedence Rule 5: Confident Inference (H >= 0.80 and S >= 0.70) -> INFERRED
        if support_score >= 0.70:
            return ColumnTypeProfile(
                col_index=col_idx,
                state=InferenceState.INFERRED,
                candidate_type=t_pred_type,
                total_cells=total_cells,
                effective_cells=effective_total,
                populated_cells=populated_count,
                null_cells=null_cells,
                nullability_ratio=nullability_ratio,
                null_marker_count=null_marker_count,
                merged_non_anchor_cells=merged_non_anchor_cells,
                category_counts=category_counts,
                inferred_type=t_pred_type,
                heuristic_support_score=support_score,
                is_ambiguous=False,
                ambiguity_reason=None,
                competing_types=competing,
                requires_human_review=False,
                sample_values=sample_values,
                formula_pattern=formula_pattern,
            )

        # Fallback: H >= 0.80 but support score penalized below 0.70 -> AMBIGUOUS
        return ColumnTypeProfile(
            col_index=col_idx,
            state=InferenceState.AMBIGUOUS,
            candidate_type=None,
            total_cells=total_cells,
            effective_cells=effective_total,
            populated_cells=populated_count,
            null_cells=null_cells,
            nullability_ratio=nullability_ratio,
            null_marker_count=null_marker_count,
            merged_non_anchor_cells=merged_non_anchor_cells,
            category_counts=category_counts,
            inferred_type=ColumnType.STRING,
            heuristic_support_score=support_score,
            is_ambiguous=True,
            ambiguity_reason=f"Support score below threshold ({support_score:.2f} < 0.70)",
            competing_types=competing,
            requires_human_review=True,
            sample_values=sample_values,
            formula_pattern=formula_pattern,
        )
