# Milestone M05 — Semantic Type & Formula Analysis
## Document 4 of 4: Comprehensive Test & Acceptance Strategy

**Date:** 2026-11-22  
**Milestone:** M05 — Semantic Type & Formula Analysis  
**Stage:** Prompt 1 of 4 (Architecture Inspection, Requirements Discovery & Planning)  
**Status:** COMPLETE (Planning & Audit Only — Zero Code Modification)  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes)

---

## 1. Test Philosophy & Multi-Language Quality Gates

The test strategy for Milestone M05 enforces absolute determinism, mathematical rigor, and zero silent data corruption.

### Quality Gate Requirements:
Every prompt execution must pass all quality gates across both supported Python versions and the underlying Rust streaming crate:

| Suite / Gate | Execution Command | Target Outcome |
| :--- | :--- | :---: |
| **Python 3.12 Regression** | `py -3.12 -m pytest tests/` | **100% green (zero failures)** |
| **Python 3.13 Regression** | `py -3.13 -m pytest tests/` | **100% green (zero failures)** |
| **M05 Focused Suite** | `py -3.12 -m pytest (Get-ChildItem tests/test_m05_*.py).FullName` | **100% green** |
| **Rust Unit Tests** | `cargo test --manifest-path crates/excel_intel_rs/Cargo.toml` | **60 passed; 0 failed** |
| **Rust Formatting** | `cargo fmt --check --manifest-path crates/excel_intel_rs/Cargo.toml` | **Clean (0 diff)** |
| **Rust Clippy Linter** | `cargo clippy --manifest-path crates/excel_intel_rs/Cargo.toml -- -D warnings` | **0 warnings** |
| **Source Immutability** | SHA-256 verification of test workbooks | **Bit-for-bit identical** |
| **Frozen Code Check** | `git diff excel_intel/core/ crates/excel_intel_rs/` | **0 lines modified** |

---

## 2. Categorized Test Scenarios & Coverage Matrix

### 2.1 Category A: Semantic Type Inference & Inference States (`tests/test_m05_types.py`)

| Test Case ID | Test Scenario Description | Input Data Conditions | Expected Outcome & Assertions |
| :--- | :--- | :--- | :--- |
| **TYPE-01** | Pure Integer Column | Cells containing `100`, `200`, `-50`, `0`. | `state = InferenceState.INFERRED`, `candidate_type = ColumnType.INTEGER`, `support_score = 1.0`, `nullable = False`. |
| **TYPE-02** | Pure Decimal / Float Column | Cells containing `3.14`, `-0.01`, `100.50`. | `state = InferenceState.INFERRED`, `candidate_type = ColumnType.DECIMAL`, `support_score = 1.0`, `nullable = False`. |
| **TYPE-03** | Currency & Formatted Decimals | Strings `$1,250.00`, `€500.25`, `($150.00)`. | `state = InferenceState.INFERRED`, `candidate_type = ColumnType.DECIMAL`, `category = ValueCategory.CURRENCY`, `support_score = 1.0`. |
| **TYPE-04** | Percentage Strings | Strings `15.5%`, `0.25%`, `-5.0%`. | `state = InferenceState.INFERRED`, `candidate_type = ColumnType.DECIMAL`, `category = ValueCategory.PERCENTAGE`, `support_score = 1.0`. |
| **TYPE-05** | Date Formats & Excel Serials | ISO dates `2024-01-15`, US `01/15/2024`, numeric serials `45300.0` with date style. | `state = InferenceState.INFERRED`, `candidate_type = ColumnType.DATE`, `support_score >= 0.95`. |
| **TYPE-06** | Text Booleans | Strings `TRUE`, `FALSE`, `true`, `false`, `Yes`, `No`. | `state = InferenceState.INFERRED`, `candidate_type = ColumnType.BOOLEAN`, `support_score >= 0.95`. |
| **TYPE-07** | Mixed Null Representations | Empty cells, `None`, `""`, `N/A`, `-`, `#N/A`. | `nullable = True`, correct `nullability_ratio`. |
| **TYPE-08** | Bimodal Type Distribution | 55% numbers, 45% strings. | `state = InferenceState.AMBIGUOUS`, `candidate_type = None`, `support_score < 0.80`, `is_ambiguous = True`, `requires_human_review = True`. Downstream M01 `type_confidence < 0.80`. |
| **TYPE-09** | 100% Blank Column | Column with zero populated values in `BODY`. | `state = InferenceState.UNKNOWN`, `candidate_type = None`, `support_score = 0.0`, `nullable = True`, `is_ambiguous = False`. Downstream M01 `type_confidence = 0.0`. Never confident string! |
| **TYPE-10** | Insufficient Sample Size | Table has 3 rows ($N_{\text{pop}} = 3 < 5$). | `state = InferenceState.INSUFFICIENT_DATA`, `candidate_type = T_{\text{pred}}` (prov.), `support_score = S`, `requires_human_review = True`. M01 projection preserves $S$. |
| **TYPE-11** | Semantic Ambiguity with High Homogeneity | 100 rows containing `"01/02/03"` (unresolved date order). | `state = InferenceState.AMBIGUOUS`, `candidate_type = None`, `support_score = 1.0`, `is_ambiguous = True`, `requires_human_review = True`. Proves AMBIGUOUS does not require $S < 0.80$. |
| **TYPE-12** | Hard Cell Budget Enforcement | Ultra-wide table: 200 cols $\times$ 1,000 rows ($200\text{k cells}$). | Slices $R_{\text{sample}} = \min(1000, \lfloor 10000/200 \rfloor) = 50$ rows. Total sampled cells $\le 10,000$ strictly. |
| **TYPE-13** | Ultra-Wide Table Bounds | Table with $C = 12,000$ columns. | Slices $C_{\text{sample}} = 10,000$, $R_{\text{sample}} = 1$. Total sampled cells $\le 10,000$. 3-band column selection covers left, middle, right. |
| **TYPE-14** | Zone Isolation Integrity | Header has text, Body has integers, Summary has formula. | Column in `BODY` is `INTEGER`; header and summary excluded. |
| **TYPE-15** | Merged Cell Span Handling | Merged cell across cols A..B in body row. | Value attributed to anchor cell; spanned empty slot not counted as null penalty. |
| **TYPE-16** | Hidden Row Annotation | Row in body is hidden via OpenXML. | Values included in type counts; flagged in sampling diagnostics. |
| **TYPE-17** | M04 Bridge Integration | `export_to_table_metadata_list()` with inferred types. | Returns valid M01 `TableMetadata` list; zero `NotImplementedError`. |

