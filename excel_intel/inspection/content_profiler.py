"""Bounded-Memory Streaming Content Profiler (M03).

Performs single-pass statistical profiling across streaming worksheet rows.
Collects cell density, column type distributions, formula density, populated bounding box,
and candidate region boundaries with strict O(C) spatial memory complexity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from excel_intel.inspection.models import (
    BoundingBox,
    ColumnProfile,
    LayoutClassification,
    SheetContentProfile,
)

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader

MAX_CANDIDATE_BLOCKS_PER_SHEET = 100
MAX_SAMPLE_HEAD_VALUES = 5


class PopulatedBlock:
    """Internal lightweight representation of a candidate contiguous row block."""

    def __init__(self, start_row: int) -> None:
        self.start_row = start_row
        self.end_row = start_row
        self.min_col: Optional[int] = None
        self.max_col: Optional[int] = None
        self.cell_count: int = 0
        self.row_widths: list[int] = []

    def add_row(self, row_idx: int, cols: list[int]) -> None:
        self.end_row = row_idx
        width = len(cols)
        self.cell_count += width
        if len(self.row_widths) < 100:
            self.row_widths.append(width)
        for c in cols:
            if self.min_col is None or c < self.min_col:
                self.min_col = c
            if self.max_col is None or c > self.max_col:
                self.max_col = c

    @property
    def box(self) -> Optional[BoundingBox]:
        if self.min_col is None or self.max_col is None:
            return None
        return BoundingBox(
            min_row=self.start_row,
            max_row=self.end_row,
            min_col=self.min_col,
            max_col=self.max_col,
        )


class ColumnAccumulator:
    """Lightweight accumulator for column statistics."""

    def __init__(self, col_index: int) -> None:
        self.col_index = col_index
        self.populated_count: int = 0
        self.blank_count: int = 0
        self.formula_count: int = 0
        self.type_counts: dict[str, int] = {
            "integer": 0,
            "float": 0,
            "string": 0,
            "date": 0,
            "boolean": 0,
            "error": 0,
        }
        self.head_values: list[Any] = []

    def record_cell(
        self, value: Any, formula: Optional[str], cell_type: Optional[str]
    ) -> None:
        if formula is not None:
            self.formula_count += 1

        if value is None or (isinstance(value, str) and value == ""):
            self.blank_count += 1
            return

        self.populated_count += 1
        if len(self.head_values) < MAX_SAMPLE_HEAD_VALUES:
            self.head_values.append(value)

        # Categorize value type
        t_str = self._detect_type(value, cell_type)
        self.type_counts[t_str] = self.type_counts.get(t_str, 0) + 1

    def _detect_type(self, val: Any, cell_type: Optional[str]) -> str:
        if cell_type == "e" or (isinstance(val, str) and val.startswith("#")):
            return "error"
        if isinstance(val, bool) or cell_type == "b":
            return "boolean"
        if cell_type == "d" or hasattr(val, "year"):
            return "date"
        if isinstance(val, int):
            return "integer"
        if isinstance(val, float):
            return "float"
        return "string"

    def to_profile(self) -> ColumnProfile:
        total = self.populated_count
        pred_type: Optional[str] = None
        homogeneity = 0.0
        if total > 0:
            best_type, count = max(self.type_counts.items(), key=lambda x: x[1])
            pred_type = best_type
            homogeneity = round(count / total, 4)

        return ColumnProfile(
            col_index=self.col_index,
            populated_count=self.populated_count,
            blank_count=self.blank_count,
            type_counts=dict(self.type_counts),
            predominant_type=pred_type,
            homogeneity_ratio=homogeneity,
            has_formulas=self.formula_count > 0,
            formula_count=self.formula_count,
        )


class ContentDistributionProfiler:
    """Consumes M02 streaming row chunks and generates bounded content profiles."""

    def __init__(self, reader: StreamingWorkbookReader) -> None:
        self.reader = reader
        self._last_blocks: dict[str, list[PopulatedBlock]] = {}

    def get_candidate_blocks(self, sheet_name: str) -> list[PopulatedBlock]:
        """Retrieve candidate blocks discovered during the profiling pass."""
        return self._last_blocks.get(sheet_name, [])

    def profile_sheet(
        self, sheet: Union[str, int], *, chunk_size: int = 1000
    ) -> SheetContentProfile:
        """Stream worksheet rows in a single pass and compute bounded summary profile.

        Args:
            sheet: Sheet name or 0-indexed position.
            chunk_size: Streaming chunk size (default 1000 rows).

        Returns:
            SheetContentProfile containing dimensions, column profiles, and layout classification.
        """
        if isinstance(sheet, int):
            names = self.reader.sheet_names
            if sheet < 0 or sheet >= len(names):
                raise ValueError(
                    f"Sheet index {sheet} out of range (0..{len(names)-1})"
                )
            sheet_name = names[sheet]
            sheet_index = sheet
        else:
            sheet_name = str(sheet)
            names = self.reader.sheet_names
            if sheet_name not in names:
                raise ValueError(f"Sheet '{sheet_name}' not found in workbook")
            sheet_index = names.index(sheet_name)

        col_accumulators: dict[int, ColumnAccumulator] = {}
        total_cells = 0
        populated_cells = 0
        empty_cells = 0
        formula_cells = 0
        error_cells = 0

        min_row: Optional[int] = None
        max_row: Optional[int] = None
        min_col: Optional[int] = None
        max_col: Optional[int] = None

        candidate_blocks: list[PopulatedBlock] = []
        current_block: Optional[PopulatedBlock] = None
        last_populated_row: Optional[int] = None

        # Single streaming pass over sheet chunks
        for chunk in self.reader.stream_sheet(sheet, chunk_size=chunk_size):
            for row_record in chunk:
                row_idx = row_record["row"]
                cells = row_record["cells"]
                if not cells:
                    continue

                row_cols: list[int] = []
                for cell in cells:
                    total_cells += 1
                    col_idx = cell["col"]
                    val = cell.get("value")
                    formula = cell.get("formula")
                    cell_type = cell.get("cell_type")

                    if col_idx not in col_accumulators:
                        col_accumulators[col_idx] = ColumnAccumulator(col_idx)

                    col_accumulators[col_idx].record_cell(val, formula, cell_type)

                    if formula is not None:
                        formula_cells += 1

                    if val is None or (isinstance(val, str) and val == ""):
                        empty_cells += 1
                    else:
                        populated_cells += 1
                        row_cols.append(col_idx)

                        if min_row is None or row_idx < min_row:
                            min_row = row_idx
                        if max_row is None or row_idx > max_row:
                            max_row = row_idx
                        if min_col is None or col_idx < min_col:
                            min_col = col_idx
                        if max_col is None or col_idx > max_col:
                            max_col = col_idx

                if row_cols:
                    # Row clustering: if gap of > 1 row between populated rows, break block
                    if last_populated_row is not None and row_idx > last_populated_row + 2:
                        if current_block is not None and len(candidate_blocks) < MAX_CANDIDATE_BLOCKS_PER_SHEET:
                            candidate_blocks.append(current_block)
                        current_block = PopulatedBlock(row_idx)
                    elif current_block is None:
                        current_block = PopulatedBlock(row_idx)

                    current_block.add_row(row_idx, row_cols)
                    last_populated_row = row_idx

        if current_block is not None and len(candidate_blocks) < MAX_CANDIDATE_BLOCKS_PER_SHEET:
            candidate_blocks.append(current_block)

        self._last_blocks[sheet_name] = candidate_blocks

        # Build final ColumnProfiles
        col_profiles: dict[int, ColumnProfile] = {
            c_idx: acc.to_profile() for c_idx, acc in sorted(col_accumulators.items())
        }

        # Actual bounding box
        actual_box: Optional[BoundingBox] = None
        if (
            min_row is not None
            and max_row is not None
            and min_col is not None
            and max_col is not None
        ):
            actual_box = BoundingBox(
                min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col
            )

        # Determine layout classification
        layout = self._classify_layout(populated_cells, actual_box, candidate_blocks)

        return SheetContentProfile(
            sheet_index=sheet_index,
            sheet_name=sheet_name,
            total_cells_visited=total_cells,
            populated_cell_count=populated_cells,
            empty_cell_count=empty_cells,
            formula_cell_count=formula_cells,
            error_cell_count=error_cells,
            min_row=min_row,
            max_row=max_row,
            min_col=min_col,
            max_col=max_col,
            actual_bounding_box=actual_box,
            column_profiles=col_profiles,
            layout_classification=layout,
        )

    def _classify_layout(
        self,
        populated_count: int,
        box: Optional[BoundingBox],
        blocks: list[PopulatedBlock],
    ) -> LayoutClassification:
        """Classify overall worksheet layout from observed facts and blocks."""
        if populated_count == 0 or box is None:
            return LayoutClassification.EMPTY

        # Bounding box density
        density = populated_count / max(1, box.cell_count)

        # Sparse Matrix: low density with dispersed coordinates
        if density < 0.15 and box.cell_count > 50:
            return LayoutClassification.SPARSE_MATRIX

        # Key-Value Grid: 2 columns, tall aspect ratio, labels in col 1, values in col 2
        if box.col_count == 2 and box.row_count >= 3:
            return LayoutClassification.KEY_VALUE_GRID

        if len(blocks) >= 2:
            return LayoutClassification.MULTI_TABLE

        # Irregular Composite: high row length variance (> 50% std/mean)
        if blocks:
            widths = blocks[0].row_widths
            if len(widths) >= 4:
                avg_w = sum(widths) / len(widths)
                variance = sum((w - avg_w) ** 2 for w in widths) / len(widths)
                if avg_w > 0 and (variance ** 0.5) / avg_w > 0.5:
                    return LayoutClassification.IRREGULAR_COMPOSITE

        return LayoutClassification.SINGLE_TABLE

