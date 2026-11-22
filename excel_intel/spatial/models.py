"""Immutable Data Contracts and Models for Spatial Detection (M04).

Provides frozen Pydantic v2 schemas modeling two-dimensional spatial regions,
separation corridors, spatial evidence, and detection reports.
Preserves strict 1-indexed Excel coordinates and immutable semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from excel_intel.inspection.models import BoundingBox

if TYPE_CHECKING:
    from excel_intel.core.types import ColumnMetadata, TableMetadata


# =============================================================================
# Enums
# =============================================================================


class SpatialRegionType(str, Enum):
    """Categorization of detected two-dimensional spatial regions."""

    DECLARED_TABLE = "declared_table"
    INFERRED_TABLE = "inferred_table"
    KEY_VALUE_GRID = "key_value_grid"
    SPARSE_ISLAND = "sparse_island"
    IRREGULAR_COMPOSITE = "irregular_composite"


class SpatialEvidenceType(str, Enum):
    """Provenance and structural rationale supporting a spatial region."""

    DECLARED_OPENXML = "DECLARED_OPENXML"
    VERTICAL_CORRIDOR_ISOLATION = "VERTICAL_CORRIDOR_ISOLATION"
    HORIZONTAL_CORRIDOR_ISOLATION = "HORIZONTAL_CORRIDOR_ISOLATION"
    DENSE_CELL_CLUSTER = "DENSE_CELL_CLUSTER"
    M03_HYPOTHESIS_CORROBORATION = "M03_HYPOTHESIS_CORROBORATION"
    NESTED_PARENT = "NESTED_PARENT"
    OVERLAPPING_INTERSECTION = "OVERLAPPING_INTERSECTION"
    LOOKAHEAD_CONTINUATION = "LOOKAHEAD_CONTINUATION"
    SINGLE_ROW_HEADER = "SINGLE_ROW_HEADER"
    HIERARCHICAL_STACKED_HEADER = "HIERARCHICAL_STACKED_HEADER"
    MERGED_HEADER_OVERLAY = "MERGED_HEADER_OVERLAY"
    TITLE_BANNER_EXCLUDED = "TITLE_BANNER_EXCLUDED"
    SUMMARY_ROW_EXCLUDED = "SUMMARY_ROW_EXCLUDED"
    NO_HEADER_DETECTED = "NO_HEADER_DETECTED"
    AMBIGUOUS_HEADER_STRUCTURE = "AMBIGUOUS_HEADER_STRUCTURE"
    HEADER_RESOURCE_LIMIT = "HEADER_RESOURCE_LIMIT"
    ZONE_TITLE_DETECTED = "ZONE_TITLE_DETECTED"
    ZONE_HEADER_DETECTED = "ZONE_HEADER_DETECTED"
    ZONE_BODY_DETECTED = "ZONE_BODY_DETECTED"
    ZONE_SUMMARY_DETECTED = "ZONE_SUMMARY_DETECTED"
    ZONE_TOTALS_DETECTED = "ZONE_TOTALS_DETECTED"
    ZONE_FOOTNOTES_DETECTED = "ZONE_FOOTNOTES_DETECTED"
    INTERLEAVED_SUBHEADER = "INTERLEAVED_SUBHEADER"
    BOUNDARY_COLLISION_DETECTED = "BOUNDARY_COLLISION_DETECTED"
    BOUNDARY_SAFE_CLEARANCE = "BOUNDARY_SAFE_CLEARANCE"
    TRAILING_FORMULA_COLLISION = "TRAILING_FORMULA_COLLISION"
    CROSS_BOUNDARY_MERGE = "CROSS_BOUNDARY_MERGE"
    OVERLAPPING_REGION_WARNING = "OVERLAPPING_REGION_WARNING"


class CorridorOrientation(str, Enum):
    """Orientation of a blank separation corridor between spatial regions."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


# =============================================================================
# Evidence & Corridor Models
# =============================================================================


class SpatialEvidence(BaseModel):
    """Deterministic structural evidence supporting a spatial region boundary."""

    evidence_type: SpatialEvidenceType
    description: str
    heuristic_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic structural confidence score in [0.0, 1.0]; not a calibrated probability.",
    )
    provenance: str = Field(
        description="Source or pipeline component that generated this evidence."
    )
    coordinates: Optional[BoundingBox] = None

    model_config = ConfigDict(frozen=True)