### 2.2 Category B: Formula Lexer & AST Parser (`tests/test_m05_formula_parser.py`)

| Test Case ID | Test Scenario Description | Input Formula String | Expected AST Structure |
| :--- | :--- | :--- | :--- |
| **FORM-01** | Simple Infix Arithmetic | `=A1 + B1 * 2` | `BinaryOpNode(+, A1, BinaryOpNode(*, B1, 2))` (correct precedence). Status = `PARSED_COMPLETE`. |
| **FORM-02** | Parenthetical Grouping | `=(A1 + B1) * 2` | `BinaryOpNode(*, BinaryOpNode(+, A1, B1), 2)`. Status = `PARSED_COMPLETE`. |
| **FORM-03** | 2D Range & Built-in Function | `=SUM(A1:B10)` | `FunctionCallNode(SUM, [RangeReferenceNode(A1:B10)])`. Status = `PARSED_COMPLETE`. |
| **FORM-04** | Nested Function Calls | `=IF(A1 > 0, SUM(B1:B10), 0)` | Nested function calls parsed; correct argument lists. Status = `PARSED_COMPLETE`. |
| **FORM-05** | 3D Cross-Sheet Reference | `=Sheet2!A1 + 'Sales Data'!B5` | References have `sheet_name="Sheet2"` and `sheet_name="Sales Data"`. |
| **FORM-06** | Multi-Sheet 3D Cube Range | `=SUM(Sheet1:Sheet3!A1:B5)` | Range node spanning multiple sheets. |
| **FORM-07** | External Workbook Reference | `=[Budget.xlsx]Sheet1!$A$1 * 1.1` | `is_external=True`, workbook name extracted. |
| **FORM-08** | Structured Table Reference | `=Table1[Sales] * Table1[@Tax]` | `StructuredReferenceNode` with table, column, and row specifier `@`. |
| **FORM-09** | Valid Rectangular Array Constant | `={1, 2; 3, 4}` | `ArrayLiteralNode(2x2 matrix)`. |
| **FORM-10** | Invalid Ragged Array Constant | `={1, 2; 3}` | Handled as malformed / unrecognized; Status = `PARSE_ERROR`. |
| **FORM-11** | Category B Unsupported Syntax | `=A1#` (spill operator) | `UnsupportedFormulaNode` emitted; span preserved; Status = `UNSUPPORTED_SYNTAX`. |
| **FORM-12** | Category B External Add-In | `=Bloomberg.BDP("AAPL", "PX_LAST")` | `UnsupportedFormulaNode` emitted; Status = `UNSUPPORTED_SYNTAX`. |
| **FORM-13** | Category C Malformed Syntax | `=SUM(A1:B10 +` (unclosed paren) | `UnparsedFormulaNode` emitted; error position recorded; Status = `PARSE_ERROR`. No crash. |
| **FORM-14** | Partial Parsing Guard | Formula containing unsupported sub-token | Root status is `UNSUPPORTED_SYNTAX`; not reported as `PARSED_COMPLETE`. |

