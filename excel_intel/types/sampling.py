"""Deterministic 2D Sampling Engine for Semantic Type Inference (M05).

Provides zone-constrained, bounded 2D sampling across SemanticZoneType.BODY
within spatial table regions. Strictly enforces the hard ceiling of 10,000 cells
per region while guaranteeing proportional representation across left, middle,
and right column bands, as well as head, middle, and tail row bands.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Sequence

from excel_intel.inspection.models import BoundingBox
from excel_intel.types.models import SamplingDiagnostics

MAX_CELL_BUDGET: int = 10_000
MAX_COL_BUDGET_STANDARD: int = 1_000
ULTRA_WIDE_COL_THRESHOLD: int = 100
ABSOLUTE_MAX_COLS: int = 10_000


def select_3band_indices(start: int, count: int, sample_target: int) -> list[int]:
    """Deterministically select sample_target 1-indexed coordinates from range [start, start + count - 1].

    Implements proportional band allocation:
    - 40% head/left band
    - 20% middle band
    - 40% tail/right band

    Guarantees:
    - Exactly min(count, sample_target) unique, strictly increasing indices.
    - Deterministic output across repeated invocations.
    - Both outer boundaries (start, start + count - 1) and middle elements are sampled.
    """
    if count <= 0 or sample_target <= 0:
        return []
    if count <= sample_target:
        return list(range(start, start + count))
    if sample_target == 1:
        return [start]
    if sample_target == 2:
        return [start, start + count - 1]

    # Target allocations
    n_first = max(1, int(math.floor(0.40 * sample_target)))
    n_mid = max(1, int(math.floor(0.20 * sample_target)))
    n_last = sample_target - n_first - n_mid
    if n_last < 1:
        n_last = 1
        n_first = max(1, sample_target - n_mid - n_last)

    # 1. First band [start, start + n_first - 1]
    first_band = list(range(start, start + n_first))

    # 2. Last band [start + count - n_last, start + count - 1]
    last_band = list(range(start + count - n_last, start + count))

    # 3. Middle band centered at mid_point
    mid_center = start + count // 2
    mid_start = mid_center - n_mid // 2
    # Ensure middle band does not overlap first_band or last_band if space permits
    if mid_start < start + n_first:
        mid_start = start + n_first
    if mid_start + n_mid > start + count - n_last:
        mid_start = max(start + n_first, start + count - n_last - n_mid)
    
    mid_band = list(range(mid_start, min(start + count - n_last, mid_start + n_mid)))

    combined = sorted(set(first_band + mid_band + last_band))

    # If set union resulted in fewer elements due to edge collisions, fill greedily with uniform step
    if len(combined) < sample_target:
        step = max(1, count // sample_target)
        for idx in range(start, start + count, step):
            if idx not in combined:
                combined.append(idx)
                if len(combined) >= sample_target:
                    break
        combined = sorted(set(combined))

    # Ensure exact length
    if len(combined) > sample_target:
        # Uniformly trim while keeping start and end
        if sample_target == 1:
            return [start]
        step = (len(combined) - 1) / (sample_target - 1)
        trimmed = [combined[int(round(i * step))] for i in range(sample_target)]
        return sorted(set(trimmed))

    return combined


def sample_body_coordinates(
    body_box: BoundingBox,
    *,
    cell_budget: int = MAX_CELL_BUDGET,
    hidden_rows: Optional[set[int]] = None,
    hidden_cols: Optional[set[int]] = None,
    merge_cells: Optional[Sequence[Any]] = None,
) -> tuple[list[int], list[int], SamplingDiagnostics]:
    """Deterministically compute 2D row and column sample indices for a table BODY bounding box.

    Strictly satisfies FR-1.8:
    - Hard cell budget ceiling: B_cells <= 10,000 cells per region.
    - For R rows and C cols in BODY:
      * If C > 10,000: C_sample = 10,000 and R_sample = 1.
      * Else if C > 100: C_sample = min(C, 1,000).
      * Else: C_sample = C.
      * If C <= 10,000: R_sample = min(R, floor(10,000 / C_sample)).
    - Proof: C_sample * R_sample <= 10,000 under all geometries.
    """
    total_rows = max(0, body_box.max_row - body_box.min_row + 1)
    total_cols = max(0, body_box.max_col - body_box.min_col + 1)

    if total_rows == 0 or total_cols == 0:
        diag = SamplingDiagnostics(
            total_rows=total_rows,
            total_cols=total_cols,
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
        return [], [], diag

    # Step 1: Column dimension budget
    if total_cols > ABSOLUTE_MAX_COLS:
        c_target = ABSOLUTE_MAX_COLS
        r_target = 1
    elif total_cols > ULTRA_WIDE_COL_THRESHOLD:
        c_target = min(total_cols, MAX_COL_BUDGET_STANDARD)
        r_target = min(total_rows, cell_budget // c_target)
    else:
        c_target = total_cols
        r_target = min(total_rows, cell_budget // c_target)

    # Safety clamps: ensure at least 1 row and 1 col if total > 0
    c_target = max(1, min(total_cols, c_target))
    r_target = max(1, min(total_rows, r_target))

    # Defensive guarantee: strictly never exceed cell_budget
    if c_target * r_target > cell_budget:
        r_target = max(1, cell_budget // c_target)

    # Step 2: 3-band deterministic selection
    sampled_col_indices = select_3band_indices(body_box.min_col, total_cols, c_target)
    sampled_row_indices = select_3band_indices(body_box.min_row, total_rows, r_target)

    sampled_rows = len(sampled_row_indices)
    sampled_cols = len(sampled_col_indices)
    sampled_cells = sampled_rows * sampled_cols

    assert sampled_cells <= cell_budget, (
        f"Internal sampling error: sampled_cells ({sampled_cells}) exceeded budget ({cell_budget})"
    )

    is_truncated = (sampled_rows < total_rows) or (sampled_cols < total_cols)
    truncation_details = None
    if is_truncated:
        truncation_details = (
            f"2D sampling cap applied: sampled {sampled_rows}/{total_rows} rows, "
            f"{sampled_cols}/{total_cols} cols ({sampled_cells}/{total_rows * total_cols} cells)."
        )

    # Diagnostics: count hidden rows/cols and merges intersecting body_box
    hidden_row_cnt = 0
    if hidden_rows:
        hidden_row_cnt = sum(
            1 for r in range(body_box.min_row, body_box.max_row + 1) if r in hidden_rows
        )

    hidden_col_cnt = 0
    if hidden_cols:
        hidden_col_cnt = sum(
            1 for c in range(body_box.min_col, body_box.max_col + 1) if c in hidden_cols
        )

    merged_cell_cnt = 0
    if merge_cells:
        for m in merge_cells:
            box = getattr(m, "box", None)
            if box is not None:
                if (
                    box.min_row <= body_box.max_row
                    and box.max_row >= body_box.min_row
                    and box.min_col <= body_box.max_col
                    and box.max_col >= body_box.min_col
                ):
                    merged_cell_cnt += 1

    diag = SamplingDiagnostics(
        total_rows=total_rows,
        total_cols=total_cols,
        sampled_rows=sampled_rows,
        sampled_cols=sampled_cols,
        sampled_cells=sampled_cells,
        is_truncated=is_truncated,
        truncation_details=truncation_details,
        sampled_row_indices=sampled_row_indices,
        sampled_col_indices=sampled_col_indices,
        hidden_row_count=hidden_row_cnt,
        hidden_col_count=hidden_col_cnt,
        merged_cell_count=merged_cell_cnt,
    )

    return sampled_row_indices, sampled_col_indices, diag
