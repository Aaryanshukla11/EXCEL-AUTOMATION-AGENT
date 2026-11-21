"""Immutable Data Contracts and Models for Workbook Inspection (M03).

Provides frozen Pydantic v2 schemas modeling declared OpenXML structural facts,
inferred structural region hypotheses, structural anomalies, and inspection reports.
Strictly separates declarative facts from heuristic inferences.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# =============================================================================
# Coordinate Utilities
# =============================================================================

_CELL_REF_REGEX = re.compile(r"^\$?([A-Za-z]+)\$?([0-9]+)$")


def col_letter_to_index(col_str: str) -> int:
    """Convert Excel column letter (e.g., 'A', 'Z', 'AA') to 1-indexed integer."""
    result = 0
    for char in col_str.upper():
        if not ("A" <= char <= "Z"):
            raise ValueError(f"Invalid column character in '{col_str}': {char}")
        result = result * 26 + (ord(char) - ord("A") + 1)
    if result < 1 or result > 16384:
        raise ValueError(f"Column index {result} out of Excel range (1..16384)")
    return result


def col_index_to_letter(col_idx: int) -> str:
    """Convert 1-indexed integer to Excel column letter."""
    if col_idx < 1 or col_idx > 16384:
        raise ValueError(f"Column index {col_idx} out of Excel range (1..16384)")
    result = []
    idx = col_idx
    while idx > 0:
        idx -= 1
        result.append(chr(ord("A") + (idx % 26)))
        idx //= 26
    return "".join(reversed(result))


def cell_ref_to_row_col(cell_ref: str) -> tuple[int, int]:
    """Parse cell reference (e.g. 'A1', '$B$10') into 1-indexed (row, col)."""
    clean_ref = cell_ref.replace("$", "").strip()
    match = _CELL_REF_REGEX.match(clean_ref)
    if not match:
        raise ValueError(f"Invalid cell reference: '{cell_ref}'")
    col_str, row_str = match.groups()
    row = int(row_str)
    col = col_letter_to_index(col_str)
    if row < 1 or row > 1048576:
        raise ValueError(f"Row {row} out of Excel range (1..1048576)")
    return row, col


def row_col_to_cell_ref(row: int, col: int) -> str:
    """Format 1-indexed (row, col) into standard A1 cell reference."""
    if row < 1 or row > 1048576:
        raise ValueError(f"Row {row} out of Excel range (1..1048576)")
    col_str = col_index_to_letter(col)
    return f"{col_str}{row}"


# =============================================================================
# Enums
# =============================================================================


class SheetVisibility(str, Enum):
    """OpenXML sheet visibility state."""

    VISIBLE = "visible"
    HIDDEN = "hidden"
    VERY_HIDDEN = "veryHidden"


class AnomalySeverity(str, Enum):
    """Severity level of structural anomalies."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RegionType(str, Enum):
    """Categorization of inferred structural worksheet regions."""

    TABULAR_DATA = "tabular_data"
    KEY_VALUE_BLOCK = "key_value_block"
    METADATA_HEADER = "metadata_header"
    SUMMARY_STATISTICS = "summary_statistics"
    MATRIX_OR_CROSS_TAB = "matrix_or_cross_tab"
    IRREGULAR_GRID = "irregular_grid"


class LayoutClassification(str, Enum):
    """Overall worksheet layout classification."""

    EMPTY = "EMPTY"
    SINGLE_TABLE = "SINGLE_TABLE"
    MULTI_TABLE = "MULTI_TABLE"
    KEY_VALUE_GRID = "KEY_VALUE_GRID"
    SPARSE_MATRIX = "SPARSE_MATRIX"
    IRREGULAR_COMPOSITE = "IRREGULAR_COMPOSITE"


class RegionRole(str, Enum):
    """Functional role of an identified structural region."""

    DECLARED_LIST_OBJECT = "declared_list_object"
    INFERRED_TABULAR_CANDIDATE = "inferred_tabular_candidate"
    KEY_VALUE_BLOCK = "key_value_block"
    TITLE_BANNER = "title_banner"
    SUMMARY_FOOTER = "summary_footer"
    SPARSE_ISLAND = "sparse_island"


