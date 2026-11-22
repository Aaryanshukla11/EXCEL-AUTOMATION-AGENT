# M05 PROMPT 4 EVIDENCE REPORT: HARDENED DEPENDENCY GRAPH, CYCLE DETECTION & MANIFEST ADAPTER

**Milestone:** M05 — Semantic Type & Formula Dependency Analysis  
**Stage:** Prompt 4 — Hardened Dependency Graph, Cycle Detection & Manifest Integration  
**Date:** 2026-11-23  
**Branch:** `feat/m05-prompt4-dependency-dag`  
**Status:** COMPLETE & PASSING ALL QUALITY GATES  

---

## 1. Executive Summary & Authorization Context

Following the authorization to implement and harden **M05 Prompt 4** on feature branch `feat/m05-prompt4-dependency-dag`, this evidence report documents the complete implementation, architectural hardening, and multi-environment verification of the Excel Formula Calculation Dependency Graph, Cycle Detection Subsystem, and Downstream Manifest Adapter.

All identified technical gaps from the M05 Scope Recovery Plan have been fully resolved:
1. **Defined Names Resolution:** Full resolution for both workbook-level and sheet-scoped defined names with sheet-level precedence, recursive alias resolution, cycle detection for mutually recursive defined names, and explicit `UNRESOLVED` dependency tracking.
2. **Dynamic Spill Reference Semantics:** First-class modeling of Excel dynamic array spill references (`A1#`, `Sheet2!B5#`), preserving anchor coordinates, creating `DYNAMIC_SPILL` nodes, setting `has_dynamic_spills = True`, and enforcing `cycle_status = POTENTIAL_CYCLES_UNVERIFIED`.
3. **Safety Caps & Deterministic Degradation:** Strict multi-tier resource caps (`MAX_GRAPH_NODES = 50_000`, `MAX_GRAPH_EDGES = 100_000`, `MAX_RANGE_EXPANSION = 1_000`). Bounded degradation prevents silent edge dropping: sets `is_complete = False` and logs granular entries in `incompleteness_reasons`.
4. **Recursion-Safe Iterative Tarjan SCC:** Hardened `cycle_detector.py` replacing recursive calls with explicit call-stack simulation and iterative BFS cycle path reconstruction, ensuring 100% recursion safety on arbitrarily deep calculation graphs (verified up to 1,500+ node chains without `RecursionError`).
5. **Architectural Manifest Facade Relocation:** Relocated the manifest builder from `excel_intel/formulas/manifest.py` to `excel_intel/adapters/manifest_adapter.py`, preserving frozen M01 core contracts and providing clean separation of concerns.

### Scope Boundaries Enforced
- **Zero Formula Recalculation:** The calculation graph statically analyzes formula AST structure and dependency topology with zero formula evaluation (`eval()`, `exec()`) or recalculation.
- **Frozen Modules Intact:** M01 (`excel_intel/core/`), M02 (`crates/excel_intel_rs/`), M03 (`excel_intel/inspection/`), and M04 (`excel_intel/spatial/`) remain completely unmodified.
- **Strict Branch Isolation:** All implementation and verification performed exclusively on `feat/m05-prompt4-dependency-dag` without modifying `main` or executing premature pushes.

---

## 2. Production Architecture & Deliverables

### 2.1 Production Modules: `excel_intel/formulas/` & `excel_intel/adapters/`

1. `excel_intel/formulas/cycle_detector.py`
   - Deterministic implementation of Tarjan's Strongly Connected Components (SCC) algorithm running in $O(|V| + |E|)$ time.
   - Iterative call-stack simulation (`_strongconnect_iterative`) eliminating Python recursion limits.
   - Iterative BFS shortest-cycle path reconstruction (`_reconstruct_cycle_path`) within SCCs.
   - Accurately detects direct self-loops (`[A1, A1]`), multi-node transitive cycles (`[A1, B1, C1, A1]`), and containment cycles.