### 2.3 Category C: Formula Dependency Graph & Calculation DAG (`tests/test_m05_formula_graph.py`)

| Test Case ID | Test Scenario Description | Graph Setup / Formula Network | Expected Analysis Outcome |
| :--- | :--- | :--- | :--- |
| **DAG-01** | Linear Calculation Chain | `A1=10`, `B1=A1*2`, `C1=B1+5` | Precedents of `C1` are `B1` (direct) and `A1` (transitive); dependents of `A1` are `B1`, `C1`. |
| **DAG-02** | Diamond Calculation DAG | `A1=10`, `B1=A1*2`, `B2=A1*3`, `C1=B1+B2` | Acyclic DAG; `has_cycles = False`; correct topological order. |
| **DAG-03** | Direct Self-Reference | `A1 = A1 + 1` | `has_cycles = True`, cycle `[A1, A1]`. |
| **DAG-04** | Direct Range Containment Cycle | `A5 = SUM(A1:A10)` (in cell A5) | Direct cycle detected: `A5` is inside `A1:A10`. `has_cycles = True`. |
| **DAG-05** | Indirect Multi-Cell Cycle | `A1=B1`, `B1=C1`, `C1=A1` | Tarjan SCC detects cycle `[A1, B1, C1, A1]`. `has_cycles = True`. |
| **DAG-06** | Incomplete Dependency Guard | Graph contains an unsupported formula node | `is_complete = False`, `cycle_status = UNCERTAIN_INCOMPLETE_DEPENDENCIES`. Never claims cycle-free with certainty! |
| **DAG-07** | Volatile Function Cataloging | `A1=NOW()`, `B1=OFFSET(A1,1,0)`, `C1=SUM(D1:D10)` | `volatile_cells = ["A1", "B1"]` (excludes `C1`). |
| **DAG-08** | Bounded Range Expansion | `SUM(A1:A5)` vs `SUM(A:A)` | `A1:A5` expands to 5 cell edges; `A:A` stored as single Range Node (zero memory explosion). |
| **DAG-09** | Cross-Sheet Calculation DAG | `Sheet1!A1 = Sheet2!B1 * 2` | Cross-sheet edge `Sheet2!B1 -> Sheet1!A1`. |
| **DAG-10** | External Reference Tracking | `A1 = [External.xlsx]Sheet1!B5` | Recorded in `external_references` list. |

### 2.4 Category D: Integration, Immutability & Concurrency (`tests/test_m05_integration.py`)

| Test Case ID | Test Scenario Description | Execution Scope | Expected Verification Outcome |
| :--- | :--- | :--- | :--- |
| **INT-01** | End-to-End Workbook Analysis | Realistic multi-sheet financial model | Generates complete `DiscoveryManifest` with `TableMetadata` and `FormulaGraphMetadata`. |
| **INT-02** | Source Immutability Check | Pre- and post-inspection SHA-256 | Source file SHA-256 bit-for-bit identical before and after M05 execution. |
| **INT-03** | Determinism Across Repeated Runs | Execute analysis 3 times on same workbook | Exact matching manifest IDs, bounding boxes, types, support scores, and DAG edges. |
| **INT-04** | Concurrent Multi-Workbook Isolation | 4 concurrent threads analyzing 8 distinct workbooks | Zero cross-contamination; 100% thread isolation. |

---

## 3. Measurable Acceptance Criteria & Benchmark Budgets

### 3.1 Basis for Latency & Throughput Budgets
1. **Semantic Type Inference Budget ($< 100\text{ ms} / 10\text{k cells}$):**
   - *Basis:* In Python, regex pattern matching across a compiled dictionary of 6 patterns on $10,000$ strings takes $\approx 35\text{ ms}$. With streaming chunk iteration and integer arithmetic, $100\text{ ms}$ provides a reliable $2.8\times$ engineering safety margin.
2. **Formula Lexing & Parsing Budget ($< 20\text{ \mu s} / \text{formula} \implies > 50,000\text{ formulas/sec}$):**
   - *Basis:* A pure Python recursive-descent parser for standard spreadsheet expressions (average length 15–30 characters, 5–10 tokens) executes in $12\text{ \mu s}$ on modern x86_64 cores. Budgeting $20\text{ \mu s}$ accommodates nested function calls and character span tracking.
