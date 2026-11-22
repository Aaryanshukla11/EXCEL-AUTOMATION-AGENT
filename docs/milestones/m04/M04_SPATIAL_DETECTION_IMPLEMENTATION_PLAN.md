# Milestone M04 — Spatial Detection
## Document 3 of 3: Comprehensive Implementation Plan

**Date:** 2026-11-21  
**Milestone:** M04 — Spatial Detection  
**Stage:** Prompt 1 of 4 (Architecture Inspection & Requirements Discovery)  
**Status:** COMPLETE (Planning & Audit Only — Zero Code Modification)  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes)

---

## 1. Subsystem Architecture & Package Structure

Milestone M04 introduces the `excel_intel.spatial` package. It sits between M03 structural inspection and M05 type/formula analysis:

```
excel_intel/
└── spatial/
    ├── __init__.py           # Unified exports (SpatialDetector, SpatialTableRegion, etc.)
    ├── models.py             # Immutable Pydantic v2 spatial contracts
    ├── grid_segmenter.py     # 2D whitespace corridors & connected-component spatial clustering
    ├── header_resolver.py    # Multi-row hierarchical header resolution & compound name builder
    ├── zone_classifier.py    # Semantic zone breakdown (Title, Header, Body, Summary, Notes)
    ├── boundary_sentinel.py  # ADR-005 margin clearance & zero-space collision detection
    └── detector.py           # SpatialDetector facade orchestrating spatial analysis
```

---

## 2. Proposed Data Contracts & Schemas (`excel_intel/spatial/models.py`)

All models are frozen Pydantic v2 schemas:

```python
class RegionZoneType(str, Enum):
    TITLE_BANNER = "TITLE_BANNER"
    COLUMN_HEADER = "COLUMN_HEADER"
    DATA_BODY = "DATA_BODY"
    SUMMARY_TOTALS = "SUMMARY_TOTALS"
    FOOTNOTES = "FOOTNOTES"

class RegionZone(BaseModel):
    """Discrete semantic zone within a detected tabular region."""
    zone_type: RegionZoneType
    box: BoundingBox
    row_count: int
    cell_count: int
    model_config = ConfigDict(frozen=True)

class HeaderColumn(BaseModel):
    """Resolved column header with hierarchical path and coordinates."""
    col_index: int
    resolved_name: str
    hierarchy_levels: list[str]  # e.g. ["2024 Performance", "Q1"]
    is_merged: bool = False
    model_config = ConfigDict(frozen=True)

class MarginClearance(BaseModel):
    """ADR-005 clearance evaluation for append operations."""
    spare_rows_below: int
    has_zero_space_collision: bool
    has_trailing_formulas: bool
    adjacent_formulas: list[str] = Field(default_factory=list)
    safe_for_append: bool
    model_config = ConfigDict(frozen=True)

class SpatialTableRegion(BaseModel):
    """Primary detected rectangular tabular entity."""
    region_id: str
    sheet_name: str
    bounding_box: BoundingBox
    is_list_object: bool
    list_object_name: Optional[str] = None
    zones: dict[RegionZoneType, RegionZone]
    headers: list[HeaderColumn]
    margin: MarginClearance
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    model_config = ConfigDict(frozen=True)

    def to_table_metadata(self) -> TableMetadata:
        """Convert to M01 canonical TableMetadata."""
        ...

class SpatialAnalysisReport(BaseModel):
    """Root spatial analysis report for a worksheet or workbook."""
    workbook_path: str
    sheet_name: str
    detected_tables: list[SpatialTableRegion]
    sparse_islands: list[BoundingBox] = Field(default_factory=list)
    boundary_anomalies: list[StructuralAnomaly] = Field(default_factory=list)
    model_config = ConfigDict(frozen=True)
```

---

## 3. Core Algorithms & Detection Strategy