class SeparationCorridor(BaseModel):
    """A contiguous blank corridor separating distinct spatial regions."""

    orientation: CorridorOrientation
    start_index: int = Field(ge=1, le=1048576, description="1-indexed starting row or column")
    end_index: int = Field(ge=1, le=1048576, description="1-indexed ending row or column")
    width: int = Field(ge=1, description="Number of contiguous blank rows or columns")
    span_min: int = Field(ge=1, le=1048576, description="Orthogonal start coordinate")
    span_max: int = Field(ge=1, le=1048576, description="Orthogonal end coordinate")

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_bounds(self) -> SeparationCorridor:
        if self.start_index > self.end_index:
            raise ValueError(
                f"start_index ({self.start_index}) cannot exceed end_index ({self.end_index})"
            )
        if self.span_min > self.span_max:
            raise ValueError(
                f"span_min ({self.span_min}) cannot exceed span_max ({self.span_max})"
            )
        expected_width = self.end_index - self.start_index + 1
        if self.width != expected_width:
            raise ValueError(
                f"width ({self.width}) does not match index span ({expected_width})"
            )
        return self


# =============================================================================
# Spatial Region & Report Models
# =============================================================================


class HeaderResolutionStatus(str, Enum):
    """Categorization of hierarchical header resolution outcomes."""

    HIGH_CONFIDENCE = "high_confidence"
    TENTATIVE = "tentative"
    AMBIGUOUS = "ambiguous"
    NO_HEADER_DETECTED = "no_header_detected"
    INCOMPLETE_RESOURCE_LIMIT = "incomplete_resource_limit"


class HeaderHierarchyLevel(BaseModel):
    """Single level within a multi-row hierarchical header column."""

    row_index: int = Field(ge=1, le=1048576, description="1-indexed row number")
    col_index: int = Field(ge=1, le=16384, description="1-indexed column number")
    raw_value: str = Field(description="Raw cell value string as stored in worksheet")
    is_merged: bool = Field(default=False, description="True if value originated from a merged range overlay")
    merge_range_ref: Optional[str] = Field(default=None, description="OpenXML merged range ref if applicable")

    model_config = ConfigDict(frozen=True) 


class ResolvedHeaderColumn(BaseModel):
    """Resolved column header with hierarchical path, provenance, and coordinates."""

    col_index: int = Field(ge=1, le=16384, description="1-indexed column number")
    resolved_name: str = Field(description="Resolved compound header name (e.g. 'Financials -> Revenue')")
    raw_name: str = Field(description="Original leaf cell value before compounding")
    hierarchy_levels: list[HeaderHierarchyLevel] = Field(default_factory=list)
    depth: int = Field(ge=1, default=1, description="Hierarchy depth (number of stacked levels)")
    is_duplicate: bool = Field(default=False, description="True if name collided with another column in same region")
    disambiguated_name: Optional[str] = Field(
        default=None, description="Unique disambiguated name if duplicate (e.g. 'Revenue_2')"
    )
    source_coordinate: str = Field(description="A1 cell reference of the leaf header cell")

    model_config = ConfigDict(frozen=True)

    def to_column_metadata(
        self,
        inferred_type: Any,
        type_confidence: float = 1.0,
        nullable: bool = True,
    ) -> ColumnMetadata:
        """Convert to M01 ColumnMetadata with caller-supplied verified type."""
        from excel_intel.core.types import ColumnMetadata, ColumnType

        if isinstance(inferred_type, str):
            inferred_type = ColumnType(inferred_type)

        return ColumnMetadata(
            index=self.col_index,
            header_name=self.disambiguated_name or self.resolved_name,
            inferred_type=inferred_type,
            type_confidence=type_confidence,
            nullable=nullable,
        )