3. **Graph Construction & Cycle Detection Budget ($< 500\text{ ms} / 10\text{k formula nodes}$):**
   - *Basis:* Tarjan's SCC algorithm runs in $O(|V| + |E|)$ time. For $10,000$ vertices and $20,000$ edges, pure Python graph traversal takes $\approx 120\text{ ms}$. A $500\text{ ms}$ budget accommodates edge deduplication and path extraction.
4. **End-to-End Workbook Analysis Budget ($< 3.0\text{ seconds}$):**
   - *Basis:* For standard workbooks (< 50 MB, < 100,000 rows, < 5,000 formulas), spatial detection takes $\approx 1.2\text{ s}$ (verified in M04). Adding $0.8\text{ s}$ for type inference and $0.3\text{ s}$ for formula graph analysis yields $\approx 2.3\text{ s}$, safely under the $3.0\text{ s}$ ceiling.

### 3.2 Basis for Memory Ceiling Compliance ($O(W \cdot C + K)$)
- **Streaming Window ($W=50$ rows):** Consumes $\approx 0.5\text{ MB}$ of active Python memory.
- **Retained Graph ($K_{\text{graph}}$):**
  - Configurable hard limits: `max_graph_nodes = 50,000`, `max_graph_edges = 100,000`.
  - At $\approx 200\text{ bytes}$ per edge, $100,000$ edges consume $\approx 20\text{ MB}$.
  - Combined with baseline RSS ($\approx 19.0\text{ MB}$) and M04 spatial report retention ($\approx 38.8\text{ MB}$ in extreme sparse cases), total process RSS is bounded to $\approx 80\text{ MB}$, well below the $235.0\text{ MiB}$ defensive tripwire and $250.0\text{ MiB}$ hard ceiling.

---

## 4. Traceability Matrix & Sign-Off Checklist

| Requirement | Design Specification | Implementation Module | Primary Test Module |
| :--- | :--- | :--- | :--- |
| **FR-1: Semantic Type Inference & States** | Plan §2.1, §3.1 | `excel_intel/types/` | `tests/test_m05_types.py` |
| **FR-2: Formula Lexer & Grammar** | Plan §2.2, §3.2 | `excel_intel/formulas/lexer.py` | `tests/test_m05_formula_parser.py` |
| **FR-3: Formula AST Parser** | Plan §2.2, §3.2 | `excel_intel/formulas/parser.py` | `tests/test_m05_formula_parser.py` |
| **FR-4: Dependency Graph DAG** | Plan §2.3 | `excel_intel/formulas/graph.py` | `tests/test_m05_formula_graph.py` |
| **FR-5: Cycle & Volatile Sentinels** | Plan §2.3, §3.3 | `excel_intel/formulas/cycle_detector.py` | `tests/test_m05_formula_graph.py` |
| **FR-6: Manifest Integration** | Plan §4 | `excel_intel/analyzer.py` | `tests/test_m05_manifest_integration.py` |
| **NFR-1: Memory Bounds** | Plan §3 | Multi-tier resource caps | `tests/benchmarks/run_m05_benchmarks.py` |
| **NFR-2: Throughput Targets** | Strategy §3.1 | Streaming chunk architecture | Benchmark suite |
| **NFR-3: Source Immutability** | Strategy §1 | Read-only streaming reader | All M05 tests |
| **NFR-4: Zero Native Dependencies** | Plan §1 | Pure Python implementation | Build audit |

---

## 5. Unresolved Architectural Decisions Requiring Approval

1. **Provisional 0.80 Homogeneity Threshold:** Designated provisional; columns with $H < 0.80$ marked `state = InferenceState.AMBIGUOUS`, `requires_human_review = True`, and strictly excluded from automated mutations.
2. **Ambiguous / Unknown / Insufficient Type Representation in M01 Projection:** M01 has no `AMBIGUOUS`, `UNKNOWN`, or `INSUFFICIENT_DATA` enum values; projected to `ColumnType.STRING` carrier with true underlying `type_confidence = S` preserved, with downstream consumers checking M05 Tier 1 inference states.
3. **Range Node Hyper-Edge Threshold ($K_{\text{expand}} = 1,000$):** Ranges $> 1,000$ cells or whole columns (`A:A`) remain Range Nodes without individual cell edge expansion.

---

## 6. Milestone M05 Planning Sign-Off
Milestone M05 Test & Acceptance Strategy is finalized. All functional requirements, algorithmic formulations, performance budgets, and error sentinels are completely defined. Ready for Project Owner authorization.
