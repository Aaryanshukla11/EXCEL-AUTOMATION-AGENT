# M05 PROMPT 3 EVIDENCE REPORT: FORMULA LEXER, PARSER & STRONGLY-TYPED AST

**Milestone:** M05 — Semantic Type & Formula Dependency Analysis  
**Stage:** Prompt 3 — Formula Lexer, Parser & Strongly-Typed AST Subsystem  
**Date:** 2026-11-23  
**Status:** COMPLETE & PASSING ALL QUALITY GATES (Pure Syntactic Scope Enforced)  

---

## 1. Executive Summary & Authorization Context

Pursuant to the V2 architectural authority, Re-Audit findings (R-01, R-02, R-03), and Project Owner authorization, **M05 Prompt 3: Formula Lexer, Parser & Strongly-Typed AST** has been implemented.

The subsystem implements a deterministic, pure-Python lexical analyzer and operator-precedence recursive-descent parser that converts raw Excel formula strings into strongly-typed, immutable Pydantic v2 AST representations.

### Critical Scope Boundaries Enforced
- **Pure Syntactic Scope (R-01 Resolved):** Prompt 3 emits typed AST nodes and reference nodes only. Precedent extraction, dependency graph construction, range hyperedges, and Tarjan SCC cycle detection are strictly excluded from Prompt 3 and deferred to Prompt 4.
- **Three Discrete Root Statuses (R-02 Resolved):** The parser contract emits exclusively one of three root statuses (`PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, `PARSE_ERROR`). Category A/B/C classifications are subordinate syntax tags only.
- **Syntactic Parsing Decoupled from Security Policy (R-03 Resolved):** Syntactically valid functions that are not on execution allowlists (e.g. `CMD(...)`, `WEBSERVICE(...)`, custom UDFs) parse normally into `FunctionCallNode` with status `PARSED_COMPLETE`. Security allowlist enforcement is strictly an execution-layer policy in Tier 3 DEL.
- **Zero Formula Recalculation:** The subsystem performs static syntactic analysis only; no calculation, formula evaluation (`eval()`, `exec()`), network requests, or workbook mutations.
- **Resource Bounds Enforced:** Hard bounds on formula length ($\le 16,384$ chars), token count ($\le 4,096$), AST nesting depth ($\le 64$), and AST node count ($\le 4,096$).
- **Frozen Modules Unmodified:** Zero modifications to M01 (`excel_intel/core/`), M02 (`crates/excel_intel_rs/`), M03 (`excel_intel/inspection/`), M04 (`excel_intel/spatial/`), or M05 Prompt 2 (`excel_intel/types/`).
- **Preservation of Pre-Existing State:** Uncommitted modifications in `excel_intel/inspection/inspector.py` and `excel_intel/inspection/topology_inspector.py` from the M03 remediation sprint remain untouched.
- **Zero Autonomous Commits/Pushes:** All code remains in the working directory without staging, committing, or pushing.

---

## 2. Deliverables Summary

### 2.1 Production Package: `excel_intel/formulas/`
The package `excel_intel/formulas/` provides four core modules implementing Prompt 3:

1. `excel_intel/formulas/models.py`
   - Immutable, frozen Pydantic v2 AST node contracts (`model_config = ConfigDict(frozen=True)`):
     - `FormulaParseStatus`: Root status enum (`PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, `PARSE_ERROR`).
     - `ASTNodeType`: AST node categorization enum.
     - `BaseASTNode`: Base model enforcing half-open character span provenance `span: tuple[int, int]`.
     - `LiteralNode`: Typed literals (`NUMBER`, `STRING`, `BOOLEAN`, `ERROR`) with verbatim text preservation.
     - `CellReferenceNode`: Coordinate validation ($1 \le \text{col} \le 16384, 1 \le \text{row} \le 1048576$), relative/absolute anchor flags, sheet and external workbook qualification, and `to_a1()` canonical serialization.
     - `RangeReferenceNode`: 2D rectangular bounds, 3D multi-sheet spans (`Sheet1:Sheet3`), full column ranges (`A:A`), full row ranges (`1:1`).
     - `StructuredReferenceNode`: Excel Table ListObject structured reference contracts (`table_name`, `column_name`, `column_end`, `specifiers`, `is_this_row`).
     - `FunctionCallNode`: Normalized uppercase function name and ordered child argument AST nodes.
     - `BinaryOpNode`, `UnaryOpNode`, `PostfixOpNode`: Infix, prefix, and postfix operator nodes.
     - `ArrayLiteralNode`: Strict rectangular 2D matrix validation with `@model_validator(mode="after")`.
     - `UnsupportedFormulaNode`: Bounded sentinel capturing raw unsupported text, syntax category, and diagnostics without fabricating AST semantics.
     - `UnparsedFormulaNode`: Malformed syntax error container capturing offset and diagnostic error message.
     - `FormulaParseResult`: Comprehensive container with `.is_success` property.

