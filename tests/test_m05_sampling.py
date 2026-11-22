"""Unit tests for M05 Deterministic 2D Sampling."""

import pytest

from excel_intel.inspection.models import BoundingBox, DeclaredMergeCell
from excel_intel.types.sampling import (
    MAX_CELL_BUDGET,
    sample_body_coordinates,
    select_3band_indices,
)


class TestSamplingEngine:
    """Test suite verifying hard cell budget caps and 3-band coverage."""

    def test_3band_index_selection_coverage(self) -> None:
        # Selection of 10 from 100
        indices = select_3band_indices(start=1, count=100, sample_target=10)
        assert len(indices) == 10
        # Check start and end are preserved
        assert indices[0] == 1
        assert indices[-1] == 100
        # Check monotonic ordering
        assert indices == sorted(indices)
        # Check unique
        assert len(set(indices)) == 10
        # Check middle values are present
        has_mid = any(30 <= idx <= 70 for idx in indices)
        assert has_mid is True

    def test_sample_small_table_no_truncation(self) -> None:
        # 10 rows, 5 cols = 50 cells (well below 10,000)
        box = BoundingBox(min_row=2, max_row=11, min_col=1, max_col=5)
        rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)

        assert len(rows) == 10
        assert len(cols) == 5
        assert diag.sampled_cells == 50
        assert diag.is_truncated is False
        assert diag.truncation_details is None

    def test_sample_tall_table_bounded_budget(self) -> None:
        # 5 cols, 50,000 rows
        box = BoundingBox(min_row=2, max_row=50001, min_col=1, max_col=5)
        rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)

        assert len(cols) == 5
        # 10,000 / 5 = 2,000 rows
        assert len(rows) == 2000
        assert diag.sampled_cells == 10000
        assert diag.is_truncated is True
        assert "2D sampling cap applied" in str(diag.truncation_details)
        # Strict hard ceiling
        assert diag.sampled_cells <= MAX_CELL_BUDGET

    def test_sample_ultra_wide_table(self) -> None:
        # 200 cols, 1,000 rows
        box = BoundingBox(min_row=1, max_row=1000, min_col=1, max_col=200)
        rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)

        # C_sample = min(200, 1000) = 200
        assert len(cols) == 200
        # R_sample = min(1000, 10000 // 200) = 50
        assert len(rows) == 50
        assert diag.sampled_cells == 10000
        assert diag.sampled_cells <= MAX_CELL_BUDGET

    def test_sample_extreme_wide_table_exceeding_10k_cols(self) -> None:
        # 12,000 cols, 50 rows
        box = BoundingBox(min_row=1, max_row=50, min_col=1, max_col=12000)
        rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)

        # C_sample = 10,000, R_sample = 1
        assert len(cols) == 10000
        assert len(rows) == 1
        assert diag.sampled_cells == 10000
        assert diag.sampled_cells <= MAX_CELL_BUDGET

    def test_single_cell_bounding_box(self) -> None:
        # 1x1 table
        box = BoundingBox(min_row=1, max_row=1, min_col=1, max_col=1)
        rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)
        assert rows == [1]
        assert cols == [1]
        assert diag.sampled_cells == 1
        assert diag.total_rows == 1
        assert diag.total_cols == 1
        assert diag.is_truncated is False

    def test_zero_count_indices(self) -> None:
        assert select_3band_indices(start=1, count=0, sample_target=10) == []
        assert select_3band_indices(start=1, count=10, sample_target=0) == []

    def test_hidden_lines_and_merge_diagnostics(self) -> None:
        box = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=10)
        m = DeclaredMergeCell.from_ref("B2:C3")
        rows, cols, diag = sample_body_coordinates(
            box,
            hidden_rows={2, 3, 5},
            hidden_cols={1},
            merge_cells=[m],
        )
        assert diag.hidden_row_count == 3
        assert diag.hidden_col_count == 1
        assert diag.merged_cell_count == 1

    def test_combinatorial_sampling_budget_proof(self) -> None:
        """Prove that sampled cell count NEVER exceeds 10,000 across a wide grid of dimensions."""
        test_row_counts = [1, 2, 10, 50, 100, 200, 500, 1000, 5000, 10000, 50000, 1048576]
        test_col_counts = [1, 2, 5, 20, 50, 100, 200, 500, 1000, 5000, 10000, 16384]

        for r_count in test_row_counts:
            for c_count in test_col_counts:
                box = BoundingBox(min_row=1, max_row=r_count, min_col=1, max_col=c_count)
                rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)
                assert diag.sampled_cells <= MAX_CELL_BUDGET, (
                    f"Violation at {r_count}x{c_count}: {diag.sampled_cells} > {MAX_CELL_BUDGET}"
                )
                assert len(rows) * len(cols) == diag.sampled_cells
                assert len(rows) <= r_count
                assert len(cols) <= c_count

    def test_coverage_and_determinism_across_runs(self) -> None:
        """Verify first, middle, last coverage and deterministic output across repeated runs."""
        box = BoundingBox(min_row=10, max_row=10009, min_col=5, max_col=504)  # 10,000 rows, 500 cols

        run_results = []
        for _ in range(5):
            rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)
            run_results.append((rows, cols, diag.sampled_cells))

        # 1. Determinism
        first_r, first_c, first_cnt = run_results[0]
        for r, c, cnt in run_results[1:]:
            assert r == first_r, "Row sampling is non-deterministic"
            assert c == first_c, "Col sampling is non-deterministic"
            assert cnt == first_cnt

        # 2. First, middle, last coverage
        assert first_r[0] == 10  # First row
        assert first_r[-1] == 10009  # Last row
        mid_row = 10 + 10000 // 2
        assert any(abs(r - mid_row) <= 100 for r in first_r), "Middle row band not covered"

        assert first_c[0] == 5  # First col
        assert first_c[-1] == 504  # Last col
        mid_col = 5 + 500 // 2
        assert any(abs(c - mid_col) <= 10 for c in first_c), "Middle col band not covered"

    def test_zero_full_matrix_materialization(self) -> None:
        """Verify that high-dimensional bounds (Excel max 1,048,576 x 16,384) do not materialize a matrix."""
        import time

        box = BoundingBox(min_row=1, max_row=1048576, min_col=1, max_col=16384)
        t0 = time.perf_counter()
        rows, cols, diag = sample_body_coordinates(box, cell_budget=MAX_CELL_BUDGET)
        elapsed = time.perf_counter() - t0

        assert elapsed < 0.1, f"Sampling took too long ({elapsed:.3f}s), matrix may have been materialized"
        assert diag.sampled_cells <= MAX_CELL_BUDGET
        assert diag.total_rows == 1048576
        assert diag.total_cols == 16384
