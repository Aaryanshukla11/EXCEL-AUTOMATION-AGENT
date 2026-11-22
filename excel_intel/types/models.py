"""Immutable Data Contracts and Schemas for Semantic Type Inference (M05).

Defines frozen Pydantic v2 schemas modeling fine-grained value categories,
explicit inference states, sampling diagnostics, column type profiles, and
region type reports.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from excel_intel.core.types import ColumnType


class InferenceState(str, Enum):
    """Explicit state of column semantic type inference."""

    INFERRED = "INFERRED"                      # Clear predominant type (H >= 0.80, S >= 0.70)
    UNKNOWN = "UNKNOWN"                        # 100% empty, blank, or all null markers
    AMBIGUOUS = "AMBIGUOUS"                    # Low homogeneity (H < 0.80) or semantic ambiguity
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"    # Populated count below threshold (< 5)


class ValueCategory(str, Enum):
    """Fine-grained semantic value category."""

    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    CURRENCY = "CURRENCY"
    PERCENTAGE = "PERCENTAGE"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    FORMULA = "FORMULA"
    NULL = "NULL"
    ERROR = "ERROR"

    def to_column_type(self) -> ColumnType:
        """Map fine-grained semantic category to canonical M01 ColumnType."""
        if self in (ValueCategory.INTEGER,):
            return ColumnType.INTEGER
        if self in (ValueCategory.DECIMAL, ValueCategory.CURRENCY, ValueCategory.PERCENTAGE):
            return ColumnType.DECIMAL
        if self == ValueCategory.DATE:
            return ColumnType.DATE
        if self == ValueCategory.BOOLEAN:
            return ColumnType.BOOLEAN
        if self == ValueCategory.FORMULA:
            return ColumnType.FORMULA
        return ColumnType.STRING


class NormalizedValue(BaseModel):
    """Normalized value representation preserving formatting provenance."""

    raw_value: Any
    category: ValueCategory
    normalized_value: Any = None
    currency_symbol: Optional[str] = None
    is_accounting_negative: bool = False
    percentage_factor: Optional[float] = None
    format_code: Optional[str] = None
    is_date_serial: bool = False
    parsed_date: Optional[datetime.date] = None
    error_code: Optional[str] = None
    has_date_order_ambiguity: bool = False
    is_boolean_candidate: bool = False
    is_null_marker: bool = False
    null_marker_text: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class SamplingDiagnostics(BaseModel):
    """Diagnostics recording 2D sampling coverage and grid bounds."""

    total_rows: int = Field(ge=0, description="Total row count in evaluated zone")
    total_cols: int = Field(ge=0, description="Total column count in evaluated zone")
    sampled_rows: int = Field(ge=0, description="Number of rows deterministically sampled")
    sampled_cols: int = Field(ge=0, description="Number of columns deterministically sampled")
    sampled_cells: int = Field(ge=0, le=10000, description="Total sampled cells (hard cap: 10,000)")
    is_truncated: bool = False
    truncation_details: Optional[str] = None
    sampled_row_indices: list[int] = Field(default_factory=list)
    sampled_col_indices: list[int] = Field(default_factory=list)
    hidden_row_count: int = Field(default=0, ge=0)
    hidden_col_count: int = Field(default=0, ge=0)
    merged_cell_count: int = Field(default=0, ge=0)
    semantic_observation_count: Optional[int] = Field(
        default=None, ge=0, description="Total semantic observations (excluding non-anchor merged coordinates and blanks)"
    )

    model_config = ConfigDict(frozen=True)


class ColumnTypeProfile(BaseModel):
    """Detailed statistical profile of a single column within BODY zone."""

    col_index: int = Field(ge=1, le=16384, description="1-indexed column index")
    state: InferenceState = Field(description="Discrete architectural inference state")
    candidate_type: Optional[ColumnType] = Field(
        default=None,
        description="Verified semantic type; None if state is UNKNOWN or AMBIGUOUS.",
    )
    total_cells: int = Field(ge=0)
    effective_cells: int = Field(default=0, ge=0, description="Sampled coordinates excluding non-anchor merged coordinates")
    populated_cells: int = Field(ge=0)
    null_cells: int = Field(ge=0)
    nullability_ratio: float = Field(ge=0.0, le=1.0)
    null_marker_count: int = Field(default=0, ge=0, description="Count of observed textual null markers (e.g. '-', 'N/A')")
    merged_non_anchor_cells: int = Field(default=0, ge=0, description="Count of cells covered by non-anchor horizontal merges")
    category_counts: dict[str, int] = Field(default_factory=dict)
    inferred_type: ColumnType = Field(
        description="Projected M01 schema carrier; STRING for UNKNOWN, AMBIGUOUS, or INSUFFICIENT_DATA.",
    )
    heuristic_support_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic consistency/support score; not a calibrated probability.",
    )
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    competing_types: list[ValueCategory] = Field(default_factory=list)
    requires_human_review: bool = False
    sample_values: list[Any] = Field(default_factory=list)
    formula_pattern: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class RegionTypeReport(BaseModel):
    """Type inference report for an entire detected spatial table region."""

    region_id: str
    sheet_name: str
    body_row_start: int = Field(ge=1)
    body_row_end: int = Field(ge=1)
    body_col_start: int = Field(ge=1)
    body_col_end: int = Field(ge=1)
    columns: dict[int, ColumnTypeProfile] = Field(default_factory=dict)
    has_ambiguous_columns: bool = False
    sampling: SamplingDiagnostics
    is_tentative: bool = False

    model_config = ConfigDict(frozen=True)

    def to_m01_inferred_types(self) -> dict[int, ColumnType]:
        """Produce mapping of column index to ColumnType for M04 TableMetadata conversion."""
        return {col_idx: p.inferred_type for col_idx, p in self.columns.items()}