2. `excel_intel/formulas/graph.py`
   - `DependencyNodeType` enum: `CELL`, `RANGE`, `NAMED_RANGE`, `EXTERNAL`, `STRUCTURED_TABLE`, `DYNAMIC_SPILL`, `UNRESOLVED`.
   - `CycleStatus` enum: `NO_CYCLES` (verified), `CYCLES_DETECTED`, `POTENTIAL_CYCLES_UNVERIFIED` (incomplete / unverified).
   - `DynamicSpillReference`: Immutable AST representation preserving `anchor_cell`, `raw_reference`, and `sheet_name`.
   - `FormulaGraphReport`: Immutable Pydantic v2 reporting model with `.to_formula_graph_metadata()` lossless projection to canonical M01 `FormulaGraphMetadata`.
   - `FormulaDependencyGraph`:
     - Directed edge semantics: Directed edge $(u \rightarrow v)$ strictly indicates that dependent $v$ depends on precedent $u$.
     - Defined Names Pre-Scan & Resolver: Lexer-based token inspection resolving names against `sheet_defined_names` (precedence) and `global_defined_names`, linking underlying targets to formula cells, and flagging recursive cycles.
     - Dynamic Spill Representation: Creates `CELL` (anchor) $\rightarrow$ `DYNAMIC_SPILL` $\rightarrow$ `dependent` edges, setting `has_dynamic_spills = True` and `is_complete = False`.
     - Bounded Range Expansion (FR-4.2): Compact ranges ($\le 1,000$ cells) expand to individual cell edges; large ranges ($> 1,000$ cells) or unbounded full columns/rows (`A:A`, `1:1`) are stored as single $O(1)$ `RangeNode` hyper-edges.
     - Direct range containment cycle detection (FR-5.1): Immediate circular reference flagged if formula cell falls inside referenced range bounds.
     - Volatile function cataloging (FR-5.3): Catalogs calls to `NOW`, `TODAY`, `RAND`, `RANDBETWEEN`, `OFFSET`, `INDIRECT`, `INFO`, and `CELL`.
     - Safety Caps & Limits: Enforces `MAX_GRAPH_NODES = 50_000`, `MAX_GRAPH_EDGES = 100_000`, and range expansion fallback when edge cap would be breached.

3. `excel_intel/adapters/manifest_adapter.py`
   - Canonical M01 DiscoveryManifest Synthesis Adapter (`build_discovery_manifest()`):
     - Maps verified column types from `RegionTypeReport.to_m01_inferred_types()` to M04 `SpatialDetector.export_to_table_metadata_list()`.
     - Projects `FormulaGraphReport` to canonical M01 `FormulaGraphMetadata`.
     - Synthesizes and validates root M01 `DiscoveryManifest` with file metadata, 64-char SHA-256 validation, spatial tables, and formula graph metadata with zero data fabrication.

4. `excel_intel/formulas/__init__.py`
   - Clean public export surface strictly reserved for authorized Prompt 3 components (models, lexer, parser).

---

## 3. Architecture & Contract Compliance Verification