class EvidenceCode(str, Enum):
    """Standardized deterministic evidence codes supporting region hypotheses."""

    HOMOGENEOUS_TYPE = "HOMOGENEOUS_TYPE"
    HEADER_CONTRAST = "HEADER_CONTRAST"
    BOUNDARY_SEPARATION = "BOUNDARY_SEPARATION"
    DENSE_CELL_CLUSTER = "DENSE_CELL_CLUSTER"
    LIST_OBJECT_DECLARED = "LIST_OBJECT_DECLARED"
    TOTALS_ROW_DETECTED = "TOTALS_ROW_DETECTED"
    REPEATED_HEADER_PATTERN = "REPEATED_HEADER_PATTERN"
    EMPTY_MARGIN_ISOLATION = "EMPTY_MARGIN_ISOLATION"


# =============================================================================
# Spatial Bounding Models
# =============================================================================


class BoundingBox(BaseModel):
    """Immutable 1-indexed coordinate bounding box in an Excel grid."""

    min_row: int = Field(ge=1, le=1048576, description="Minimum 1-indexed row")
    max_row: int = Field(ge=1, le=1048576, description="Maximum 1-indexed row")
    min_col: int = Field(ge=1, le=16384, description="Minimum 1-indexed column")
    max_col: int = Field(ge=1, le=16384, description="Maximum 1-indexed column")

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_bounds(self) -> BoundingBox:
        if self.min_row > self.max_row:
            raise ValueError(
                f"min_row ({self.min_row}) cannot exceed max_row ({self.max_row})"
            )
        if self.min_col > self.max_col:
            raise ValueError(
                f"min_col ({self.min_col}) cannot exceed max_col ({self.max_col})"
            )
        return self

    @property
    def row_count(self) -> int:
        """Total rows spanned by this bounding box."""
        return self.max_row - self.min_row + 1

    @property
    def col_count(self) -> int:
        """Total columns spanned by this bounding box."""
        return self.max_col - self.min_col + 1

    @property
    def cell_count(self) -> int:
        """Total cells enclosed in this rectangular area."""
        return self.row_count * self.col_count

    def to_a1_ref(self) -> str:
        """Return canonical A1 reference string, e.g. 'A1:D10' or 'A1'."""
        top_left = row_col_to_cell_ref(self.min_row, self.min_col)
        bottom_right = row_col_to_cell_ref(self.max_row, self.max_col)
        if top_left == bottom_right:
            return top_left
        return f"{top_left}:{bottom_right}"

    def contains_coord(self, row: int, col: int) -> bool:
        """Return True if (row, col) is inside this bounding box."""
        return (
            self.min_row <= row <= self.max_row
            and self.min_col <= col <= self.max_col
        )

    def intersects(self, other: BoundingBox) -> bool:
        """Return True if this bounding box overlaps with another."""
        return not (
            self.max_row < other.min_row
            or self.min_row > other.max_row
            or self.max_col < other.min_col
            or self.min_col > other.max_col
        )

    @classmethod
    def from_a1_ref(cls, ref: str) -> BoundingBox:
        """Construct BoundingBox from an A1 or range reference (e.g. 'A1:C10')."""
        clean_ref = ref.replace("$", "").strip()
        if ":" in clean_ref:
            parts = clean_ref.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid range reference: '{ref}'")
            r1, c1 = cell_ref_to_row_col(parts[0])
            r2, c2 = cell_ref_to_row_col(parts[1])
            return cls(
                min_row=min(r1, r2),
                max_row=max(r1, r2),
                min_col=min(c1, c2),
                max_col=max(c1, c2),
            )
        else:
            r, c = cell_ref_to_row_col(clean_ref)
            return cls(min_row=r, max_row=r, min_col=c, max_col=c)


class HiddenInterval(BaseModel):
    """1-indexed interval of consecutive hidden rows or columns."""

    dimension: str = Field(description="'row' or 'col'")
    start: int = Field(ge=1, description="1-indexed starting index")
    end: int = Field(ge=1, description="1-indexed ending index")

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_interval(self) -> HiddenInterval:
        if self.dimension not in ("row", "col"):
            raise ValueError(f"dimension must be 'row' or 'col', got '{self.dimension}'")
        if self.start > self.end:
            raise ValueError(
                f"start ({self.start}) cannot exceed end ({self.end})"
            )
        return self

    @property
    def count(self) -> int:
        """Number of items hidden in this interval."""
        return self.end - self.start + 1


# =============================================================================
# Declared OpenXML Facts (Deterministic, Zero Probabilities)
# =============================================================================


