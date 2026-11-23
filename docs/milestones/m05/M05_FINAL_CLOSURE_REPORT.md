# M05 FINAL CLOSURE & QUALITY CERTIFICATION REPORT

**Milestone:** M05 — Semantic Type & Formula Dependency Analysis  
**Date:** 2026-11-23  
**Status:** CLOSED  
**Branch:** `main`  
**Merge Commit:** `01a00d18067fad3f7225a9bfea25c2261b771bcc`  

---

## 1. Executive Summary

Milestone **M05: Semantic Type & Formula Dependency Analysis** is formally **CLOSED**. All authorized stages across Prompts 1 through 4 have been implemented, hardened, independently audited, verified across multiple runtimes, and integrated into `main` via merge commit `01a00d1`.

The platform now features:
1. **A purely deterministic, statistically evaluated Semantic Type Inference Engine** with discrete inference states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`), provisional 0.80 ambiguity guards, and deterministic 2D sliding-window coordinate sampling bounded strictly to 10,000 cells per region.
2. **A pure-Python Excel Formula Lexer & Operator-Precedence Parser** producing immutable strongly-typed Pydantic v2 AST representations with exact span provenance, explicit three-state result contracts (`PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, `PARSE_ERROR`), and zero runtime crashes on malformed expressions.
3. **A Directed Calculation Dependency Graph & Cycle Detection Subsystem** mapping precedent-dependent calculation topology ($u \rightarrow v$), resolving defined names (workbook and sheet-scoped), preserving dynamic spill references (`A1#`), enforcing multi-tier safety caps (50,000 nodes, 100,000 edges), cataloging volatile Excel functions, and detecting circular references via a hardened, recursion-safe iterative implementation of Tarjan's Strongly Connected Components (SCC) algorithm.
4. **A Downstream Canonical Manifest Synthesis Adapter** (`excel_intel/adapters/manifest_adapter.py`) bridging verified semantic column types and formula graph metadata with M04 spatial table boundaries to produce the canonical M01 `DiscoveryManifest` without modifying frozen core contracts.

### Architectural Invariants Strictly Maintained
- **Zero Formula Recalculation:** The platform statically analyzes formula syntax and calculation topology; zero formula evaluation (`eval()`, `exec()`) or runtime calculation is performed.
- **Defensive Memory & Complexity Bounds:** Bounded 2D sampling ($\le 10,000$ cells); bounded range expansion ($\le 1,000$ cells); bounded graph dimensions ($\le 50,000$ nodes, $\le 100,000$ edges); $O(V + E)$ cycle detection.
- **Frozen Modules Integrity:** Core modules M01 (`excel_intel/core/`), M02 (`crates/excel_intel_rs/`), M03 (`excel_intel/inspection/`), and M04 (`excel_intel/spatial/`) remain completely unmodified.
- **Complete Test Verification:** 422 total automated tests passing cleanly across Python 3.12 (362 tests), Python 3.13 (362 tests), and Rust Cargo (60 tests).

---

## 2. Milestone Architecture & Component Inventory

```text
excel_intel/
├── types/                     # Prompt 2: Semantic Type Inference Engine
│   ├── __init__.py            # Public exports
│   ├── models.py              # Inferred types, states, sampling diagnostics, RegionTypeReport
│   ├── pattern_detector.py    # Fine-grained lexical regex and numeric classification
│   ├── sampling.py            # Deterministic 3-band 2D coordinate selector (<= 10,000 cells)
│   └── type_inferrer.py       # Column type inferrer with provisional 0.80 ambiguity guard
├── formulas/                  # Prompts 3 & 4: Formula Lexer, Parser & Calculation DAG
│   ├── __init__.py            # Public exports (strictly Prompt 3 models, lexer, parser)
│   ├── models.py              # Immutable Pydantic v2 AST contracts, span provenance
│   ├── lexer.py               # Deterministic tokenizer with span tracking (<= 16k chars, 4k tokens)
│   ├── parser.py              # Operator-precedence parser with FR-3.3 status guard (<= 64 depth)
│   ├── cycle_detector.py      # Hardened iterative Tarjan SCC cycle detector (recursion-safe)
│   └── graph.py               # Directed calculation DAG with bounded range expansion & defined names
└── adapters/                  # Downstream Integration Adapters
    ├── __init__.py            # Public exports
    └── manifest_adapter.py    # Canonical DiscoveryManifest synthesis adapter (FR-6)
```

