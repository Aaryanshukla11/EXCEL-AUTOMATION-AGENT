# M05 PROMPT 4 EVIDENCE REPORT: DEPENDENCY GRAPH, CYCLE DETECTION & MANIFEST INTEGRATION

**Milestone:** M05 — Semantic Type & Formula Dependency Analysis  
**Stage:** Prompt 4 — Dependency Graph, Cycle Detection & Manifest Integration  
**Date:** 2026-11-22  
**Status:** COMPLETE & PASSING ALL QUALITY GATES  

---

## 1. Executive Summary & Authorization Context

Following the implementation and acceptance of M05 Prompt 3 (Formula Lexer, Parser & Strongly-Typed AST), implementation was authorized for **M05 Prompt 4: Dependency Graph, Cycle Detection & Canonical Manifest Integration**.

Prompt 4 completes the analytical pipeline of Milestone M05 by constructing a directed formula calculation graph, performing bounded range expansion, detecting direct and transitive circular references via Tarjan's Strongly Connected Components (SCC) algorithm, enforcing the FR-5.2 incomplete dependency status guard, cataloging volatile Excel functions, and synthesizing the root M01 `DiscoveryManifest` by bridging M04 spatial table boundaries with M05 verified semantic column profiles.

### Scope Boundaries Enforced
- **Zero Formula Recalculation:** The calculation graph strictly maps dependency topology. No formula values, calculation engines, or worksheet recalculations are performed.
- **Frozen Modules Intact:** M01 (`excel_intel/core/`), M02 (`crates/excel_intel_rs/`), M03 (`excel_intel/inspection/`), and M04 (`excel_intel/spatial/`) remain completely unmodified.
- **Zero Autonomous Commits/Pushes:** All code and evidence artifacts remain in the local working directory.

---

## 2. Deliverables Summary

### 2.1 Production Modules: `excel_intel/formulas/`
1. `excel_intel/formulas/cycle_detector.py`
   - Deterministic implementation of Tarjan's Strongly Connected Components (SCC) algorithm running in $O(|V| + |E|)$ time.
   - Detects both single-node self-loops (direct circular references) and multi-node SCCs (transitive calculation cycles).
   - Reconstructs closed cycle paths as ordered sequences of node IDs starting and ending at the same node (e.g. `['Sheet1!A1', 'Sheet1!B1', 'Sheet1!A1']`).

2. `excel_intel/formulas/graph.py`
   - Directed calculation graph data structures:
     - `DependencyNodeType`: Categorization enum (`CELL`, `RANGE`, `NAMED_RANGE`, `EXTERNAL`, `STRUCTURED_TABLE`).
     - `DependencyNode`: Immutable Pydantic v2 node representation.
     - `CycleStatus`: Discrete cycle outcome guard (`NO_CYCLES`, `CYCLES_DETECTED`, `UNCERTAIN_INCOMPLETE_DEPENDENCIES`).
     - `FormulaGraphReport`: Comprehensive analytical output model containing node counts, edge counts, cycle status, circular paths, volatile cells, unparsed cells, and unsupported cells, with `.to_formula_graph_metadata()` lossless projection to M01.
   - `FormulaDependencyGraph`:
     - Directed edge semantics: Directed edge $(u \rightarrow v)$ strictly indicates that $v$ depends on precedent $u$ ($u$ is an input to $v$; $v$ is a dependent of $u$).
     - Bounded range expansion (FR-4.2): Compact ranges ($\le 1,000$ cells) expand into discrete cell edges $(c \rightarrow v)$; large ranges ($> 1,000$ cells) or unbounded full columns/rows (`A:A`, `1:1`) are stored as single $O(1)$ `RangeNode` hyper-edges $(R \rightarrow v)$.
     - Direct range containment cycle detection (FR-5.1): If formula cell $V = (s_v, r_v, c_v)$ references range $R$ on sheet $s_v$ containing coordinate $(r_v, c_v)$, immediate circular reference is flagged.
     - Volatile function cataloging (FR-5.3): Catalogs calls to `NOW`, `TODAY`, `RAND`, `RANDBETWEEN`, `OFFSET`, `INDIRECT`, `INFO`, and `CELL` into `volatile_cells`.
     - Incomplete graph invariant (FR-5.2): If any formula in the workbook failed parsing (`PARSE_ERROR`) or contained unsupported syntax (`UNSUPPORTED_SYNTAX`), `is_complete` is set to `False`. When `is_complete == False`, the graph **STRICTLY CANNOT claim `has_cycles = False` with certainty**; it must report `cycle_status = CycleStatus.UNCERTAIN_INCOMPLETE_DEPENDENCIES`.
     - Multi-tier safety caps: `MAX_RANGE_EXPANSION = 1_000`, `MAX_GRAPH_NODES = 50_000`, `MAX_GRAPH_EDGES = 100_000`.