class DeclaredSheetProperties(BaseModel):
    """Declared worksheet-level properties from workbook XML."""

    sheet_id: int = Field(description="Unique positive OpenXML sheetId")
    name: str = Field(description="Display sheet name")
    visibility: SheetVisibility = Field(default=SheetVisibility.VISIBLE)
    declared_dimension_ref: Optional[str] = Field(
        default=None, description="Raw ref string from <dimension> element"
    )
    declared_dimension_box: Optional[BoundingBox] = Field(
        default=None, description="Parsed BoundingBox of declared dimension"
    )
    tab_color_rgb: Optional[str] = Field(
        default=None, description="Hex RGB color of sheet tab if declared"
    )

    model_config = ConfigDict(frozen=True)


class DeclaredMergeCell(BaseModel):
    """Merged cell range explicitly declared in worksheet XML."""

    ref: str = Field(description="Range reference, e.g. 'A1:C1'")
    box: BoundingBox = Field(description="Parsed bounding box of merged range")
    top_left_cell: str = Field(description="Top-left anchor cell, e.g. 'A1'")

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_ref(cls, ref: str) -> DeclaredMergeCell:
        box = BoundingBox.from_a1_ref(ref)
        top_left = row_col_to_cell_ref(box.min_row, box.min_col)
        return cls(ref=ref, box=box, top_left_cell=top_left)


class DeclaredListObject(BaseModel):
    """Declared Excel Table (ListObject) from xl/tables/table*.xml."""

    id: int = Field(description="Table ID attribute")
    name: str = Field(description="Table internal name")
    display_name: str = Field(description="Table UI display name")
    ref: str = Field(description="Grid range reference, e.g. 'A1:E50'")
    box: BoundingBox = Field(description="Parsed table bounding box")
    header_row_count: int = Field(default=1, ge=0)
    totals_row_count: int = Field(default=0, ge=0)
    column_names: list[str] = Field(default_factory=list)
    has_auto_filter: bool = Field(default=False)
    auto_filter_ref: Optional[str] = Field(default=None)

    model_config = ConfigDict(frozen=True)


class DeclaredDefinedName(BaseModel):
    """Declared OpenXML defined name / named range from workbook XML."""

    name: str = Field(description="Defined name string")
    value: str = Field(description="Formula, cell reference, or constant value")
    local_sheet_id: Optional[int] = Field(
        default=None, description="0-indexed sheet scope ID, or None for workbook scope"
    )
    scope: str = Field(
        default="workbook", description="'workbook' or sheet name"
    )
    comment: Optional[str] = Field(default=None)
    is_hidden: bool = Field(default=False)

    model_config = ConfigDict(frozen=True)


class DeclaredOpenXmlFacts(BaseModel):
    """Exhaustive collection of deterministic OpenXML facts for a worksheet.

    Contains NO heuristic inferences or probabilistic scores.
    """

    properties: DeclaredSheetProperties
    declared_dimension: Optional[BoundingBox] = None
    merge_cells: list[DeclaredMergeCell] = Field(default_factory=list)
    list_objects: list[DeclaredListObject] = Field(default_factory=list)
    hidden_rows: list[HiddenInterval] = Field(default_factory=list)
    hidden_columns: list[HiddenInterval] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


# =============================================================================
# Inferred Region Hypotheses & Structural Anomalies
# =============================================================================


class InferredRegionHypothesis(BaseModel):
    """Heuristic structural hypothesis with transparent, normalized confidence."""

    hypothesis_id: str = Field(description="Unique identifier for this hypothesis")
    region_type: RegionType = Field(description="Inferred classification of the region")
    role: RegionRole = Field(
        default=RegionRole.INFERRED_TABULAR_CANDIDATE,
        description="Functional role of the candidate region",
    )
    box: BoundingBox = Field(description="Grid bounding box of the hypothesis")
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Normalized heuristic score between 0.0 and 1.0"
    )
    parent_hypothesis_id: Optional[str] = Field(
        default=None, description="ID of parent container region if nested"
    )
    evidence_codes: list[EvidenceCode] = Field(
        default_factory=list, description="Standardized evidence codes"
    )
    evidence_descriptions: list[str] = Field(
        default_factory=list, description="Human-readable supporting evidence"
    )
    deduction_penalties: list[str] = Field(
        default_factory=list, description="Penalties deducted from confidence"
    )
    source_provenance: str = Field(
        default="heuristic_inference", description="Origin of this hypothesis"
    )

    model_config = ConfigDict(frozen=True)