---

## 3. Four-Prompt Implementation Lifecycle Summary

### Prompt 1: Architecture Audit, Requirements & Plan (Accepted)
- Completed comprehensive architecture inspection of existing frozen modules (M01–M04).
- Defined discrete inference states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`) and designated 0.80 support score as provisional.
- Codified strict 2D deterministic sampling budget ($\le 10,000$ cells) and lossy M01 projection table.
- Established explicit EBNF formula grammar replacing universal compatibility claims.

### Prompt 2: Semantic Type Inference Engine (Accepted)
- Implemented pattern detection across integers, decimals, currency, percentages, dates, ISO timestamps, and UUIDs.
- Built deterministic 3-band 2D coordinate sampler respecting the 10,000-cell bound.
- Enforced provisional 0.80 ambiguity threshold and losslessly projected verified types to canonical M01 `ColumnProfile`.

### Prompt 3: Formula Lexer, Parser & Strongly-Typed AST (Accepted)
- Built deterministic tokenizer with exact span provenance, multi-character operators, external workbook prefixes, and structured table references.
- Implemented operator-precedence parser adhering to FR-3.3 three-state result contract (`PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, `PARSE_ERROR`).
- Enforced recursion limit (`MAX_NESTING_DEPTH = 64`) and AST node limit (`MAX_AST_NODES = 10_000`).

### Prompt 4: Hardened Dependency Graph, Cycle Detection & Manifest Adapter (Accepted & Merged)
- Built directed calculation graph where directed edge $(u \rightarrow v)$ indicates dependent $v$ depends on precedent $u$.
- Hardened Defined Names resolution supporting workbook-level and sheet-scoped names with precedence, range targets, unresolved tracking, and recursive cycle detection.
- Dynamic Spill References modeled with anchor coordinates, `DYNAMIC_SPILL` node type, and `POTENTIAL_CYCLES_UNVERIFIED` status guard.
- Hardened iterative Tarjan's SCC cycle detector eliminating Python recursion limits.
- Enforced strict resource limits (`MAX_GRAPH_NODES = 50_000`, `MAX_GRAPH_EDGES = 100_000`) with deterministic degradation.
- Relocated canonical manifest synthesizer to `excel_intel/adapters/manifest_adapter.py`.
- Integrated cleanly into `main` via merge commit `01a00d1`.

---

## 4. Acceptance Criteria & Requirements Traceability Matrix

