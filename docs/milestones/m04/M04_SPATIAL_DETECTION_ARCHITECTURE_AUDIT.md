# Milestone M04 — Spatial Detection
## Document 1 of 3: Architecture Inspection & Repository Audit

**Date:** 2026-11-21  
**Milestone:** M04 — Spatial Detection  
**Stage:** Prompt 1 of 4 (Architecture Inspection & Requirements Discovery)  
**Status:** COMPLETE (Planning & Audit Only — Zero Code Modification)  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes)

---

## 1. Executive Summary & Context

Milestone M04 (Spatial Detection) represents the critical spatial intelligence bridge between low-level OpenXML streaming extraction/inspection (M02/M03) and semantic type/formula analysis and cognitive consolidation planning (M05/M06).

Following the formal completion and acceptance of M01, M02, and M03, this audit inspects the entire repository to establish how Spatial Detection must be designed and integrated into the Autonomous Excel Intelligence Platform without introducing parallel, duplicate, or conflicting architectures.

### Primary Audit Findings:
1. **Existing Baseline (M01–M03):** The platform already possesses high-performance native streaming ingestion (`StreamingWorkbookReader`), package metadata inspection (`PackageStructureInspector`), sheet topology discovery (`SheetTopologyInspector`), bounded-memory content profiling (`ContentDistributionProfiler`), and coarse heuristic block detection (`ContentAnomalyDetector`).
2. **The Spatial Gap:** M03 deliberately restricts its scope to single-pass whole-sheet summaries, layout classification (`SINGLE_TABLE`, `MULTI_TABLE`, `KEY_VALUE_GRID`, `SPARSE_MATRIX`), and coarse row-run clustering (`PopulatedBlock`). It cannot perform 2D spatial segmentation (e.g. separating horizontally adjacent side-by-side tables on shared rows), cannot resolve hierarchical or merged multi-row headers, cannot segment intra-region zones (title banner vs header vs data vs summary footer), and cannot calculate ADR-005 margin clearance for safe append operations.
3. **Architectural Placement:** M04 must be housed in `excel_intel.spatial`, consuming M03's `WorkbookInspectionReport` and `StreamingWorkbookReader`, and emitting strongly-typed `SpatialAnalysisReport` and `TableMetadata` structures required downstream by M05 and M06 (`DiscoveryManifest`).

---

## 2. Comprehensive Repository Inspection & Inventory

### 2.1 Milestone M01 Baseline (`excel_intel.core.types`)
- **Spatial Primitives:**
  - `CellCoordinate`: Immutable 1-indexed discrete coordinate `(row, col)`.
  - `BoundingBox`: Immutable rectangular boundary `(start_row, start_col, end_row, end_col)`. Note: M01 uses `start_row`/`end_row`, while M03 uses `min_row`/`max_row`. M04 must cleanly bridge these models.
- **Downstream Target Contracts:**
  - `TableMetadata`: Target contract for detected tabular grids (`sheet_name`, `bounding_box`, `header_row`, `columns`, `is_list_object`, `list_object_name`).
  - `ColumnMetadata`: Column-level metadata (`index`, `header_name`, `inferred_type`, `type_confidence`, `nullable`, `formula_pattern`).
  - `DiscoveryManifest`: Root structural manifest consumed by cognitive orchestration (`manifest_id`, `workbook_path`, `tables: list[TableMetadata]`, `formula_graph`).

### 2.2 Milestone M02 Baseline (`excel_intel.core.parser` & `excel_intel_rs`)
- **Native Streaming Parser:** `StreamingWorkbookReader` streams row records chunk-by-chunk (`stream_sheet(sheet, chunk_size)`).
- **Cell Token Stream:** Yields dict records: `{"row": int, "cells": [{"col": int, "value": Any, "formula": Optional[str], "cell_type": str, "style_id": int}]}`.
- **Memory & Resource Enforcement:** Strict 235 MB warning tripwire, 250 MB hard process ceiling, 8 MB burst allocation trigger. Scratch disk lifecycle management with `FILE_SHARE_READ` Windows lock isolation.
- **Package Part Access:** `read_package_part(part_name)` provides safe direct access to internal XML parts without full archive extraction.