3. `excel_intel/formulas/manifest.py`
   - Canonical M01 DiscoveryManifest Synthesis Facade (`build_discovery_manifest()`):
     - Maps verified column types from `RegionTypeReport.to_m01_inferred_types()` to M04 `SpatialDetector.export_to_table_metadata_list()`.
     - Projects `FormulaGraphReport` to canonical M01 `FormulaGraphMetadata`.
     - Synthesizes and validates root M01 `DiscoveryManifest` with file metadata, SHA-256 digest validation, spatial tables, and formula graph metadata with zero data fabrication.

4. `excel_intel/formulas/__init__.py`
   - Export of all public graph, cycle detection, and manifest builder components.

### 2.2 Test Suite Expansion
- `tests/test_m05_formula_graph.py` (6 tests): Precedent-dependent edge orientation, bounded compact range expansion, large range hyper-edges, full col/row ranges, volatile function indexing, external workbooks, and structured references.
- `tests/test_m05_cycle_detection.py` (8 tests): Standalone Tarjan SCC, acyclic DAGs (`NO_CYCLES`), direct self-loops, direct range containment cycles, indirect transitive cycles, incomplete graph invariant on unparsed formulas and unsupported syntax (`UNCERTAIN_INCOMPLETE_DEPENDENCIES`), and confirmed cycles in incomplete graphs.
- `tests/test_m05_manifest_integration.py` (3 tests): End-to-end `DiscoveryManifest` synthesis, SHA-256 length validation, and missing verified types error handling.

---

## 3. Architecture & Contract Compliance Verification

| Requirement | Contract Specification | Implementation Evidence | Verification Result |
| :--- | :--- | :--- | :--- |
| **FR-4.1 (Edge Semantics)** | Directed edge $(u \rightarrow v)$ means $v$ depends on $u$ | `FormulaDependencyGraph._add_edge(precedent, dependent)` | **PASS** |
| **FR-4.2 (Bounded Expansion)** | Ranges $\le 1,000$ cells expand; $> 1,000$ cells or `A:A` stay `RangeNode` | Verified in `test_bounded_range_expansion_compact_range` & `test_large_range_hyper_edge_bounding` | **PASS** |
| **FR-5.1 (Direct Containment)**| Formula cell $V \in R$ flagged as immediate circular reference | Checked in `add_formula()` and verified in `test_direct_range_containment_cycle` | **PASS** |
| **FR-5.1 (Transitive Cycles)** | Tarjan's SCC identifies multi-node calculation cycles | Implemented in `CycleDetector` and verified in `test_indirect_transitive_cycle` | **PASS** |
| **FR-5.2 (Incomplete Guard)** | Incomplete dependencies strictly report `UNCERTAIN_INCOMPLETE_DEPENDENCIES` | Enforced in `analyze()` and verified in `test_incomplete_graph_invariant_*` | **PASS** |
| **FR-5.3 (Volatile Catalog)** | Catalogs `NOW`, `TODAY`, `RAND`, `OFFSET`, `INDIRECT`, etc. | Evaluated via AST traversal and verified in `test_volatile_function_cataloging` | **PASS** |
| **FR-6.1 (TableMetadata Bridge)**| Supplies verified column types to M04 `export_to_table_metadata_list()` | Implemented in `build_discovery_manifest()` without type fabrication | **PASS** |
| **FR-6.2 (Manifest Assembly)** | Combines `list[TableMetadata]` and `FormulaGraphMetadata` into `DiscoveryManifest` | Verified in `test_build_discovery_manifest_success` | **PASS** |

---

## 4. Test Verification & Quality Gate Results

### 4.1 Focused Formula & Manifest Test Suite
```
py -3.12 -m pytest tests/test_m05_formula_*.py tests/test_m05_cycle_detection.py tests/test_m05_manifest_integration.py -v
============================= 57 passed in 1.12s ==============================
```

### 4.2 Full Python 3.12 Regression Suite
```
py -3.12 -m pytest tests/ -q
345 passed in 15.6s
```

### 4.3 Full Python 3.13 Regression Suite
```
py -3.13 -m pytest tests/ -q
345 passed in 15.4s
```

### 4.4 Rust Native Engine Test Suite (`excel_intel_rs`)
```
cargo test --manifest-path crates/excel_intel_rs/Cargo.toml
test result: ok. 60 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.18s
```

---

## 5. Frozen Module Audit & Integrity Verification

- `excel_intel/core/` (M01): Zero diff against HEAD.
- `crates/excel_intel_rs/` (M02): Zero diff against HEAD.
- `excel_intel/spatial/` (M04): Zero diff against HEAD.
- `excel_intel/inspection/` (M03): Confirmed identical to previously audited Nov 21 streaming iterparse baseline.
- Zero autonomous git commits or pushes executed.

---

## 6. SHA-256 Synchronization Verification

Both copies of this evidence report are verified identical:
- Root: `M05_PROMPT_4_EVIDENCE_REPORT.md`
- Mirror: `docs/milestones/m05/M05_PROMPT_4_EVIDENCE_REPORT.md`
- Status: Synchronized and verified bit-for-bit identical via PowerShell `Get-FileHash` SHA-256.
