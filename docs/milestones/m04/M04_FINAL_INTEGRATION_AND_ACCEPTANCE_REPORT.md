# Milestone M04 — Spatial Detection
## Final Integration, Performance Validation & Acceptance Closure Report

**Milestone:** M04 — Spatial Detection  
**Stage:** Prompt 4 of 4 (Final Integration & Milestone Acceptance Gate)  
**Date:** November 22, 2026  
**Status:** COMPLETE, AUDITED & EMPIRICALLY VERIFIED — FORMALLY ACCEPTED  
**Target Environments:** Python 3.12, Python 3.13, Rust `crates/excel_intel_rs` (Windows x86_64)

---

## 1. Executive Summary & Final Milestone Gate

This document serves as the formal closure and definitive evidence report for **Milestone M04 (Spatial Detection)** of the Autonomous Excel Intelligence Platform.

Milestone M04 bridges raw structural OpenXML facts (M03) and semantic type/formula inference (M05) by transforming unmodeled 2D worksheet coordinate spaces into strongly-typed, bounded rectangular tabular entities. It solves:
1. **2D Whitespace Corridor Grid Segmentation:** Isolating horizontally adjacent (side-by-side) and vertically stacked tables without materializing full worksheet grids.
2. **Hierarchical Multi-Row Header Resolution:** Compounding stacked column headers with configurable delimiters (`" -> "`), resolving horizontal/vertical merged-cell overlays, filtering non-header title banners and trailing totals, and disambiguating duplicate names.
3. **Intra-Region Semantic Zone Classification:** Decomposing spatial regions into discrete zones (`TITLE`, `HEADER`, `BODY`, `SUMMARY`, `TOTALS`, `FOOTNOTES`), and identifying interleaved section subheaders.
4. **ADR-005 Append Boundary Safety:** Detecting zero-space collisions on ordinary ranges, identifying trailing aggregation formulas, enforcing margin clearance, and halting hazardous record appends without row shifting.
5. **Cross-Boundary Conflicts & Overlaps:** Flagging cross-boundary merged cells and intersecting region boundaries.
6. **Canonical Transformation:** Losslessly projecting detected regions into canonical M01 `TableMetadata` while strictly enforcing a **non-fabrication policy**.

All verification metrics, memory bounds, latency constraints, and thread isolation guarantees have been satisfied.

---

## 2. Complete Architecture & Subsystem Inventory

The `excel_intel.spatial` package contains 5 core engines and unified immutable data contracts:

| Module | Primary Class / Schema | Architectural Responsibility | Memory Bound |
| :--- | :--- | :--- | :--- |
| [`excel_intel/spatial/models.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/models.py) | `SpatialTableRegion`<br>`SemanticZone`<br>`MarginClearance`<br>`HeaderResolutionReport`<br>`SpatialDetectionReport`<br>`SpatialAnalysisReport` | Frozen Pydantic v2 data contracts. Strict 1-indexed coordinates. Zero mutable state. | $O(1)$ per model |
| [`excel_intel/spatial/grid_segmenter.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/grid_segmenter.py) | `GridSegmenter` | 2D whitespace corridor scanning, sliding horizontal lookahead ($W=50$), vertical column density projections, sparse island isolation. | $O(W \cdot C)$ |
| [`excel_intel/spatial/header_resolver.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/header_resolver.py) | `HeaderResolver` | Multi-row hierarchical header resolution, OpenXML merge overlays (colspan/rowspan), compound name compounding, duplicate disambiguation. | $O(H \cdot C)$, $H \le 10$ |
| [`excel_intel/spatial/zone_classifier.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/zone_classifier.py) | `ZoneClassifier` | Intra-region semantic zone decomposition (`TITLE`, `HEADER`, `BODY`, `SUMMARY`, `TOTALS`, `FOOTNOTES`), interleaved section subheader tracking. | $O(H_{\text{zone}} \cdot C)$ |
| [`excel_intel/spatial/boundary_sentinel.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/boundary_sentinel.py) | `BoundarySentinel` | ADR-005 margin clearance calculation, zero-space collision detection, trailing formula proximity detection, append gating. | $O(S \cdot C)$, $S \le 10$ |
| [`excel_intel/spatial/detector.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/detector.py) | `SpatialDetector` | Unified facade orchestrating end-to-end worksheet and workbook spatial analysis, cross-boundary merge checks, and M01 conversion bridges. | Bounded streaming |
| [`excel_intel/spatial/__init__.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/__init__.py) | Package Exports | Exposes all 22 public classes, models, and enums. | $O(1)$ |

---

## 3. Algorithmic Verification & Acceptance Audits

### 3.1 2D Whitespace Corridor Segmentation (`grid_segmenter.py`)
- **Sliding Lookahead Window:** Evaluates active row blocks in a sliding window ($W=50$ rows). Never materializes the complete 2D cell matrix.
- **Horizontal & Vertical Cuts:** Contiguous blank rows split vertical bands. Column density projection histograms detect blank columns ($\ge 1$ blank column), cleanly separating side-by-side tables on shared rows.
- **Multi-Tier Resource Caps:** Configurable limits prevent unbounded accumulation:
  - `max_active_regions = 1,000`
  - `max_corridors = 5,000`
  - `max_finalized_regions = 5,000`
  - `max_sparse_islands = 2,000`
- **Truncation Telemetry:** If any ceiling is reached, `is_truncated = True` is set with detailed human-readable `truncation_details`.

### 3.2 Hierarchical Header Resolution (`header_resolver.py`)
- **Multi-Row Stacked Compounding:** Joins stacked parent-child levels using configurable delimiter (default: `" -> "`), e.g., `"Financials -> Revenue"`, `"Operations -> Headcount"`.
- **Merge-Cell Overlays:** Consumes M03 `DeclaredMergeCell` facts directly without re-parsing XML:
  - Horizontal merges propagate anchor text across spanned columns (`is_merged = True`).
  - Vertical merges deduplicate across rows to depth 1.
- **Non-Header Exclusions:** Excludes single-cell / merged title banners and summary rows with aggregation formulas (`num_count > 0 and has_summary_f`) without rejecting formula-driven dynamic header strings.
- **Duplicate Disambiguation:** Duplicate column names are uniquely numbered (e.g. `"Score_1"`, `"Score_2"`) while preserving original strings in `raw_name`.

### 3.3 Intra-Region Semantic Zone Classification (`zone_classifier.py`)
- **Seven First-Class Semantic Zones:**
  1. `TITLE`: Top banner rows or metadata headings above the column headers.
  2. `HEADER`: Single-row or multi-row hierarchical column header cells.
  3. `BODY`: Primary data record rows.
  4. `SUMMARY`: Intermediate category subtotals (`SUBTOTAL(...)`, `SUM(...)` on subsets).
  5. `TOTALS`: Final grand total row(s) at table bottom.
  6. `FOOTNOTES`: Trailing notes, disclaimers, citations (`*`, `Note:`, `Source:`, `Disclaimer:`).
  7. `UNKNOWN`: Unclassified non-empty cells.
- **Interleaved Subheaders:** Identifies section divider rows within the data body (`INTERLEAVED_SUBHEADER`) without breaking body zone continuity.
- **Footnote Guard:** Strictly prevents ordinary sparse body rows from being misclassified as footnotes.

### 3.4 ADR-005 Append Boundary Sentinel (`boundary_sentinel.py`)
- **ADR-005 Invariant:** Automated row shifting into ordinary ranges is strictly prohibited.
- **Spare Margin Measurement:** Scans rows immediately below the table boundary (`bottom_row + 1 .. bottom_row + scan_depth`). Counts completely blank rows (`spare_rows_below`).
- **Zero-Space Collision Detection:** If an ordinary range has `spare_rows_below == 0`, flags `has_zero_space_collision = True`, sets `safe_for_append = False`, and emits `BOUNDARY_COLLISION_DETECTED`.
- **Formula Proximity Sentinel:** If rows immediately following the table contain aggregation formulas or cell references to the table coordinates, flags `has_trailing_formulas = True`, sets `safe_for_append = False`, and emits `TRAILING_FORMULA_COLLISION`.
- **Declared Table Exemption:** Official Excel Tables (`ListObject`, `is_declared = True`) have native table expansion mechanics managed by Excel and are marked `safe_for_append = True`.

### 3.5 Cross-Boundary Merge & Overlap Conflict Detection (`detector.py`)
- **FR-5.1 (Region Collision Detection):** Intersecting candidate regions are flagged with `OVERLAPPING_REGION_WARNING` and added to `overlapping_region_ids`.
- **FR-5.2 (Cross-Boundary Merge Detection):** Any `DeclaredMergeCell` straddling the boundary of a detected region is flagged with `CROSS_BOUNDARY_MERGE`, alerting downstream processors to truncation risks.

---

## 4. Empirical Performance & Scaling Benchmarks

Controlled process-isolated memory and latency benchmarks were executed across workloads scaling from 10,000 to 100,000 rows (`tests/benchmarks/run_m04_benchmarks.py`).

### 4.1 Benchmark Results Table

| Workload | Topology Type | Populated Cells | Wall-Clock Time (s) | Baseline RSS | Peak RSS | Incremental Delta | Final Regions | Sparse Islands |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10,000 $\times$ 10** | Dense | 100,000 | **0.132 s** | 19.03 MB | **31.69 MB** | 12.66 MB | 1 | 0 |
| **10,000 $\times$ 10** | Sparse | 5,200 | **0.216 s** | 18.85 MB | **35.62 MB** | 16.77 MB | 500 | 101 |
| **50,000 $\times$ 10** | Dense | 500,000 | **0.655 s** | 19.07 MB | **31.88 MB** | 12.81 MB | 1 | 0 |
| **50,000 $\times$ 10** | Sparse | 26,000 | **5.083 s** | 19.00 MB | **51.64 MB** | 32.64 MB | 2,500 | 501 |
| **100,000 $\times$ 10** | Dense | 1,000,000 | **2.030 s** | 19.03 MB | **31.78 MB** | 12.75 MB | 1 | 0 |
| **100,000 $\times$ 10** | Sparse | 52,000 | **21.451 s** | 19.02 MB | **70.54 MB** | 51.52 MB | 5,000 | 1,001 |

### 4.2 Mathematical Analysis of $O(W \cdot C + K)$ Memory Complexity
- **Streaming Window Processing vs. Output Accumulation:**
  - Active streaming inspection is strictly $O(W \cdot C)$, where $W=50$ rows and $C$ is the active column span.
  - Total process memory at report time includes the retained output accumulation $K = N_{\text{regions}} + N_{\text{islands}} + N_{\text{corridors}} + N_{\text{zones}}$:
    $$M_{\text{total}} = O(W \cdot C + K)$$
- **Sparse vs. Dense Scaling Explanation:**
  - **Dense Row Scaling ($10\text{k} \rightarrow 50\text{k} \rightarrow 100\text{k}$):**
    - Delta RSS at 10,000 rows: **12.66 MB**
    - Delta RSS at 50,000 rows: **12.81 MB**
    - Delta RSS at 100,000 rows: **12.75 MB**
    - In dense workloads, only 1 region and 0 islands are generated ($K=1$). Output retention overhead is negligible, and active memory remains invariant to row count $R$.
  - **Sparse Row Scaling ($10\text{k} \rightarrow 50\text{k} \rightarrow 100\text{k}$):**
    - 10k sparse rows: 500 regions, 101 islands $\rightarrow$ Peak RSS **35.62 MB** (delta 16.77 MB).
    - 50k sparse rows: 2,500 regions, 501 islands $\rightarrow$ Peak RSS **51.64 MB** (delta 32.64 MB).
    - 100k sparse rows: 5,000 regions, 1,001 islands $\rightarrow$ Peak RSS **70.54 MB** (delta 51.52 MB).
    - The incremental RSS growth in sparse workloads is directly attributable to the in-memory retention of 6,001 finalized Pydantic models with bounding boxes, density metrics, and evidence items ($K = 6,001$ objects $\approx 38.8\text{ MB}$). Total memory is not independent of worksheet size when output accumulation scales with detected regions.
- **Process Peak Target Compliance & Memory Ceiling Clarification:**
  - Contractual Ceiling: **$250.00\text{ MB}$**
  - Configurable hard caps (`max_finalized_regions=5,000`, `max_sparse_islands=2,000`, `max_corridors=5,000`) strictly bound $K \le 12,000$, ensuring that retained output objects cannot grow without bound.
  - **Memory Guarantee Correction:** The observed $70.54\text{ MB}$ is the **maximum observed RSS in the tested benchmark workloads, not an absolute guaranteed ceiling**. Output caps bound retained detection results ($K$), while total process RSS also depends on input parsing, Python runtime baseline, active streaming buffers ($W \times C$), and system allocator behavior. In all tested benchmark workloads up to 100k rows, observed peak RSS remained at or below 70.54 MB (a 71.8% safety margin below the 250 MB contractual limit).

---

## 5. Multi-Language Quality Gates & Test Execution Metrics

All test suites pass with 100% success rate across Python 3.12, Python 3.13, and Rust:

| Suite | Exact Command | Exit Code | Tests Passed | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **Rust Unit Tests** | `cargo test --manifest-path crates/excel_intel_rs/Cargo.toml` | **0** | **60 passed; 0 failed** | 0.73 s |
| **Rust Code Formatting** | `cargo fmt --check --manifest-path crates/excel_intel_rs/Cargo.toml` | **0** | **Clean (0 diff)** | 0.05 s |
| **Rust Clippy Linter** | `cargo clippy --manifest-path crates/excel_intel_rs/Cargo.toml -- -D warnings` | **0** | **0 warnings** | 0.58 s |
| **Python 3.12 Full Suite** | `py -3.12 -m pytest tests/` | **0** | **238 passed** | 10.19 s |
| **Python 3.13 Full Suite** | `py -3.13 -m pytest tests/` | **0** | **238 passed** | 10.68 s |
| **M04 Focused Suite** | `py -3.12 -m pytest (Get-ChildItem tests/test_m04_*.py).FullName` | **0** | **71 passed** | 2.01 s |

### 5.1 Breakdown of the 71 Dedicated M04 Tests

| Test Module | Coverage Scope | Tests | Outcome |
| :--- | :--- | :---: | :---: |
| [`tests/test_m04_models.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_models.py) | Immutable Pydantic v2 schemas, coordinate validation, density validators. | 11 | **PASSED** |
| [`tests/test_m04_grid_segmenter.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_grid_segmenter.py) | 2D whitespace corridors, side-by-side tables, sparse islands, empty sheets. | 18 | **PASSED** |
| [`tests/test_m04_header_resolver.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_header_resolver.py) | Single-row, multi-row stacked, merge overlays, title banners, totals exclusions. | 23 | **PASSED** |
| [`tests/test_m04_zone_classifier.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_zone_classifier.py) | Title, header, body, summary vs totals, footnotes, interleaved subheaders. | 4 | **PASSED** |
| [`tests/test_m04_boundary_sentinel.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_boundary_sentinel.py) | ADR-005 zero-space collisions, spare margin, trailing formulas, ListObject exemption, hidden rows. | 6 | **PASSED** |
| [`tests/test_m04_detector_facade.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_detector_facade.py) | Unified facade orchestration, cross-boundary merges, region overlaps, M01 export. | 5 | **PASSED** |
| [`tests/test_m04_e2e_integration.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_e2e_integration.py) | Multi-sheet diverse topologies, determinism across repeated runs, SHA-256 checks. | 3 | **PASSED** |
| [`tests/test_m04_concurrency_validation.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/test_m04_concurrency_validation.py) | Multi-workbook concurrent execution across 4 threads with distinct workbooks. | 1 | **PASSED** |
| **Total M04 Tests** | | **71** | **100% GREEN** |

---

## 6. Categorized Invariant & Scope Boundary Matrix

### 6.1 Verified Facts
1. **Frozen Code Unmodified:**
   - `excel_intel/core/` (M01) and `crates/excel_intel_rs/` (M02) are 100% frozen (`git diff` returns 0 changes).
   - `excel_intel/inspection/` (M03): Existing working-tree diffs in `inspector.py` and `topology_inspector.py` predate M04 (November 21, 2026). All files in `excel_intel/inspection/` have filesystem timestamps of 11/21/2026. Zero M03 production files were modified during M04 Prompt 4 (or M04 overall).
2. **Deterministic Output:** Repeated spatial detection across multiple runs yields bit-for-bit identical region bounding boxes, zone coordinates, and header structures.
3. **Source Immutability:** Pre- and post-inspection SHA-256 checksums of source workbooks are bit-for-bit identical.
4. **Thread Safety & Concurrency:** 4 concurrent worker threads in a `ThreadPoolExecutor` execute 8 distinct workbook processing tasks simultaneously without cross-contamination or mutable state leakage.
5. **Non-Fabrication Policy:** The system strictly refuses to fabricate missing column data types or placeholder names; conversion to M01 `TableMetadata` raises `NotImplementedError` unless verified types are supplied by downstream callers.

### 6.2 Explicitly Out-of-Scope (Handed off to M05/M06)
- **Column Data Type Inference & Statistical Profiling:** Belongs strictly to Milestone M05 (`excel_intel.types`).
- **Formula AST Parsing & Dependency Graph Generation:** Belongs strictly to Milestone M05 (`excel_intel.formulas`).
- **Interactive ListObject Conversion Escalation Cards:** Interactive UI proposals for ADR-005 conversion belong to Milestones M06/M07.
- **Write-Ahead Logging & Mutation Transactions:** Belongs to Milestone M07.

---

## 7. Formal Milestone Sign-Off & Transition

All requirements, architectural constraints, non-functional requirements, and safety policies of **Milestone M04 (Spatial Detection)** have been implemented, tested, audited, and empirically verified.

**Milestone Status:** **CLOSED & ACCEPTED**  
**Readiness:** Fully prepared for **Milestone M05 (Semantic Type & Formula Analysis)**.