### 3.1 2D Whitespace Corridor & Connected-Component Segmentation (`grid_segmenter.py`)
1. **Streaming Sliding Window:** Stream rows using `StreamingWorkbookReader.stream_sheet()` into a lightweight sliding window of $W = 50$ rows.
2. **Horizontal Cuts:** Detect empty row intervals ($\ge 1$ blank rows) to establish vertical candidate bands.
3. **Vertical Cuts (Corridor Scanning):** Across each horizontal candidate band, compute column density projection histogram. Contiguous empty column intervals ($\ge 1$ blank columns) define vertical cuts, splitting side-by-side tables on shared rows.
4. **Declared Table Anchors:** Declared OpenXML tables (`DeclaredListObject` from M03) act as fixed spatial anchors. Any candidate block intersecting an explicit `ListObject` bounding box is anchored by the declared box.

### 3.2 Header Hierarchy & Entropy Transition (`header_resolver.py`)
1. **Type Transition Boundary:** Scan the top rows of a candidate region. Calculate type entropy shift where rows transition from label-dominant (string/text) to data-dominant (integers, floats, dates).
2. **Title Banner Filter:** A single populated row followed by a blank row or having width 1 (e.g. A1 text with table at A3:D20) is classified as `TITLE_BANNER` and stripped from the table headers.
3. **Multi-Row Stacked Hierarchy:** If rows 1..K are all string/label rows:
   - Overlay declared merged cells (`DeclaredMergeCell` from M03).
   - If a cell spans columns A..D in row 1 with text `"Sales"`, propagate `"Sales"` as the parent prefix for columns A, B, C, D.
   - Combine with row 2 labels: `["Sales -> North", "Sales -> South", "Sales -> East", "Sales -> West"]`.
4. **Collision Deduplication:** If duplicate column names result, disambiguate with 1-indexed suffixes (e.g. `"Total_1"`, `"Total_2"`).

### 3.3 Semantic Zone Decomposition (`zone_classifier.py`)
1. **Title Zone:** Rows above the column header row.
2. **Header Zone:** Identified header row(s).
3. **Data Body:** Rows from `header_end + 1` down to the last regular data row.
4. **Summary Zone:** Rows immediately below the data body exhibiting:
   - Aggregation formula patterns (`SUM(A2:A20)`, `AVERAGE`, `COUNT`, `SUBTOTAL`).
   - Summary label text (`Total`, `Grand Total`, `Average`, `Sum`).
5. **Footnotes Zone:** Trailing rows containing disclaimers, asterisks (`*`), or notes with width $\le 2$.

### 3.4 ADR-005 Append Boundary Sentinel (`boundary_sentinel.py`)
1. **Spare Space Scan:** Scan rows immediately following the table boundary (`summary_box.max_row` or `data_box.max_row`).
2. **Collision Evaluation:**
   - If `spare_rows_below == 0` (another table or formula exists on `max_row + 1`):
     - For ordinary ranges: `has_zero_space_collision = True`, `safe_for_append = False`.
     - Emit `ERR_BOUNDARY_COLLISION`.
   - If trailing summary formulas exist:
     - Record formula text in `adjacent_formulas`.
     - Prohibit append without user escalation to convert the range to a `ListObject` (ADR-005).

---

## 4. Four-Prompt Execution Breakdown

### Prompt 1: Architecture Inspection & Requirements Discovery (CURRENT)
- **Status:** COMPLETE upon delivery of these 3 reports.
- **Output:** `M04_SPATIAL_DETECTION_ARCHITECTURE_AUDIT.md`, `M04_SPATIAL_DETECTION_REQUIREMENTS.md`, `M04_SPATIAL_DETECTION_IMPLEMENTATION_PLAN.md`.
- **Preconditions:** M01–M03 frozen and accepted.
- **Exit Gate:** Formal Project Owner review and authorization to proceed to Prompt 2.

### Prompt 2: Spatial Data Models & 2D Grid Segmenter
- **Target Deliverables:**
  - `excel_intel/spatial/models.py` (Immutable schemas: `RegionZoneType`, `RegionZone`, `HeaderColumn`, `MarginClearance`, `SpatialTableRegion`, `SpatialAnalysisReport`).
  - `excel_intel/spatial/grid_segmenter.py` (2D whitespace scanning, horizontal/vertical corridor cuts, side-by-side table separation, sparse island clustering).
  - `excel_intel/spatial/__init__.py` (Initial package exports).
  - `tests/test_m04_spatial_models.py` (Validation of schemas, conversions, coordinate invariants).
  - `tests/test_m04_grid_segmenter.py` (Side-by-side tables, stacked tables, sparse islands, empty sheets).