| Requirement | Contract Specification | Implementation Evidence | Verification Result |
| :--- | :--- | :--- | :--- |
| **FR-4.1 (Edge Semantics)** | Directed edge $(u \rightarrow v)$ indicates $v$ depends on $u$ | `FormulaDependencyGraph._add_edge(precedent, dependent)` | **PASS** |
| **FR-4.2 (Bounded Expansion)** | Ranges $\le 1,000$ expand; $> 1,000$ or `A:A`/`1:1` stay `RangeNode` | Verified in `test_bounded_range_expansion_compact_range` & `test_large_range_hyper_edge_bounding` | **PASS** |
| **FR-4.3 (Defined Names)** | Workbook & sheet-scoped names with precedence & cycle detection | Verified in `test_defined_names_workbook_level_resolution`, `test_defined_names_sheet_scoped_precedence`, `test_defined_names_recursive_cycle` | **PASS** |
| **FR-4.4 (Dynamic Spills)** | Preserves anchor coordinates, `DYNAMIC_SPILL` node type | Verified in `test_dynamic_spill_reference_semantics` & `test_dynamic_spill_cycle` | **PASS** |
| **FR-5.1 (Direct Containment)**| Formula cell $V \in R$ flagged as immediate circular reference | Checked in `add_formula()` and verified in `test_direct_range_containment_cycle` | **PASS** |
| **FR-5.1 (Transitive Cycles)** | Tarjan's SCC identifies multi-node calculation cycles | Implemented in `CycleDetector` and verified in `test_indirect_transitive_cycle` | **PASS** |
| **FR-5.2 (Incomplete Guard)** | Incomplete dependencies strictly report `POTENTIAL_CYCLES_UNVERIFIED` | Enforced in `analyze()` and verified in `test_incomplete_graph_invariant_*` | **PASS** |
| **FR-5.3 (Volatile Catalog)** | Catalogs `NOW`, `TODAY`, `RAND`, `OFFSET`, `INDIRECT`, etc. | Evaluated via AST traversal and verified in `test_volatile_function_cataloging` | **PASS** |
| **FR-5.4 (Resource Caps)** | Strict node (50k) and edge (100k) caps with graceful incomplete reporting | Verified in `test_resource_safety_limits_nodes_and_edges` & `test_range_expansion_edge_cap_fallback` | **PASS** |
| **FR-5.5 (Recursion Safety)** | Iterative Tarjan SCC handles deep graphs (>1000 nodes) without `RecursionError` | Verified in `test_iterative_tarjan_deep_chain_acyclic` & `test_iterative_tarjan_deep_chain_cycle` | **PASS** |
| **FR-6.1 (TableMetadata Bridge)**| Supplies verified column types to M04 `export_to_table_metadata_list()` | Implemented in `manifest_adapter.py` without type fabrication | **PASS** |
| **FR-6.2 (Manifest Assembly)** | Combines `list[TableMetadata]` and `FormulaGraphMetadata` into `DiscoveryManifest` | Verified in `test_build_discovery_manifest_success` | **PASS** |

---

## 4. Test Verification & Quality Gate Results

### 4.1 M05 Prompt 4 Hardened Test Suite (30 Tests)
```
py -3.12 -m pytest tests/test_m05_cycle_detection.py tests/test_m05_formula_graph.py tests/test_m05_manifest_integration.py tests/test_m05_formula_integration.py -v
============================= 30 passed in 1.02s ==============================
```
- `tests/test_m05_cycle_detection.py`: 10 passed (including 1500-node iterative Tarjan recursion safety tests).
- `tests/test_m05_formula_graph.py`: 15 passed (including defined names, dynamic spill references, and resource safety caps).
- `tests/test_m05_manifest_integration.py`: 3 passed (relocated manifest adapter verification).
- `tests/test_m05_formula_integration.py`: 2 passed (precedent extraction tests on feature branch).

### 4.2 M05 Prompt 3 Regression Suite (41 Tests)
```
py -3.12 -m pytest tests/test_m05_formula_lexer.py tests/test_m05_formula_parser.py tests/test_m05_formula_models.py tests/test_m05_formula_edge_cases.py tests/test_m05_formula_unsupported.py -q
41 passed in 0.43s
```

### 4.3 M05 Prompt 2 Regression Suite (50 Tests)
```
py -3.12 -m pytest tests/test_m05_pattern_detector.py tests/test_m05_sampling.py tests/test_m05_type_inferrer.py tests/test_m05_type_integration.py tests/test_m05_type_models.py -q
50 passed in 2.21s
```

### 4.4 Full Platform Regression Suites

#### Python 3.12:
```
py -3.12 -m pytest tests/ -q
356 passed in 15.1s
```

#### Python 3.13:
```
py -3.13 -m pytest tests/ -q
356 passed in 15.0s
```

#### Rust Native Engine (`excel_intel_rs`):
```
cargo test --manifest-path crates/excel_intel_rs/Cargo.toml
test result: ok. 60 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.68s
```

---

## 5. Scope Recovery & Working Tree Integrity

- Current branch: `feat/m05-prompt4-dependency-dag`
- Working tree status: All production and test modifications verified.
- Uncommitted changes are staged/ready for project owner inspection and authorization.
- Zero premature pushes or commits executed.