2. `excel_intel/formulas/lexer.py`
   - Deterministic tokenizer with half-open character span tracking relative to the original formula string.
   - Robust recognition of:
     - Double-quoted strings with `""` escape handling (`"Total: ""` & A1`).
     - Integers, decimals, and scientific notation (`1.5e-3`, `2.5E+4`).
     - Booleans (`TRUE`, `FALSE`) and standard Excel error literals (`#N/A`, `#DIV/0!`, `#REF!`, `#VALUE!`, `#NAME?`, `#NUM!`, `#NULL!`, etc.).
     - Unquoted and single-quoted cell references (`A1`, `$B$2`, `Sheet1!C3`, `'Sales Summary'!$D$4`).
     - External workbook references (`[Budget.xlsx]Sheet1!A1`, `'[Corporate Budget.xlsx]Q1'!A1`).
     - 3D multi-sheet references (`Sheet1:Sheet3!A1:B10`, `'Jan:Dec'!$A$1:$B$10`).
     - Full column references (`A:A`, `$A:$B`, `Sheet1!A:A`) and full row references (`1:1`, `1:10`).
     - Structured table references (`Table1[Sales]`, `Table1[[#Headers],[Sales]]`, `[@Quantity]`, `[@[Unit Price]]`).
     - Dynamic array spill operator `#` following cell or range coordinates (`A1#`).
     - Arithmetic, comparison, concatenation, range, and structural delimiter operators.
   - Resource safety bounds: `MAX_FORMULA_LENGTH = 16_384` chars, `MAX_TOKENS = 4_096` tokens.

3. `excel_intel/formulas/parser.py`
   - Pure-Python recursive-descent precedence parser:
     - Comparison operators (`=`, `<>`, `<`, `>`, `<=`, `>=`) at precedence level 1.
     - String concatenation (`&`) at precedence level 2.
     - Additive operators (`+`, `-`) at precedence level 3.
     - Multiplicative operators (`*`, `/`) at precedence level 4.
     - Exponentiation (`^`) at precedence level 5 with Excel standard left-associativity ($2^3^2 = (2^3)^2$).
     - Unary prefix operators (`+`, `-`) with support for arbitrary prefix chaining (`--5`).
     - Postfix operators (`%`).
     - Parenthesized sub-expressions with strict nesting depth limits.
   - Strict Array Constant Validation:
     - Rows delimited by `;`, elements delimited by `,`.
     - Rejects ragged matrices with `PARSE_ERROR`.
     - Rejects dynamic formulas or cell references inside `{}` with `PARSE_ERROR`.
   - Prevention of Partial Parsing Conflation:
     - Strictly validates that all tokens are consumed. Extra tokens following root expressions (`=SUM(1, 2) 42`) fail with `PARSE_ERROR`.
   - Detection of Recognized Unsupported Syntax:
     - Dynamic array spill hash (`A1#`) $\rightarrow$ `DYNAMIC_ARRAY_SPILL`.
     - Lambda helper functions (`LAMBDA`, `MAP`, `REDUCE`, `SCAN`, `MAKEARRAY`, `BYROW`, `BYCOL`) $\rightarrow$ `LAMBDA_HELPER`.
     - Third-party UDFs with dot namespaces (`Bloomberg.BDP`) $\rightarrow$ `THIRD_PARTY_UDF`.
     - Complex external URI chains (`'https://sharepoint.com/...[Book.xlsx]Sheet1'!A1`) $\rightarrow$ `EXTERNAL_URI_CHAIN`.
   - Resource safety tripwires: `MAX_NESTING_DEPTH = 64`, `MAX_AST_NODES = 4_096`.

4. `excel_intel/formulas/__init__.py`
   - Clean public exports strictly exposing Prompt 3 AST models, lexer, and parser contracts. Zero Prompt 4 exports.

---

## 3. Syntax Categorization & Verification

| Syntax Category | Construct Example | AST Representation | Result Status |
| :--- | :--- | :--- | :--- |
| **Supported Infix / Prefix** | `=A1 + 2 * B2 ^ 3` | `BinaryOpNode` tree | `PARSED_COMPLETE` |
| **Cell & Range Refs** | `='Sales Summary'!$A$1:B10` | `RangeReferenceNode` | `PARSED_COMPLETE` |
| **3D Sheet Ranges** | `=Sheet1:Sheet3!A1:B10` | `RangeReferenceNode(is_3d=True)` | `PARSED_COMPLETE` |
| **Full Col / Full Row** | `=A:B + 1:1` | `RangeReferenceNode(is_full_col=True)` | `PARSED_COMPLETE` |
| **Structured Table Refs** | `=Table1[[#Headers],[Sales]]` | `StructuredReferenceNode` | `PARSED_COMPLETE` |
| **Array Constants** | `={1, 2, 3; 4, 5, 6}` | `ArrayLiteralNode(is_rectangular=True)` | `PARSED_COMPLETE` |
| **Unauthorized Functions** | `=CMD("calc.exe")`, `=WEBSERVICE("...")` | `FunctionCallNode` | `PARSED_COMPLETE` |
| **Dynamic Array Spill** | `=A1#`, `=SUM(Sheet1!B2#)` | `UnsupportedFormulaNode` | `UNSUPPORTED_SYNTAX` |
| **Lambda Helpers** | `=LAMBDA(x, x+1)`, `=MAP(A1:A10, ...)` | `UnsupportedFormulaNode` | `UNSUPPORTED_SYNTAX` |
| **Third-Party UDFs** | `=Bloomberg.BDP("AAPL", "PX_LAST")` | `UnsupportedFormulaNode` | `UNSUPPORTED_SYNTAX` |
| **External URI Chains** | `='https://sharepoint.com/[Book.xlsx]S1'!A1`| `UnsupportedFormulaNode` | `UNSUPPORTED_SYNTAX` |
| **Malformed Syntax** | `=(`, `={1, 2; 3}`, `=+*&`, `=A1:` | `UnparsedFormulaNode` | `PARSE_ERROR` |

---

## 4. Test Suite Execution & Quality Gates

### 4.1 Prompt 3 Unit Test Suite (41 Tests)
The comprehensive unit test suite validates tokenization, parsing, AST immutability, precedence, unsupported syntax, malformed error reporting, resource limits, adversarial inputs, and deterministic repeatability:

- `tests/test_m05_formula_models.py` (5 tests): AST model immutability, `to_a1()` canonical formatting, rectangular matrix validation, out-of-bounds coordinate rejection.
- `tests/test_m05_formula_lexer.py` (8 tests): Tokenizer coverage across numbers, strings, cell references, structured refs, operators, error values, column letter conversion, and length limits.
- `tests/test_m05_formula_parser.py` (16 tests): Operator precedence, left-associativity, 2D/3D ranges, whole column/row ranges, functions, structured refs, array constants, unauthorized functions, nesting depth limit, formula length limit, deterministic repeatability, and adversarial malformed inputs.
- `tests/test_m05_formula_unsupported.py` (6 tests): Dynamic array spill (`A1#`), lambda helpers (`LAMBDA`, `MAP`, etc.), third-party UDFs (`Bloomberg.BDP`), standard dot function whitelist, complex external URI chains.
- `tests/test_m05_formula_edge_cases.py` (6 tests): Unary chaining (`--5`), parenthesis override, case insensitivity, scientific notation, coordinate boundary extremes (`XFD1048576`), Excel error literals in expressions.

### 4.2 Multi-Environment Results

| Test Suite | Python 3.12 Result | Python 3.13 Result | Rust Suite Result | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Prompt 3 Core Tests (41 tests)** | **41 / 41 PASS (0.70s)** | **41 / 41 PASS (0.79s)** | N/A | **PASS** |
| **M05 Prompt 2 Typing (50 tests)** | **50 / 50 PASS (1.12s)** | **50 / 50 PASS (1.05s)** | N/A | **PASS** |
| **M04 Spatial Segmentation (71 tests)** | **71 / 71 PASS (2.23s)** | **71 / 71 PASS (2.15s)** | N/A | **PASS** |
| **M03 Inspection Engine (62 tests)** | **62 / 62 PASS (3.09s)** | **62 / 62 PASS (2.95s)** | N/A | **PASS** |
| **M02 Rust Core (`excel_intel_rs`)** | N/A | N/A | **60 / 60 PASS (0.77s)** | **PASS** |

Total Automated Tests Passed: **284 / 284 across Python 3.12, Python 3.13, and Rust environments with 0 failures.**

---

## 5. Security & Resource Tripwire Verification

1. **No Code Execution (`eval()`, `exec()`):** Static inspection verifies zero dynamic evaluation calls. All AST generation uses declarative Pydantic v2 schemas.
2. **Deterministic Allowlist Decoupling:** Formulas with unapproved or dangerous function names (e.g. `CMD`, `WEBSERVICE`) parse without error into `FunctionCallNode` with `PARSED_COMPLETE`. Execution-layer security allowlisting belongs strictly to Tier 3 DEL.
3. **Resource Limit Enforcement:**
   - Input length $> 16,384$ characters raises `LexerError` and returns `PARSE_ERROR`.
   - Token count $> 4,096$ tokens raises `LexerError` and returns `PARSE_ERROR`.
   - Expression nesting depth $> 64$ levels raises `ParseException` and returns `PARSE_ERROR`.
   - AST node count $> 4,096$ nodes raises `ParseException` and returns `PARSE_ERROR`.
4. **Adversarial Input Handling:** Incomplete strings, stray operators, unbalanced delimiters, and ragged array constants are handled gracefully without uncaught exceptions.

---

## 6. Git Status & Change-Control Verification

```text
Tracked files modified (Pre-existing M03 remediation diff preserved):
 M M03_PROMPT_3_EVIDENCE_REPORT.md
 M docs/milestones/m03/M03_PROMPT_3_EVIDENCE_REPORT.md
 M excel_intel/inspection/inspector.py
 M excel_intel/inspection/topology_inspector.py

Untracked Prompt 3 production & test files:
 ?? excel_intel/formulas/
 ?? tests/test_m05_formula_edge_cases.py
 ?? tests/test_m05_formula_lexer.py
 ?? tests/test_m05_formula_models.py
 ?? tests/test_m05_formula_parser.py
 ?? tests/test_m05_formula_unsupported.py
 ?? M05_PROMPT_3_EVIDENCE_REPORT.md
 ?? docs/milestones/m05/M05_PROMPT_3_EVIDENCE_REPORT.md
```

- **M01–M04 Production Code:** Completely untouched.
- **M05 Prompt 2 Type Inference:** Completely untouched.
- **M03 Uncommitted Modifications:** Preserved intact in working tree.
- **M05 Prompt 4 Boundary:** Graph construction, cycle detection, and manifest integration have not been commenced.
- **Git State:** Clean; zero staging, zero commits, zero stashes, zero resets.

---

## 7. Quality Gate Verdict

**VERDICT: ACCEPTED & PASSED**

M05 Prompt 3 is fully implemented, verified across Python 3.12, Python 3.13, and Rust test suites, and adheres strictly to the approved syntactic scope. Prompt 4 remains unstarted pending Project Owner review.
