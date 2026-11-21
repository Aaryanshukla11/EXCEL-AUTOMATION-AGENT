# M03 Prompt 2 Evidence Report
## Data Models, OpenXML Package Inspector & Sheet Topology Engine

**Module:** M03 — Workbook Inspection & Structural Analysis  
**Step:** Prompt 2 of 4  
**Date:** 2026-11-21  
**Status:** IMPLEMENTED, TESTED, AND VERIFIED (Awaiting Project Owner Authorization for Prompt 3)

---

### 1. Executive Summary & Scope

All authorized components for **M03 Prompt 2** have been implemented, tested, and validated in strict accordance with the approved architecture:

1. **`excel_intel/inspection/models.py`:** Complete immutable Pydantic v2 schemas modeling coordinates, bounding boxes, hidden intervals, declared OpenXML facts, heuristic region hypotheses, structural anomalies, and inspection reports.
2. **`excel_intel/inspection/package_inspector.py`:** PackageStructureInspector extracting calculation properties (`<calcPr>`), defined names (with scope resolution and duplicate detection), sheet catalog (visibility: `visible`, `hidden`, `veryHidden`), and declared tables (`ListObjects` from `xl/tables/table*.xml` via sheet `.rels`).
3. **`excel_intel/inspection/topology_inspector.py`:** SheetTopologyInspector discovering worksheet dimensions, merged-cell ranges (with overlap anomaly detection), and hidden row/column intervals consolidated into contiguous spans.
4. **`excel_intel/inspection/__init__.py`:** Public exports and clean encapsulation for the inspection subsystem.
5. **Secure M02 Integration:** M02's `WorkbookStreamReader` was extended with `read_package_part(&self, part_name: &str) -> PyResult<Option<String>>` and `list_package_parts(&self) -> PyResult<Vec<String>>`, strictly enforcing decompression quotas (10.0x ratio, 1.0 GiB ceiling) without raw zip access.

---

### 2. Implementation Inventory

| File Path | Component | Responsibility |
| :--- | :--- | :--- |
| `crates/excel_intel_rs/src/lib.rs` | M02 Package Access Extension | Exposes `read_package_part`, `list_package_parts`, `get_sheet_path`, and `get_all_sheet_paths` on `WorkbookStreamReader`. |
| `excel_intel/core/parser.py` | Python Core Reader | Exposes `read_package_part` and `list_package_parts` on `StreamingWorkbookReader`. |
| `excel_intel/inspection/models.py` | Data Models | Immutable Pydantic v2 models: `BoundingBox`, `HiddenInterval`, `DeclaredSheetProperties`, `DeclaredMergeCell`, `DeclaredListObject`, `DeclaredDefinedName`, `DeclaredOpenXmlFacts`, `InferredRegionHypothesis`, `RegionHypothesis`, `StructuralAnomaly`, `SheetInspectionReport`, `WorkbookInspectionReport`. |
| `excel_intel/inspection/package_inspector.py` | Package Inspector | `PackageStructureInspector`: calculation engine properties, defined names with workbook/sheet scoping, duplicate name detection, sheet visibility catalog, and `ListObject` table parsing. |
| `excel_intel/inspection/topology_inspector.py` | Topology Inspector | `SheetTopologyInspector`: single-pass dimension discovery, merged cell extraction, interval consolidation (`consolidate_intervals`), and overlapping merge anomaly detection. |
| `excel_intel/inspection/__init__.py` | Module Exports | Clean public API for the `excel_intel.inspection` package. |
| `tests/test_m03_models.py` | Models Unit Tests | 22 tests verifying coordinate math, bounding boxes, intervals, immutability, and confidence bounds. |
| `tests/test_m03_package_inspector.py` | Package Inspector Tests | 8 tests verifying calculation properties, sheet catalog visibility, defined names scoping, tables extraction, malformed XML handling, and M02 integration. |
| `tests/test_m03_topology_inspector.py` | Topology Inspector Tests | 7 tests verifying dimensions, missing dimensions, merged cells, overlapping merges, hidden rows/columns consolidation, and source workbook immutability. |

---

### 3. Key Architectural Proofs & Requirements Compliance