# Canonical alias for compatibility
RegionHypothesis = InferredRegionHypothesis


class ColumnProfile(BaseModel):
    """Summary statistics for a single column discovered during streaming."""

    col_index: int = Field(ge=1, description="1-indexed column position")
    populated_count: int = Field(default=0, ge=0)
    blank_count: int = Field(default=0, ge=0)
    type_counts: dict[str, int] = Field(default_factory=dict)
    predominant_type: Optional[str] = None
    homogeneity_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    has_formulas: bool = False
    formula_count: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)


class SheetContentProfile(BaseModel):
    """Bounded-memory summary profile of worksheet cell contents."""

    sheet_index: int = Field(ge=0)
    sheet_name: str
    total_cells_visited: int = Field(default=0, ge=0)
    populated_cell_count: int = Field(default=0, ge=0)
    empty_cell_count: int = Field(default=0, ge=0)
    formula_cell_count: int = Field(default=0, ge=0)
    error_cell_count: int = Field(default=0, ge=0)
    min_row: Optional[int] = None
    max_row: Optional[int] = None
    min_col: Optional[int] = None
    max_col: Optional[int] = None
    actual_bounding_box: Optional[BoundingBox] = None
    column_profiles: dict[int, ColumnProfile] = Field(default_factory=dict)
    layout_classification: LayoutClassification = LayoutClassification.EMPTY

    model_config = ConfigDict(frozen=True)


class StructuralAnomaly(BaseModel):
    """Detected structural irregularity, inconsistency, or defect."""

    anomaly_id: str = Field(description="Unique identifier for this anomaly")
    severity: AnomalySeverity = Field(description="Severity classification")
    code: str = Field(description="Standardized anomaly code, e.g. 'ANOM_MIXED_TYPE'")
    message: str = Field(description="Detailed explanation of the detected anomaly")
    cell_ref: Optional[str] = Field(default=None, description="A1 coordinate if localized")
    box: Optional[BoundingBox] = Field(
        default=None, description="Affected bounding box if rectangular"
    )
    evidence: Optional[str] = Field(default=None, description="Diagnostic evidence")

    model_config = ConfigDict(frozen=True)


# =============================================================================
# Inspection Reports
# =============================================================================


class SheetInspectionReport(BaseModel):
    """Complete inspection report for an individual worksheet."""

    sheet_index: int = Field(ge=0, description="0-indexed position in workbook")
    sheet_name: str = Field(description="Name of the worksheet")
    facts: DeclaredOpenXmlFacts = Field(
        description="Deterministic declared OpenXML facts"
    )
    profile: Optional[SheetContentProfile] = Field(
        default=None, description="Streaming content profile if computed"
    )
    layout_classification: LayoutClassification = Field(
        default=LayoutClassification.EMPTY,
        description="Overall structural layout classification",
    )
    region_hypotheses: list[InferredRegionHypothesis] = Field(
        default_factory=list, description="Inferred structural region candidates"
    )
    anomalies: list[StructuralAnomaly] = Field(
        default_factory=list, description="Sheet-level structural anomalies"
    )
    actual_cell_count: Optional[int] = Field(
        default=None, description="Populated cells discovered during inspection"
    )

    model_config = ConfigDict(frozen=True)


class WorkbookInspectionReport(BaseModel):
    """Top-level immutable workbook inspection report."""

    workbook_path: str = Field(description="Source workbook file path")
    package_type: str = Field(description="'xlsx' or 'xlsm'")
    is_1904: bool = Field(description="True if workbook uses 1904 date system")
    has_macros: bool = Field(description="True if VBA macro container present")
    calc_pr: dict[str, Any] = Field(
        default_factory=dict, description="Workbook calculation properties"
    )
    defined_names: list[DeclaredDefinedName] = Field(
        default_factory=list, description="Workbook and sheet-scoped defined names"
    )
    sheets: list[SheetInspectionReport] = Field(
        default_factory=list, description="Individual sheet inspection reports"
    )
    workbook_anomalies: list[StructuralAnomaly] = Field(
        default_factory=list, description="Package-level or cross-sheet anomalies"
    )
    inspection_timestamp: str = Field(
        description="ISO 8601 UTC timestamp of inspection completion"
    )

    model_config = ConfigDict(frozen=True)