### 2.3 Milestone M03 Baseline (`excel_intel.inspection`)
- **Package Inspector (`package_inspector.py`):**
  - Discovers `<calcPr>` engine properties, workbook defined names with scope resolution, sheet catalog visibility (`visible`, `hidden`, `veryHidden`), and declared OpenXML Excel Tables (`ListObjects`).
- **Topology Inspector (`topology_inspector.py`):**
  - Parses worksheet dimensions (`<dimension ref="...">`), declared merged cells (`<mergeCell ref="...">`), and hidden row/column intervals.
  - Ownership: Owns structural XML anomalies (`ANOM_INVALID_DIMENSION_REF`, `ANOM_OVERLAPPING_MERGE_CELLS`, `ANOM_CORRUPT_TABLE_XML`, `ANOM_DUPLICATE_DEFINED_NAME`).
- **Content Profiler (`content_profiler.py`):**
  - Single-pass streaming row analysis with $O(C)$ spatial complexity.
  - Computes `ColumnProfile` (populated count, type distributions, predominant type, homogeneity ratio, formula count).
  - Computes `SheetContentProfile` (actual bounding box, cell counts, layout classification: `EMPTY`, `SINGLE_TABLE`, `MULTI_TABLE`, `KEY_VALUE_GRID`, `SPARSE_MATRIX`, `IRREGULAR_COMPOSITE`).
  - `PopulatedBlock`: Coarse row clustering based on empty row intervals (`row_idx > last_populated_row + 2`).
- **Anomaly Detector & Coarse Region Hypotheses (`anomaly_detector.py`):**
  - Owns content-derived anomalies (`ANOM_UNDERSTATED_DIMENSION`, `ANOM_MIXED_COLUMN_TYPES`, `ANOM_FORMULA_INCONSISTENCY`, `ANOM_JAGGED_ROW_STRUCTURE`, `ANOM_FRAGMENTED_REGIONS`).
  - Evaluates approved 4-factor heuristic confidence formula:
    $$\text{Score} = \max\left(0.0, \min\left(1.0, 0.40 H_{\text{type}} + 0.30 S_{\text{hdr}} + 0.20 B_{\text{bnd}} + 0.10 D_{\text{den}} - P_{\text{penalties}}\right)\right)$$
- **Inspector Facade (`inspector.py`):**
  - Assembles `WorkbookInspectionReport` and `SheetInspectionReport`.
  - Proven multi-workbook concurrent isolation and deterministic execution.

---

## 3. Existing Capabilities vs. Spatial Detection Gaps

The table below contrasts what the platform currently detects (M01–M03) against the spatial detection capabilities required for M04:

| Feature / Capability | Existing System (M01–M03) | Required in M04 Spatial Detection |
| :--- | :--- | :--- |
| **Declared Excel Tables** | Fully extracts `DeclaredListObject` facts with exact coordinates and column names. | Reuses M03 facts directly; establishes baseline anchors for non-table boundary comparison. |
| **Declared Merged Cells** | Extracts `DeclaredMergeCell` list and flags overlapping merges. | Analyzes spatial relation of merged cells to regions (header merges vs internal cell merges vs cross-boundary merges). |
| **Row-Run Clustering** | Identifies candidate blocks separated by vertical gaps ($> 2$ blank rows). | Performs full 2D connected-component segmentation; detects both horizontal and vertical whitespace cuts. |
| **Side-by-Side Tables** | **FAILED / MISSING:** Merges horizontally adjacent tables on shared rows into a single wide block. | **MUST HAVE:** Evaluates vertical whitespace corridors (blank columns) to segment side-by-side tables cleanly. |
| **Header Identification** | Coarse heuristic checking if candidate row 1 has strings while body has numbers. | Resolves multi-row headers, hierarchical stacked headers, merged header labels, and exact header/data transition boundary. |
| **Zone Decomposition** | Whole-block bounding box only. | Decomposes region into Title Banner, Header Zone, Data Grid Body, Summary / Totals Zone, and Footnotes. |
| **ADR-005 Safety Clearance** | None. | Measures spare cell margin below ranges; detects trailing formulas and zero-space collisions for safe record appends. |
| **Downstream Manifest** | Contract defined in M01 (`TableMetadata`, `DiscoveryManifest`), but unpopulated by M03. | Converts verified spatial regions into populated `TableMetadata` ready for M05 type inference and M06 planning. |

