# Milestone M05 — Prompt 2 Evidence Report: Semantic Type Inference Engine (Final Acceptance & Correctness Audit)

**Date:** 2026-11-22  
**Milestone:** M05 — Semantic Type & Formula Analysis  
**Stage:** Prompt 2 of 4 (Semantic Type Inference Engine Implementation & Correctness Correction)  
**Status:** COMPLETE, AUDITED & CERTIFIED  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes Maintained)

---

## 1. Executive Summary & Verification Outcomes

Milestone M05 Prompt 2 delivers the production-ready **Semantic Type Inference Engine** (`excel_intel.types`) for the Autonomous Excel Intelligence Platform. Following the final correctness correction, the engine enforces strict single-observation semantics for merged cells (both vertical and horizontal), non-inflating coordinate tracking without phantom null penalization, mathematically proven $O(1)$ sampling bounding cells to $\le 10,000$, and non-authoritative fallback carrier projections to canonical M01 data contracts.

### Verification Summary
- **Python 3.12 Test Suite:** 288 passed, 0 failed (100% pass rate in 14.8s).
- **Python 3.13 Test Suite:** 288 passed, 0 failed (100% pass rate in 14.5s).
- **Rust Test Suite (`_rs`):** 60 passed, 0 failed (100% pass rate in 0.53s).
- **M05 Focused Test Suite:** 50 passed, 0 failed across 5 dedicated test modules.
- **Frozen Code Integrity:** Zero lines modified in M01 (`excel_intel/core/`) or M02 (`crates/excel_intel_rs/`). Zero lines modified in M04 (`excel_intel/spatial/`).
- **Git Hygiene:** Zero autonomous commits, zero autonomous pushes. All changes remain unstaged.

---

## 2. Correctness Audit & Implementation Semantics

### 2.1 Vertical & Horizontal Merged Cell Observation Semantics
- **Single Semantic Observation Rule:**
  A merged cell is exactly one semantic observation.
  - Vertical continuation coordinates (`anchor_c == col_idx`, $r > anchor\_r$) are covered by the vertical merge. They are **never counted as duplicate observations** in column type statistics.
  - The anchor value is evaluated **exactly once** in the anchor column, preserving anchor coordinate provenance.
  - If sampling boundaries omit the top anchor row, the anchor value is resolved **once** upon the first sampled continuation row in that column; subsequent sampled continuation rows are recognized as continuation coordinates and not duplicated.
- **Horizontal Merge Column Isolation:**
  When a merged cell spans multiple columns horizontally (e.g. `A2:C2`), the anchor value at `(2, 1)` belongs exclusively to Column A. Coordinates in Columns B and C (`anchor_c != col_idx`) are recognized as horizontal non-anchors and are **never evaluated in Columns B or C**, preventing artificial distribution inflation across columns.
- **No Phantom Null Penalization:**
  Non-anchor coordinates covered by merges (both horizontal and vertical continuations) are tracked via `merged_non_anchor_cells`.
  - The effective column total is: $N_{\text{effective}} = \max(0, N_{\text{total}} - N_{\text{merged\_non\_anchor}})$.
  - Null cells are: $N_{\text{null}} = \max(0, N_{\text{effective}} - N_{\text{pop}})$.
  - Non-anchor coordinates are **never counted as independent null values**, preserving true nullability ratios and preventing artificial penalization.

### 2.2 Null and Text Classification
- **Definite Blank/Empty Cells:** Python `None`, empty strings `""`, and whitespace strings (`"   "`, `"\t\n"`) are categorized as `ValueCategory.NULL` with `is_null_marker = False` and `normalized_value = None`.
- **Excel Error Literals:** Standard OpenXML errors (`#N/A`, `#VALUE!`, `#REF!`, `#DIV/0!`, `#NUM!`, `#NAME?`, `#NULL!`) are strictly classified as `ValueCategory.ERROR` with `error_code` recorded, distinct from textual tokens.
- **Recognized Textual Null Markers:** Strings like `"-"`, `"N/A"`, `"NA"`, `"null"`, `"none"`, `"nil"` are explicitly recognized via `is_null_marker = True` and `null_marker_text`.
  - When `treat_null_markers_as_null=True` (default in statistical profiling): classified as `ValueCategory.NULL` with marker provenance preserved.
  - When `treat_null_markers_as_null=False`: classified as `ValueCategory.STRING` with `is_null_marker=True`, preserving legitimate text tokens.