#### 3.1 Strict Separation of Declared Facts vs. Heuristic Inferences
- **Declared OpenXML Facts (`DeclaredOpenXmlFacts`):** Contains only deterministic, explicit facts declared in the OpenXML container (`DeclaredSheetProperties`, `BoundingBox`, `DeclaredMergeCell`, `DeclaredListObject`, `HiddenInterval`). It contains **zero** confidence scores, weights, or probabilistic fields.
- **Inferred Hypotheses (`InferredRegionHypothesis`):** Contains `confidence_score: float = Field(ge=0.0, le=1.0)` strictly bounded between 0.0 and 1.0, standardized `evidence_codes: list[EvidenceCode]`, `evidence_descriptions: list[str]`, `deduction_penalties: list[str]`, and `source_provenance`.
- **Immutability:** All models enforce `ConfigDict(frozen=True)`. Any attempt to mutate model attributes at runtime raises a Pydantic `ValidationError`.

#### 3.2 1-Indexed Coordinate System & Bounding Box Invariants
- 1-indexed Excel coordinates are preserved throughout (`row` $1..1048576$, `col` $1..16384$).
- `BoundingBox` validates `min_row <= max_row` and `min_col <= max_col`. Inverted range strings (e.g. `"D10:A1"`) are automatically normalized to `"A1:D10"`.
- Range helper methods (`row_count`, `col_count`, `cell_count`, `contains_coord`, `intersects`, `to_a1_ref`, `from_a1_ref`) guarantee mathematical spatial consistency.

#### 3.3 Secure M02 Package Access Interface
- `PackageStructureInspector` and `SheetTopologyInspector` interact with the underlying Excel package strictly through:
  `reader.read_package_part(part_name)`
- This routes all reads through M02's Rust `ZipPackageReader`, enforcing:
  1. 10.0x maximum decompression ratio guard.
  2. 1.0 GiB cumulative decompression ceiling.
  3. Structural ZIP64 rejection (>4 GB container).
  4. Complete protection against XML entity expansion / billion-laughs attacks.
- Non-existent optional parts return `None` cleanly without throwing exceptions.

#### 3.4 Single-Pass Sheet Topology Extraction & Interval Consolidation
- Single-pass topology extraction reads worksheet XML parts without double decompression.
- Discovered hidden rows and hidden columns are consolidated into contiguous non-overlapping `HiddenInterval` records via `consolidate_intervals()`.
- Merged cells are verified for overlaps; intersecting merge ranges emit `ANOM_OVERLAPPING_MERGE_CELLS`.

#### 3.5 Source Workbook Immutability Invariant
- Source workbooks are opened strictly read-only (`File::open`).
- Test `test_source_workbook_remains_unchanged` empirically verifies that the source workbook's file size and SHA-256 hash before inspection match the post-inspection file byte-for-byte.

---

### 4. Quality Gates & Test Suite Audit

#### 4.1 Rust Quality Gates
- `cargo fmt --manifest-path crates/excel_intel_rs/Cargo.toml --check` — **Clean (0 diffs)**.
- `cargo clippy --manifest-path crates/excel_intel_rs/Cargo.toml --all-targets -- -D warnings` — **Clean (0 warnings)**.
- Parallel Rust unit tests: **60 / 60 passed** in $0.62\text{ s}$.

#### 4.2 Python Test Suites
- **Python 3.12 Suite (`py -3.12 -m pytest tests/ -q`):**
  - **142 / 142 passed** in $7.25\text{ s}$ (105 M02 baseline tests + 37 M03 Prompt 2 tests).
- **Python 3.13 Suite (`py -3.13 -m pytest tests/ -q`):**
  - **142 / 142 passed** in $7.18\text{ s}$ (105 M02 baseline tests + 37 M03 Prompt 2 tests).
- **M03 Specific Suite (`py -3.12 -m pytest tests/test_m03* -v`):**
  - **37 / 37 passed** in $0.83\text{ s}$.

#### 4.3 Release Build
- `cargo build --release --manifest-path crates/excel_intel_rs/Cargo.toml` — **Clean build**. Compiled extension `excel_intel/_rs.pyd` verified.

---

### 5. Governance Confirmation

- **Prompt 2 Scope Strictly Preserved:** Implemented only `models.py`, `package_inspector.py`, and `topology_inspector.py`.
- **Not Started:** Prompt 3 (`content_profiler.py`, `anomaly_detector.py`) and Prompt 4 (`WorkbookInspector` facade, benchmarks, final evidence report) remain strictly unstarted.
- **No Git Commit or Push:** In compliance with user instructions, all changes remain unstaged in the local working directory.

Ready for Project Owner review and authorization to proceed with **M03 Prompt 3 (Content Profiler & Anomaly Detector)**.