class HeaderResolutionReport(BaseModel):
    """Structured result of hierarchical header resolution for a spatial region."""

    region_id: str
    sheet_name: str
    status: HeaderResolutionStatus
    header_row_start: Optional[int] = Field(default=None, ge=1)
    header_row_end: Optional[int] = Field(default=None, ge=1)
    header_row_count: int = Field(default=0, ge=0)
    columns: list[ResolvedHeaderColumn] = Field(default_factory=list)
    heuristic_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic structural confidence in [0.0, 1.0]; not a calibrated probability.",
    )
    evidence: list[SpatialEvidence] = Field(default_factory=list)
    is_ambiguous: bool = Field(default=False)
    ambiguity_details: Optional[str] = Field(default=None)
    delimiter_used: str = Field(default=" -> ")
    is_truncated: bool = Field(default=False)
    truncation_details: Optional[str] = Field(default=None)

    model_config = ConfigDict(frozen=True)

    def to_column_metadata_list(
        self,
        inferred_types: Optional[dict[int, Any]] = None,
    ) -> list[ColumnMetadata]:
        """Convert resolved headers to M01 ColumnMetadata list.

        Args:
            inferred_types: Mapping from 1-indexed column index to ColumnType.
                Must be provided for every column. Fabricating placeholder types is disallowed.

        Raises:
            NotImplementedError: If inferred_types is missing or incomplete.
        """
        if inferred_types is None:
            raise NotImplementedError(
                "Lossless conversion to M01 ColumnMetadata requires verified column data types; "
                "HeaderResolutionReport refuses to fabricate unverified types."
            )
        col_meta_list = []
        for col in self.columns:
            if col.col_index not in inferred_types:
                raise NotImplementedError(
                    f"Column index {col.col_index} ('{col.resolved_name}') missing from verified types."
                )
            col_meta_list.append(
                col.to_column_metadata(inferred_types[col.col_index])
            )
        return col_meta_list


# =============================================================================
# Semantic Zones & Boundary Sentinel Models
# =============================================================================


class SemanticZoneType(str, Enum):
    """Categorization of semantic sub-zones within a spatial table region."""

    TITLE = "TITLE"
    HEADER = "HEADER"
    BODY = "BODY"
    SUMMARY = "SUMMARY"
    TOTALS = "TOTALS"
    FOOTNOTES = "FOOTNOTES"
    UNKNOWN = "UNKNOWN"

    # Aliases for plan document compatibility
    TITLE_BANNER = "TITLE"
    COLUMN_HEADER = "HEADER"
    DATA_BODY = "BODY"
    SUMMARY_TOTALS = "SUMMARY"


RegionZoneType = SemanticZoneType


class SemanticZone(BaseModel):
    """Discrete semantic zone within a detected tabular region."""

    zone_type: SemanticZoneType
    bounding_box: BoundingBox
    row_count: int = Field(ge=0)
    cell_count: int = Field(ge=0)
    populated_cell_count: int = Field(default=0, ge=0)
    heuristic_confidence: float = Field(
        ge=0.0,
        le=1.0,
        default=1.0,
        description="Heuristic structural confidence score in [0.0, 1.0]; not a calibrated probability.",
    )
    evidence: list[SpatialEvidence] = Field(default_factory=list)
    details: Optional[str] = None

    model_config = ConfigDict(frozen=True)


RegionZone = SemanticZone