---

## 4. Reusable Components & Extension Points

M04 must directly reuse the following approved components without duplication:
1. **`excel_intel.core.parser.StreamingWorkbookReader`:** Primary streaming data source. M04 must not re-implement ZIP parsing, XML extraction, or date conversion.
2. **`excel_intel.inspection.WorkbookInspector` & `SheetInspectionReport`:** M04 consumes the inspection report to obtain:
   - Declared OpenXML facts (`list_objects`, `merge_cells`, `hidden_rows`, `hidden_columns`).
   - Content profile (`actual_bounding_box`, `column_profiles`, `layout_classification`).
   - Detected anomalies (understated dimensions, jagged rows, formula inconsistencies).
   - Coarse candidate blocks (`blocks`).
3. **`excel_intel.core.types.BoundingBox` & `excel_intel.inspection.models.BoundingBox`:** Coordinate arithmetic, containment checks (`contains_coord`), and intersection logic (`intersects`).
4. **Memory Guard Infrastructure:** `py_check_memory_guard()` and `py_get_process_working_set_bytes()` to ensure bounded spatial analysis.

---

## 5. Architectural Boundaries & Module Placement

To maintain clean separation of concerns:
```
excel_intel/
├── core/                  # M01 Core contracts, M02 streaming parser & native bridge
├── inspection/            # M03 OpenXML package, topology, profiler, and inspection facade
└── spatial/               # M04 SPATIAL DETECTION SUBSYSTEM (New Package)
    ├── __init__.py        # Public exports
    ├── models.py          # Spatial Pydantic v2 schemas (SpatialTableRegion, RegionZone, MarginClearance)
    ├── grid_segmenter.py  # 2D whitespace corridors & connected-component spatial clustering
    ├── header_resolver.py # Multi-row hierarchical header resolution & entropy transitions
    ├── zone_classifier.py # Semantic zone breakdown (Title, Header, Body, Summary, Footnotes)
    ├── boundary_sentinel.py # ADR-005 margin clearance & zero-space collision detection
    └── detector.py        # SpatialDetector facade orchestrating spatial analysis
```

### Flow of Architectural Authority:
```mermaid
flowchart LR
    A["Raw Excel File"] --> B["M02 Native Parser\n(Streaming Rows)"]
    B --> C["M03 Inspection Facade\n(Facts, Topology, Profile)"]
    C --> D["M04 Spatial Detector\n(2D Segments, Headers, Zones, ADR-005)"]
    D --> E["M05 Semantic Type & Formula DAG"]
    E --> F["M06 Cognitive Consolidation Planner"]
```

---

## 6. Non-Regression & Invariant Analysis

1. **M01 Invariant Preservation:**
   - M01 contracts (`DiscoveryManifest`, `TableMetadata`, `BoundingBox`, `CellCoordinate`) remain frozen.
   - M04 spatial regions will provide a deterministic conversion method `to_table_metadata() -> TableMetadata`.
2. **M02 Invariant Preservation:**
   - Streaming reader, shared string generational LRU cache, and decimal memory thresholds (235 MB warning, 250 MB ceiling) remain untouched.
   - Spatial detection must operate in a single streaming pass or bounded window ($W \le 50$ rows) to preserve $O(C)$ spatial complexity.
3. **M03 Invariant Preservation:**
   - `WorkbookInspectionReport`, `SheetInspectionReport`, and M03 inspection logic remain frozen and unaltered.
   - M04 acts purely as a downstream consumer of M03 outputs.
4. **Coordinate Integrity:**
   - All cell, row, and column coordinates remain strictly 1-indexed.
5. **Epistemological Distinction:**
   - Declared OpenXML facts (`is_list_object=True`) remain distinguished from inferred regions (`is_list_object=False`).
   - Spatial confidence scores remain normalized in $[0.0, 1.0]$ and are never described as probabilities.