- **Exit Gate:** All tests passing across Python 3.12/3.13, clean clippy/fmt, Prompt 2 Evidence Report.

### Prompt 3: Header Resolver, Zone Classifier & ADR-005 Boundary Sentinel
- **Target Deliverables:**
  - `excel_intel/spatial/header_resolver.py` (Multi-row stacked headers, merged header blocks, compound column name builder).
  - `excel_intel/spatial/zone_classifier.py` (Semantic zone decomposition: Title, Header, Body, Summary, Footnotes).
  - `excel_intel/spatial/boundary_sentinel.py` (ADR-005 spare margin measurement, zero-space collision detection, append safety).
  - `excel_intel/spatial/detector.py` (`SpatialDetector` unified facade).
  - `tests/test_m04_header_resolver.py` (Single-row, multi-row, merged headers, title banners).
  - `tests/test_m04_zone_classifier.py` (Zone decomposition, summary formula identification).
  - `tests/test_m04_boundary_sentinel.py` (ADR-005 collisions, margin clearance, safety gating).
  - `tests/test_m04_detector_facade.py` (Unified spatial detector facade testing).
- **Exit Gate:** Full test suite passing, Prompt 3 Evidence Report.

### Prompt 4: Final Integration, Performance Validation & Milestone Closure
- **Target Deliverables:**
  - `tests/test_m04_e2e_integration.py` (Comprehensive multi-sheet edge-case integration).
  - `tests/test_m04_concurrency_validation.py` (Multi-workbook concurrent isolation across threads).
  - `tests/benchmarks/run_m04_benchmarks.py` (1k to 100k row scaling, $O(C \cdot W)$ memory verification, latency < 200ms / 10k cells).
  - `M04_FINAL_INTEGRATION_AND_ACCEPTANCE_REPORT.md` (and mirrored copy in `docs/milestones/m04/`).
- **Exit Gate:** 100% test pass rate, performance SLAs satisfied, formal M04 milestone sign-off.

---

## 5. Regression Risks & Mitigation Strategies

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Model Incompatibility (M01 vs M03 BoundingBox)** | Inconsistent field names (`start_row` vs `min_row`). | Provide dual attribute accessors and explicit `to_table_metadata()` adapter in `SpatialTableRegion`. |
| **Memory Blowup on Massive Worksheets** | Spatial segmenter loading entire sheet grid into memory breaks 250 MB ceiling. | Enforce sliding lookahead window of $W \le 50$ rows. Do not materialize full 2D array; maintain active column intervals and coordinate bounds only. |
| **Over-Segmentation of Sparse Matrices** | Legitimate sparse matrix split into 100 tiny single-cell tables. | Consult M03 `layout_classification`. If classified as `SPARSE_MATRIX`, bypass dense corridor cutting and treat as a unified sparse matrix. |
| **False Positive Boundary Collisions** | Harmless formatting rows flagged as collisions, blocking valid appends. | Differentiate pure formatting / empty styled rows from populated cells or formula precedents. |
| **Shared State Across Threads** | Concurrent workers inspecting workbooks cross-contaminate spatial tables. | Enforce strictly stateless class designs. Pass all context through method arguments; zero module-level mutable collections. |

---

## 6. Unresolved Questions & Decision Points for Project Owner

Before implementation begins in Prompt 2, the following design questions are submitted for Project Owner confirmation:

1. **Compound Header Delimiter:** When resolving multi-row hierarchical headers (e.g. Row 1: `"2024"`, Row 2: `"Q1"`), what is the preferred canonical string delimiter? We recommend `" -> "` (e.g. `"2024 -> Q1"`).
2. **Lookahead Window Depth:** Is a sliding window depth of $W = 50$ rows acceptable for lookahead whitespace scanning and summary zone identification, or should this be configurable via `excel_intel.config`? (We recommend a default of 50 with config override).
3. **Ambiguous Boundary Action:** Under ADR-005, when an append target has zero spare margin, our sentinel marks `safe_for_append = False` and emits `ERR_BOUNDARY_COLLISION`. Does the owner confirm that M04 should strictly flag the condition and provide the clearance metrics, leaving the user-interactive conversion proposal to M06/M07?