class MarginClearance(BaseModel):
    """ADR-005 clearance evaluation for append operations."""

    spare_rows_below: int = Field(ge=0, description="Count of empty rows immediately below table before next occupied row")
    has_zero_space_collision: bool = Field(default=False, description="True if 0 spare rows below ordinary range")
    has_trailing_formulas: bool = Field(default=False, description="True if formula exists immediately below table")
    adjacent_formulas: list[str] = Field(default_factory=list, description="Formula expressions detected in boundary zone")
    colliding_row_indices: list[int] = Field(default_factory=list, description="Row indices causing collision")
    safe_for_append: bool = Field(default=True, description="True if table is safe for automated record append under ADR-005")
    collision_reason: Optional[str] = Field(default=None, description="Detailed reason if safe_for_append is False")
    evidence: list[SpatialEvidence] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class SpatialTableRegion(BaseModel):
    """A bounded two-dimensional rectangular tabular entity."""

    region_id: str = Field(description="Deterministic stable region identifier")
    sheet_name: str
    bounding_box: BoundingBox
    region_type: SpatialRegionType
    is_declared: bool = Field(
        default=False,
        description="True if region is backed by an OpenXML ListObject declaration",
    )
    declared_name: Optional[str] = Field(
        default=None,
        description="OpenXML declared table name if is_declared is True",
    )
    heuristic_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Heuristic structural confidence score in [0.0, 1.0]; not a calibrated probability.",
    )
    evidence: list[SpatialEvidence] = Field(default_factory=list)
    parent_region_id: Optional[str] = Field(
        default=None,
        description="ID of enclosing region if this region is nested",
    )
    child_region_ids: list[str] = Field(
        default_factory=list,
        description="IDs of enclosed sub-regions if this region contains nested blocks",
    )
    overlapping_region_ids: list[str] = Field(
        default_factory=list,
        description="IDs of regions that partially overlap this region",
    )
    cell_count: int = Field(ge=0, description="Total rectangular grid area (rows * cols)")
    populated_cell_count: int = Field(ge=0, description="Count of non-empty cells")
    density: float = Field(
        ge=0.0,
        le=1.0,
        description="Ratio of populated cells to total rectangular area",
    )
    header_row: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-indexed row number of detected column headers (populated by header resolver)",
    )
    columns: Optional[list[Any]] = Field(
        default=None,
        description="Resolved column metadata when available",
    )
    header_resolution: Optional[HeaderResolutionReport] = Field(
        default=None,
        description="Resolved hierarchical header analysis if performed",
    )
    zones: dict[SemanticZoneType, SemanticZone] = Field(
        default_factory=dict,
        description="Discrete semantic zones (TITLE, HEADER, BODY, SUMMARY, TOTALS, FOOTNOTES) decomposed in this region",
    )
    zone_list: list[SemanticZone] = Field(
        default_factory=list,
        description="Ordered list of all semantic zones identified within this region",
    )
    margin: Optional[MarginClearance] = Field(
        default=None,
        description="ADR-005 append boundary margin clearance evaluation if computed",
    )
    subheaders: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Interleaved section subheaders detected within the data body",
    )

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_region(self) -> SpatialTableRegion:
        if self.populated_cell_count > self.cell_count:
            raise ValueError(
                f"populated_cell_count ({self.populated_cell_count}) cannot exceed cell_count ({self.cell_count})"
            )
        if self.cell_count > 0:
            expected_density = round(self.populated_cell_count / self.cell_count, 4)
            if abs(self.density - expected_density) > 0.01:
                raise ValueError(
                    f"density ({self.density}) does not match populated/total ratio ({expected_density})"
                )
        return self

    def to_table_metadata(self) -> TableMetadata:
        """Convert to M01 canonical TableMetadata if required information is present.

        Raises:
            NotImplementedError: If header_row or columns are unresolved.
                M04 Prompt 2 does not fabricate missing column types or header rows.
        """
        if self.header_row is None or not self.columns:
            raise NotImplementedError(
                "Lossless conversion to TableMetadata requires resolved header_row and column metadata; "
                "M04 Prompt 2 segmenter output does not fabricate unverified column types or header rows."
            )

        from excel_intel.core.types import BoundingBox as M01BoundingBox, TableMetadata

        m01_box = M01BoundingBox(
            start_row=self.bounding_box.min_row,
            start_col=self.bounding_box.min_col,
            end_row=self.bounding_box.max_row,
            end_col=self.bounding_box.max_col,
        )

        return TableMetadata(
            sheet_name=self.sheet_name,
            bounding_box=m01_box,
            header_row=self.header_row,
            columns=self.columns,
            is_list_object=self.is_declared,
            list_object_name=self.declared_name,
        )


class SpatialDetectionReport(BaseModel):
    """Complete spatial detection report for a worksheet."""

    workbook_path: str
    sheet_name: str
    regions: list[SpatialTableRegion] = Field(default_factory=list)
    sparse_islands: list[SpatialTableRegion] = Field(default_factory=list)
    corridors_detected: list[SeparationCorridor] = Field(default_factory=list)
    lookahead_window_size: int = Field(default=50, ge=1)
    lookahead_overflow_detected: bool = False
    lookahead_overflow_details: Optional[str] = None
    total_populated_cells_evaluated: int = Field(ge=0, default=0)
    is_truncated: bool = Field(
        default=False,
        description="True if output regions, islands, or corridors were truncated by resource limits.",
    )
    truncation_details: Optional[str] = Field(
        default=None,
        description="Human-readable description of truncation reasons and limits reached.",
    )
    detection_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    model_config = ConfigDict(frozen=True)


class SpatialAnalysisReport(BaseModel):
    """Workbook-level spatial analysis report aggregating sheet detections."""

    workbook_path: str
    sheets: dict[str, SpatialDetectionReport] = Field(default_factory=dict)
    total_tables_detected: int = Field(ge=0, default=0)
    total_sparse_islands: int = Field(ge=0, default=0)
    has_boundary_collisions: bool = False
    boundary_anomalies: list[dict[str, Any]] = Field(default_factory=list)
    analysis_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    model_config = ConfigDict(frozen=True)