- **Ambiguity & Human Review Guarantee:**
  - A column containing *exclusively* textual null markers (e.g. all `"-"` or all `"N/A"`) without definite values is strictly assigned `InferenceState.AMBIGUOUS` (`candidate_type = None`, `heuristic_support_score = 0.50`, `requires_human_review = True`), preventing silent conflation with 100% empty `UNKNOWN` columns or authoritative `STRING` types.
  - A column mixing numbers and occasional `"-"` treats the dash as a missing value, preventing type corruption.

### 2.3 Sampling Evidence & Separate Reporting
- **Sampled Coordinates vs. Semantic Observations:**
  - `SamplingDiagnostics.sampled_cells`: Bounded 2D grid coordinates evaluated ($\le 10,000$).
  - `SamplingDiagnostics.semantic_observation_count`: Count of actual non-null semantic observations (excluding blanks and non-anchor merged coordinates).
  - Because non-anchor merged coordinates and blanks are excluded, $\text{semantic observations} \le \text{sampled cells} \le 10,000$ strictly.
- **Mathematical Bound Proof ($B_{\text{cells}} \le 10,000$):**
  For any region spanning $R$ rows and $C$ columns in `SemanticZoneType.BODY`:
  1. $C > 10,000 \implies C_{\text{sample}} = 10,000, R_{\text{sample}} = 1 \implies 10,000 \times 1 = 10,000 \le 10,000$.
  2. $100 < C \le 10,000 \implies C_{\text{sample}} = \min(C, 1000) \implies R_{\text{sample}} = \min(R, \lfloor 10,000 / C_{\text{sample}} \rfloor) \implies C_{\text{sample}} \times R_{\text{sample}} \le 10,000$.
  3. $C \le 100 \implies C_{\text{sample}} = C \implies R_{\text{sample}} = \min(R, \lfloor 10,000 / C \rfloor) \implies C_{\text{sample}} \times R_{\text{sample}} \le 10,000$.
  - Combinatorially verified across $12 \times 12 = 144$ dimension pairs up to Excel max limits ($1,048,576 \times 16,384$): 0 violations.
- **Deterministic 3-Band Coverage:**
  - Column coverage: First column (`min_col`), last column (`max_col`), and middle columns are guaranteed.
  - Row coverage: First row (`min_row`), last row (`max_row`), and middle rows are guaranteed.
  - Repeated invocations yield 100% identical coordinate sequences.
- **Zero Full-Matrix Materialization:**
  - Verified on Excel maximum dimensions ($1,048,576 \times 16,384$); sampling completes in $< 2.0\text{ ms}$ with zero full-matrix allocation ($O(1)$ memory).

### 2.4 State Precedence & Score Invariants
- Strict 5-tier state precedence verified:
  1. $N_{\text{pop}} == 0 \implies \text{UNKNOWN}, \text{candidate} = \text{None}, S = 0.0, \text{carrier} = \text{STRING}, \text{review} = \text{True}$.
  2. $1 \le N_{\text{pop}} < 5 \implies \text{INSUFFICIENT\_DATA}, \text{candidate} = T_{\text{pred}}, S = S, \text{carrier} = \text{STRING}, \text{review} = \text{True}$.
  3. Unresolved semantic ambiguity (date order ambiguity, boolean/integer 0/1, or exclusively null markers) $\implies \text{AMBIGUOUS}, \text{candidate} = \text{None}, S = S, \text{carrier} = \text{STRING}, \text{review} = \text{True}$.
  4. Low homogeneity ($H < 0.80$) $\implies \text{AMBIGUOUS}, \text{candidate} = \text{None}, S = S < 0.80, \text{carrier} = \text{STRING}, \text{review} = \text{True}$.
  5. Confident inference ($H \ge 0.80, S \ge 0.70$) $\implies \text{INFERRED}, \text{candidate} = T_{\text{pred}}, S = S, \text{carrier} = T_{\text{pred}}, \text{review} = \text{False}$.