| Requirement | Contract Specification | Implementation Evidence | Status |
| :--- | :--- | :--- | :--- |
| **FR-1.1** | Zone-constrained sampling strictly within `SemanticZoneType.BODY` | `tests/test_m05_type_integration.py` | **PASS** |
| **FR-1.2** | Discrete inference states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`)| `excel_intel/types/models.py`, `type_inferrer.py` | **PASS** |
| **FR-1.3** | Strict precedence order: Null $\rightarrow$ Insufficient $\rightarrow$ Ambiguity $\rightarrow$ Homogeneity | `tests/test_m05_type_inferrer.py` | **PASS** |
| **FR-1.4** | Multi-pattern value classification (Integer, Decimal, Currency, Date, etc.) | `excel_intel/types/pattern_detector.py` | **PASS** |
| **FR-1.5** | Statistical metric aggregation ($N_{\text{total}}, N_{\text{pop}}, N_{\text{null}}, H, S$) | `tests/test_m05_type_models.py` | **PASS** |
| **FR-1.6** | Heuristic support score formulation $S = H \times (1 - \text{Penalty})$ | `excel_intel/types/type_inferrer.py` | **PASS** |
| **FR-1.7** | M01 schema carrier projection policy with `requires_human_review` gate | `RegionTypeReport.to_m01_inferred_types()` | **PASS** |
| **FR-1.8** | Complete deterministic 2D sampling budget ($\le 10,000$ cells max) | `excel_intel/types/sampling.py` | **PASS** |
| **FR-2.1** | Scoped EBNF formula grammar (arithmetic, comparison, concat, references, functions) | `excel_intel/formulas/lexer.py`, `parser.py` | **PASS** |
| **FR-2.2** | Valid/Invalid structured, 3D, and external workbook reference handling | `tests/test_m05_formula_edge_cases.py` | **PASS** |
| **FR-2.3** | Strict separation of syntax recognition from semantic calculation | Verified: zero formula recalculation | **PASS** |
| **FR-2.4** | Recognized unsupported syntax captured in `UnsupportedFormulaNode` | `tests/test_m05_formula_unsupported.py` | **PASS** |
| **FR-2.5** | Malformed formulas captured in `UnparsedFormulaNode` with diagnostic offsets | `tests/test_m05_formula_integration.py` | **PASS** |
| **FR-3.1** | Operator-precedence recursive-descent parser emitting immutable AST | `excel_intel/formulas/parser.py` | **PASS** |
| **FR-3.2** | Strongly typed immutable Pydantic v2 AST node hierarchy | `excel_intel/formulas/models.py` | **PASS** |
| **FR-3.3** | Prevention of partial parsing conflation (`PARSED_COMPLETE`, etc.) | `tests/test_m05_formula_parser.py` | **PASS** |
| **FR-4.1** | Directed calculation graph where $(u \rightarrow v)$ denotes dependent $v$ depends on $u$| `excel_intel/formulas/graph.py` | **PASS** |
| **FR-4.2** | Bounded range expansion ($\le 1,000$ cells expand; $> 1,000$ or `A:A` stay hyperedges) | `tests/test_m05_formula_graph.py` | **PASS** |
| **FR-4.3** | Defined Names resolution (workbook and sheet-scoped with precedence & cycle check)| `tests/test_m05_formula_graph.py` | **PASS** |
| **FR-4.4** | Dynamic Spill reference modeling preserving anchor coordinates | `tests/test_m05_formula_graph.py` | **PASS** |
| **FR-5.1** | Direct range containment cycles & Tarjan SCC transitive cycle detection | `tests/test_m05_cycle_detection.py` | **PASS** |
| **FR-5.2** | Incomplete graph invariant strictly enforces `POTENTIAL_CYCLES_UNVERIFIED` | `tests/test_m05_cycle_detection.py` | **PASS** |
| **FR-5.3** | Volatile function cataloging (`NOW`, `TODAY`, `RAND`, `OFFSET`, `INDIRECT`, etc.) | `tests/test_m05_formula_graph.py` | **PASS** |
| **FR-5.4** | Multi-tier resource safety limits with deterministic partial preservation | `tests/test_m05_formula_graph.py` | **PASS** |
| **FR-5.5** | Iterative call-stack simulation for Tarjan SCC preventing `RecursionError` | `tests/test_m05_cycle_detection.py` | **PASS** |
| **FR-6.1** | TableMetadata bridge supplying verified types to M04 export | `excel_intel/adapters/manifest_adapter.py` | **PASS** |
| **FR-6.2** | Canonical root `DiscoveryManifest` synthesis and validation | `tests/test_m05_manifest_integration.py` | **PASS** |
| **SCOPE-1**| Formula recalculation engine (evaluating formula results) | Out of scope for M05 (Phase 1) | **DEFERRED** |
| **SCOPE-2**| Universal 100% Excel compatibility (LAMBDA, MAP, complex UDFs) | Out of scope for M05 (Phase 1) | **DEFERRED** |
| **SCOPE-3**| Automated consolidation planning and schema mutation | Out of scope for M05 (Phase 1) | **DEFERRED** |

---

## 5. Automated Verification & Quality Gate Results

### 5.1 Python 3.12 Regression Suite
- **Command:** `py -3.12 -m pytest tests/`
- **Result:** **362 passed in 38.79s** (Exit code: 0)

### 5.2 Python 3.13 Regression Suite
- **Command:** `py -3.13 -m pytest tests/`
- **Result:** **362 passed in 22.35s** (Exit code: 0)

### 5.3 Rust Native Engine Suite (`crates/excel_intel_rs`)
- **Command:** `cargo test --manifest-path crates/excel_intel_rs/Cargo.toml`
- **Result:** **60 passed in 0.73s** (Exit code: 0)

### 5.4 Test Count Reconciliation
- Baseline prior to integration: 359 tests (feature branch) / 332 tests (main).
- Unified integration file: `tests/test_m05_formula_integration.py` combines the 3 Prompt 3 parser tests and the 2 Prompt 4 precedent extraction tests ($3 + 2 = 5$ tests).
- **Post-Merge Full Test Suite:** Exactly **362 Python tests** + **60 Rust tests** = **422 total automated tests**.

---

## 6. Technical Limitations & Boundary Disclaimers

1. **Formula Parsing & Scoped Grammar:** Scoped to arithmetic, comparison, string concatenation, cell references (`A1`), whole column/row ranges (`A:A`, `1:1`), 3D sheet ranges, structured table references (`Table1[Sales]`), external workbook prefixes, function calls, and rectangular array literals. Dynamic array spill operator `#` is recognized and classified as `UnsupportedFormulaNode` (`DYNAMIC_ARRAY_SPILL`), and lambda helpers (`LAMBDA`, `MAP`, `REDUCE`) are unsupported. Malformed formulas are safely captured as `UnparsedFormulaNode` without raising unhandled exceptions.
2. **Dependency Graph Completeness:** The dependency graph strictly analyzes static syntactic AST references. If a formula contains unsupported syntax, parse errors, dynamic spill references, or unresolved defined names, the graph deterministically marks `is_complete = False` and sets `cycle_status = POTENTIAL_CYCLES_UNVERIFIED`.
3. **Defined Names Resolution:** Static resolution against OpenXML declared defined names (`global_defined_names` and `sheet_defined_names`). Resolves single cells, ranges, and alias chains with cycle detection. Does not evaluate formulas within defined names (e.g. `=OFFSET(...)`) as calculation values.
4. **Dynamic Spill References:** Excel `#` operator (e.g. `A1#`) is modeled by anchoring to the spill origin cell (`A1`), linking `A1 -> A1# -> dependent`. The runtime extent (height/width) of the spilled array cannot be computed without formula execution, so `has_dynamic_spills = True`, `is_complete = False`, and `POTENTIAL_CYCLES_UNVERIFIED` are set. Dependent cells within the spill shadow are not fabricated.
5. **Graph Safety Limits:** Hard bounds enforced: `MAX_GRAPH_NODES = 50_000`, `MAX_GRAPH_EDGES = 100_000`, `MAX_RANGE_EXPANSION = 1_000`. Range expansion dynamically falls back to hyperedges if expanding would breach the edge cap. When caps are reached, graph ingestion safely stops expanding and marks `is_complete = False` with diagnostic reasons in `incompleteness_reasons`.
6. **Cycle Detection:** Tarjan's SCC algorithm runs in $O(V + E)$ time with iterative call-stack simulation and iterative BFS cycle reconstruction, preventing recursion-depth errors. When dependencies are incomplete, cycle detection flags confirmed cycles as `CYCLES_DETECTED`, but acyclic states report `POTENTIAL_CYCLES_UNVERIFIED` rather than claiming verified absence of cycles.
7. **Manifest Adapter Integration:** Downstream adapter located at `excel_intel/adapters/manifest_adapter.py`. Relies on M04 `SpatialDetector.export_to_table_metadata_list()` and projects `RegionTypeReport.to_m01_inferred_types()` and `FormulaGraphReport.to_formula_graph_metadata()`. Validates 64-character SHA-256 hex string and non-empty verified types. Does not modify frozen M01 core definitions.

---

## 7. Deferred Scope & Remaining Phase 1 Risks

1. **Formula Recalculation Engine:** Deferred to Phase 1. M05 delivers dependency topology and static ASTs only.
2. **Live External Workbook Resolution:** Deferred to Phase 1. External workbooks are indexed syntactically as `ExternalNode`; live file-system/network resolution is deferred.
3. **Automated Consolidation Planning:** Deferred to Phase 1. Columns with states `UNKNOWN`, `AMBIGUOUS`, or `INSUFFICIENT_DATA` remain gated behind Human-in-the-Loop review.

---

## 8. Final Milestone Decision

Every mandatory functional requirement (FR-1 through FR-6) and non-functional requirement (NFR-1 through NFR-5) is fully satisfied, backed by empirical test evidence across Python 3.12, Python 3.13, and Rust Cargo suites, and integrated cleanly into `main` (`commit 01a00d1`).

**Final Milestone Status:** **`CLOSED`**