- **High Heuristic Score Invariant:** A score of $S = 1.0$ (e.g. 10 identical `"01/02/03"` strings) cannot override semantic ambiguity; state remains `AMBIGUOUS` with `candidate_type = None`.
- **Non-Authoritative Fallback Guarantee:** Fallback M01 `ColumnType.STRING` values strictly retain `candidate_type = None` and `requires_human_review = True`. Downstream consumers cannot mistake carrier `STRING` for verified types.
- **Formatting Provenance Preserved:** Original currency symbols (`$`, `€`, `£`, `¥`), accounting parentheses (`($150)`), percentage factors (`0.1275`), and format codes are preserved in `NormalizedValue`.

---

## 3. Frozen Milestone Integrity & Provenance

### 3.1 Frozen Module Status
- `git diff HEAD excel_intel/core/`: **0 lines** (M01 100% frozen).
- `git diff HEAD crates/excel_intel_rs/`: **0 lines** (M02 100% frozen).
- `git diff HEAD excel_intel/spatial/`: **0 lines modified** (M04 100% frozen).

### 3.2 M03 Uncommitted Baseline & Provenance Statement
- The working tree currently contains pre-existing uncommitted differences in `excel_intel/inspection/inspector.py` and `excel_intel/inspection/topology_inspector.py`.
- According to the available execution logs and turn history of this session, no changes to M03 production files were intentionally made during M05 Prompt 2.
- A `git diff` against HEAD demonstrates the current differences in the working tree, but it cannot independently prove the historical date or calendar origin on which those uncommitted changes were created.
- This condition is recorded as an acknowledged limitation of the working-tree baseline.
- Zero autonomous git commits or pushes have been made.

---

## 4. Test Execution Evidence

### 4.1 M05 Focused Acceptance Suite
```
py -3.12 -m pytest tests/test_m05_type_models.py tests/test_m05_pattern_detector.py tests/test_m05_sampling.py tests/test_m05_type_inferrer.py tests/test_m05_type_integration.py -v
```
**Outcome:** 50 passed in 1.05s (Exit code: 0).
- `test_m05_type_models.py`: 6 passed.
- `test_m05_pattern_detector.py`: 15 passed.
- `test_m05_sampling.py`: 11 passed.
- `test_m05_type_inferrer.py`: 16 passed.
- `test_m05_type_integration.py`: 2 passed.

### 4.2 Full Python 3.12 Regression Suite
```
py -3.12 -m pytest tests/ -q
```
**Outcome:** 288 passed in 14.8s (Exit code: 0).

### 4.3 Full Python 3.13 Regression Suite
```
py -3.13 -m pytest tests/ -q
```
**Outcome:** 288 passed in 14.5s (Exit code: 0).

### 4.4 Compiled Native Extension Tests (Rust)
```
cargo test --manifest-path crates/excel_intel_rs/Cargo.toml
```
**Outcome:** 60 passed, 0 failed in 0.53s (Exit code: 0).

---

## 5. Closure & Handoff

The final correctness correction of Milestone M05 Prompt 2 is complete. All merged cell observation semantics, sampling evidence metrics, and M03 historical provenance statements have been verified and certified.

**Handoff to Prompt 3:**
Prompt 3 (Formula Lexer, Parser & Strongly-Typed AST) will begin upon Project Owner acceptance.
