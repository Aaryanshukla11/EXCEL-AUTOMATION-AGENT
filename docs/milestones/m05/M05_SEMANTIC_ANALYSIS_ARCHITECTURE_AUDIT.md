# Milestone M05 — Semantic Type & Formula Analysis
## Document 1 of 4: Architecture Inspection & Repository Audit

**Date:** 2026-11-22  
**Milestone:** M05 — Semantic Type & Formula Analysis  
**Stage:** Prompt 1 of 4 (Architecture Inspection, Requirements Discovery & Planning)  
**Status:** COMPLETE (Planning & Audit Only — Zero Code Modification)  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes)

---

## 1. Executive Summary & Context

Milestone M05 (Semantic Type & Formula Analysis) establishes the analytical and reasoning intelligence layer of the Autonomous Excel Intelligence Platform. It bridges 2D spatial table detection (M04) and cognitive consolidation planning / operation synthesis (M06).

Following the formal closure and acceptance of Milestones M01, M02, M03, and M04, this audit inspects the entire repository to determine how semantic data type inference, formula syntax parsing, formula AST modeling, and calculation dependency graph construction must be structured.

### Primary Audit Findings:
1. **Existing Baseline (M01–M04):**
   - **M01 (`excel_intel.core.types`):** Defines canonical contracts (`ColumnType`, `ColumnMetadata`, `TableMetadata`, `FormulaGraphMetadata`, `DiscoveryManifest`). These contracts are frozen and cannot be modified.
   - **M02 (`excel_intel.core.parser` & `excel_intel_rs`):** High-performance streaming OpenXML reader (`StreamingWorkbookReader`) streaming row chunks with raw `<f>` formula strings, date serial converters (`parse_excel_serial`), and 235/250 MB memory guard enforcement.
   - **M03 (`excel_intel.inspection`):** Workbook structural facts (`DeclaredOpenXmlFacts`), package properties (`<calcPr>`), defined names, and bounded-memory coarse sheet profiling (`ContentDistributionProfiler`).
   - **M04 (`excel_intel.spatial`):** 2D grid segmentation, hierarchical header resolution, intra-region semantic zone decomposition (specifically `SemanticZoneType.BODY` bounding boxes), and ADR-005 append collision sentinels.
2. **The Semantic & Formula Gap:**
   - **Semantic Type Gap:** M03 provided only crude cell-level categorizations across whole sheets (`integer`, `float`, `string`, `date`, `boolean`, `error`). It did not profile cells exclusively within the `BODY` zone of spatial tables, did not detect semantic string patterns (currency, percentages, dates formatted as strings, numeric strings), and did not compute heuristic support scores or nullability ratios. Consequently, M04's `export_to_table_metadata_list()` currently raises `NotImplementedError` awaiting verified types from M05.
   - **Formula Parsing & AST Gap:** There is currently zero formula parsing capability in the platform. Raw formula text strings from OpenXML `<f>` tags are unparsed. The platform cannot distinguish operators, cell references, ranges, 3D cross-sheet references, structured table references, built-in functions, or literals.
   - **Dependency Graph Gap:** There is no formula dependency graph or calculation DAG. The platform cannot identify calculation precedents (inputs) or dependents (downstream cells), cannot detect circular references (directed cycles), and cannot catalog volatile functions (`NOW`, `TODAY`, `OFFSET`, `INDIRECT`).
3. **Architectural Placement:**
   - M05 components must be housed cleanly in `excel_intel.types` and `excel_intel.formulas`, coordinated by an analysis facade that consumes M04's `SpatialAnalysisReport` and M02's `StreamingWorkbookReader`, and yields fully populated M01 `TableMetadata` and `FormulaGraphMetadata` to construct the canonical `DiscoveryManifest`.

---

## 2. Comprehensive Repository Inspection & Frozen Baseline Audit

### 2.1 Milestone M01 Baseline (`excel_intel.core.types`)
- **Canonical Column Types (`ColumnType` Enum):**
  - `INTEGER`: Whole numeric values.
  - `DECIMAL`: Floating-point and fixed-precision numeric values.
  - `STRING`: Textual characters and unparsed string data.
  - `DATE`: Discrete calendar dates, timestamps, and temporal values.
  - `BOOLEAN`: Logical truth values (`TRUE`, `FALSE`).
  - `FORMULA`: Computed columns where cells are primarily driven by calculation formulas.
  - *Contract Limitation:* M01 contains NO `UNKNOWN`, `AMBIGUOUS`, or `INSUFFICIENT_DATA` enum member.
- **Canonical Column Metadata (`ColumnMetadata`):**
  - `index`: 1-indexed column number.
  - `header_name`: Resolved header string.
  - `inferred_type`: Canonical `ColumnType`.
  - `type_confidence`: Mathematical confidence / heuristic support score in $[0.0, 1.0]$.
  - `nullable`: Boolean flag indicating presence of null/empty cells.
  - `formula_pattern`: Optional canonical formula pattern (e.g. `SUM(C{row}:D{row})`).
- **Canonical Table Metadata (`TableMetadata`):**
  - Represents a verified tabular entity (`sheet_name`, `bounding_box`, `header_row`, `columns: list[ColumnMetadata]`, `is_list_object`, `list_object_name`).
- **Formula Graph Contract (`FormulaGraphMetadata`):**
  - `node_count`: Count of active calculation nodes.
  - `edge_count`: Count of directed dependency edges.
  - `has_cycles`: Boolean flag indicating existence of circular dependencies.
  - `volatile_cells`: List of cell coordinates invoking volatile functions.
- **Root Discovery Manifest (`DiscoveryManifest`):**
  - Master manifest consumed by Phase 1 cognitive orchestration (`manifest_id`, `workbook_path`, `sha256`, `file_size_bytes`, `tables: list[TableMetadata]`, `formula_graph: FormulaGraphMetadata`).

### 2.2 Milestone M02 Baseline (`excel_intel.core.parser` & `excel_intel_rs`)
- **Streaming Ingestion Interface:** `StreamingWorkbookReader.stream_sheet(sheet, chunk_size=1000)` yields batches of row records.
- **Raw Cell Token Structure:**
  ```python
  {
      "row": int,
      "cells": [
          {
              "col": int,
              "value": Any,             # Parsed numeric, bool, or shared string text
              "formula": Optional[str], # Raw OpenXML formula string from <f> tag
              "cell_type": str,         # Raw OpenXML t attribute ("s", "n", "b", "e", "str", "d")
              "style_id": int           # 0-indexed xf style index
          }
      ]
  }
  ```
- **Date Serial Conversion:** `parse_excel_serial(serial: float, is_1904: bool = False)` provides exact Lotus 1-2-3 compliant serial date conversion.
- **Defensive Resource Controls:** Process working set monitored via `get_process_working_set_bytes()`; tripwire at 235 MiB; hard ceiling at 250 MiB.
- **Integrity Status:** `git diff HEAD excel_intel/core/ crates/excel_intel_rs/` yields **0 diff lines**.

### 2.3 Milestone M03 Baseline (`excel_intel/inspection/`)
- **Declared Structural Facts (`DeclaredOpenXmlFacts`):**
  - `list_objects`: Declared Excel tables with column names and display names.
  - `merge_cells`: Declared merged cell coordinate bounds (`DeclaredMergeCell`).
  - `defined_names`: Global and sheet-scoped named ranges and formula constants.
  - `calc_pr`: OpenXML calculation engine properties (`fullCalcOnLoad`, `calcCompleted`, `iterate`).
  - `sheet_visibility`: Sheet visibility states (`visible`, `hidden`, `veryHidden`).
  - `hidden_rows`: List of `HiddenInterval(dimension="row", start=..., end=...)`.
  - `hidden_cols`: List of `HiddenInterval(dimension="col", start=..., end=...)`.
- **Coarse Content Profiling (`ContentDistributionProfiler`):**
  - Computes `ColumnProfile` with coarse counts (`integer`, `float`, `string`, `date`, `boolean`, `error`), predominant type, and homogeneity ratio across entire worksheets.
- **Baseline Git Status & Provenance Boundary:**
  - `git status --porcelain excel_intel/inspection/` displays modified status for `inspector.py` and `topology_inspector.py`.
  - **Audit & Limitation:** These uncommitted diffs predate M04 and M05, having originated on November 21, 2026 during the M03 memory remediation sprint. Because the repository baseline preserves these unstaged changes under the project's zero autonomous commit rule, Git diff against HEAD shows modifications in M03. However, repository session logs and commit history confirm that **zero lines of M03 production code were modified during M04 or M05 planning**. We explicitly report this baseline limitation rather than claiming historical proof from filesystem timestamps alone.

### 2.4 Milestone M04 Baseline (`excel_intel/spatial/`)
- **2D Spatial Table Regions (`SpatialTableRegion`):**
  - Strongly-typed rectangular boundaries (`bounding_box: BoundingBox`).
  - Intra-region semantic zones (`zones: list[SemanticZone]`). The canonical data body zone is represented by `SemanticZoneType.BODY` with field `bounding_box: BoundingBox` (`min_row`, `max_row`, `min_col`, `max_col`).
  - Header resolution report (`header_resolution: HeaderResolutionReport`) containing resolved column headers (`ResolvedHeaderColumn`).
- **Canonical Conversion Bridge (`SpatialDetector.export_to_table_metadata_list`):**
  - Requires caller to provide verified column types: `inferred_types_by_region: dict[str, dict[int, Any]]`.
  - Strictly raises `NotImplementedError` if called without verified column types, enforcing the architectural invariant that M04 refuses to fabricate unverified types.
- **Integrity Status:** `git diff HEAD excel_intel/spatial/` yields **0 diff lines**.

---

## 3. Explicit Formula Grammar & Parsing Boundaries

The platform strictly avoids claiming complete Excel compatibility. Excel's formula engine contains thousands of functions, complex legacy quirks, dynamic array intersection semantics, locale-specific delimiters, and third-party VBA/XLL add-in syntaxes.

Instead, M05 defines an **explicit, deterministic formula grammar** partitioned into three exhaustive categories:

### 3.1 Syntax Categorization Matrix

| Category | Syntax Elements | Architectural Behavior |
| :--- | :--- | :--- |
| **Category A: Supported & Parsed** | - **Operators:** Infix arithmetic (`+`, `-`, `*`, `/`, `^`), concatenation (`&`), comparison (`=`, `<`, `>`, `<=`, `>=`, `<>`), prefix unary (`+`, `-`), postfix percent (`%`), range (`:`), union (`,`), intersection (` `).<br>- **References:** Single A1 relative (`A1`) and absolute (`$A$1`, `$A1`, `A$1`); 2D rectangular ranges (`A1:B10`); 3D sheet-qualified references (`Sheet1!A1`, `'Sales Summary'!A1:B10`); 3D multi-sheet cube ranges (`Sheet1:Sheet3!A1:B5`); external workbook references (`[Budget.xlsx]Sheet1!A1`); structured table references (`Table1[Col]`, `Table1[[#Headers],[Col]]`, `Table1[@Col]`, `Table1[#All]`).<br>- **Functions:** Standard built-in function calls with 0, 1, or variable arguments (e.g. `SUM`, `AVERAGE`, `IF`, `VLOOKUP`, `INDEX`, `MATCH`, `XLOOKUP`, `SUBTOTAL`, `CONCATENATE`, `NOW`, `TODAY`, `OFFSET`, `INDIRECT`, etc.).<br>- **Literals:** Numeric (`100`, `3.14159`, `1.2E-3`), string (`"Text"`, `""`), boolean (`TRUE`, `FALSE`), standard errors (`#N/A`, `#VALUE!`, `#REF!`, `#DIV/0!`, `#NUM!`, `#NAME?`, `#NULL!`).<br>- **Arrays & Grouping:** Array constants (`{1, 2; 3, 4}`), parenthetical expressions `(...)`. | Parsed into strongly-typed AST nodes (`CellReferenceNode`, `RangeReferenceNode`, `FunctionCallNode`, `BinaryOpNode`, etc.). Full precedent coordinate extraction enabled. Status = `PARSED_COMPLETE`. |
| **Category B: Recognized but Unsupported** | - **Legacy Lotus 1-2-3 shortcuts:** Unquoted implicit intersections without `@`.<br>- **Dynamic Array Spill Operator:** Trailing spill hash (`A1#`).<br>- **Opaque Third-Party Add-In UDFs:** External COM/XLL add-in calls (e.g. `=Bloomberg.BDP(...)`, `=CapIQ(...)`).<br>- **Complex Multi-Workbook Bracket Chains:** Deeply nested multi-file external links with unresolvable network URIs.<br>- **Lambda & Helper Functions:** Complex modern lambdas (`LAMBDA`, `MAP`, `REDUCE`, `SCAN`, `MAKEARRAY`). | Tokenized and bounded via character span tracking. Preserved as `UnsupportedFormulaNode` containing exact raw formula text, span `(start_col, end_col)`, and unsupported syntax classification. The dependency graph records dependency as `UNKNOWN_DEPENDENCY` and sets `is_complete = False`. Never fabricates placeholder AST semantics. Status = `UNSUPPORTED_SYNTAX`. |
| **Category C: Malformed or Invalid** | - **Unmatched Parentheses:** e.g. `=SUM(A1:B10 + 2`.<br>- **Trailing / Dangling Operators:** e.g. `=A1 + * B1`.<br>- **Unclosed String Literals:** e.g. `="Unclosed text`.<br>- **Corrupt XML Expressions:** e.g. empty `<f></f>` tags or truncated tokens. | Lexer/parser halts expression parsing at error offset without throwing unhandled exceptions. Wraps expression in `UnparsedFormulaNode` capturing raw text, error message, and exact character position. Emits `FORMULA_PARSE_ERROR` anomaly. Status = `PARSE_ERROR`. |

### 3.2 Formal Grammar Production Rules (EBNF) for Supported Syntax (Category A)
```ebnf
Expression          ::= ComparisonExpr
ComparisonExpr      ::= ConcatExpr ( ( "=" | "<" | ">" | "<=" | ">=" | "<>" ) ConcatExpr )*
ConcatExpr          ::= AdditiveExpr ( "&" AdditiveExpr )*
AdditiveExpr        ::= MultiplicativeExpr ( ( "+" | "-" ) MultiplicativeExpr )*
MultiplicativeExpr  ::= PowerExpr ( ( "*" | "/" ) PowerExpr )*
PowerExpr           ::= PercentExpr ( "^" PercentExpr )*
PercentExpr         ::= UnaryExpr ( "%" )*
UnaryExpr           ::= ( "+" | "-" )* PrimaryExpr
PrimaryExpr         ::= Literal 
                      | Reference 
                      | FunctionCall 
                      | ArrayConstant 
                      | "(" Expression ")"

Literal             ::= NumberLiteral | StringLiteral | BooleanLiteral | ErrorLiteral
NumberLiteral       ::= [0-9]+ ( "." [0-9]+ )? ( [eE] [+-]? [0-9]+ )?
StringLiteral       ::= '"' ( [^"] | '""' )* '"'
BooleanLiteral      ::= "TRUE" | "FALSE"
ErrorLiteral        ::= "#N/A" | "#VALUE!" | "#REF!" | "#DIV/0!" | "#NUM!" | "#NAME?" | "#NULL!"

Reference           ::= SingleCellRef | RangeRef | StructuredRef | ExternalRef
SingleCellRef       ::= ( SheetPrefix )? "$"? [A-Za-z]+ "$"? [0-9]+
RangeRef            ::= SingleCellRef ":" SingleCellRef
                      | ( SheetPrefix )? "$"? [A-Za-z]+ ":" "$"? [A-Za-z]+
                      | ( SheetPrefix )? "$"? [0-9]+ ":" "$"? [0-9]+
SheetPrefix         ::= ( SheetName | "'" SheetName "'" ) "!"
                      | ( SheetName ":" SheetName | "'" SheetName ":" SheetName "'" ) "!"
SheetName           ::= [^!:'\[\]]+

StructuredRef       ::= ( TableName )? "[" ( StructuredSpecifier "," )? ColumnSpecifier "]"
TableName           ::= [A-Za-z_][A-Za-z0-9_]*
StructuredSpecifier ::= "#All" | "#Data" | "#Headers" | "#Totals"
ColumnSpecifier     ::= "@"? "[" [^\]]+ "]" | "@"? [A-Za-z0-9_]+

ExternalRef         ::= "[" WorkbookName "]" ( SheetPrefix )? ( SingleCellRef | RangeRef )
WorkbookName        ::= [^\]]+

FunctionCall        ::= FunctionName "(" ( ArgumentList )? ")"
FunctionName        ::= [A-Za-z_][A-Za-z0-9_.]*
ArgumentList        ::= Expression ( "," Expression )*

ArrayConstant       ::= "{" ArrayRow ( ";" ArrayRow )* "}"
ArrayRow            ::= Literal ( "," Literal )*
```

### 3.3 Representative Valid and Invalid Constructs
- **Structured References:**
  - *Valid:* `Table1[Sales]`, `Table1[[#Headers],[Sales]]`, `Table1[[#Totals],[Sales]]`, `Table1[@Sales]`, `Table1[#All]`, `[@[Column Name]]`.
  - *Invalid / Unsupported:* Unbracketed column names (`Table1.Sales`), complex multi-table cross-joins without brackets.
- **3D References:**
  - *Valid:* `Sheet1!A1`, `'Sales Summary'!A1:B10`, `Sheet1:Sheet3!A1`, `'Jan:Dec'!$A$1:$B$10`.
  - *Invalid / Unsupported:* 3D references containing sheet wildcards (`Sheet*!A1`), disconnected external multi-files.
- **External Workbook References:**
  - *Valid:* `[Budget.xlsx]Sheet1!A1`, `'[Corporate Budget 2024.xlsx]Q1 Summary'!$B$10`.
  - *Invalid / Unsupported:* Dynamic indirect external links (`INDIRECT("[" & A1 & "]Sheet1!A1")`), DDE/OLE links (`=Excel|Sheet1!'A1'`).
- **Array Constants:**
  - *Valid:* `{1, 2, 3; 4, 5, 6}`, `{"a", "b"; "c", "d"}` (strictly rectangular matrices of literal constants).
  - *Invalid / Unsupported:* Ragged arrays (`{1, 2; 3}`), arrays containing cell references or formulas (`{A1, B1}`).
- **Prevention of Partial Parsing Conflation:**
  - The parser emits a root `FormulaParseResult` wrapping the AST.
  - `FormulaParseResult.status` is strictly an enum: `PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, or `PARSE_ERROR`.
  - If any sub-expression contains an `UnsupportedFormulaNode` or `UnparsedFormulaNode`, top-level status is downgraded.
  - Dependency extraction checks `status == PARSED_COMPLETE` before certifying precedent completeness; otherwise, dependencies are flagged as tentative/incomplete.

---

## 4. Separation of InferenceState from Support Score & Precedence

### 4.1 Separation Principle: Discrete State vs. Numeric Support
- `InferenceState` is a discrete categorical architectural classification: `INFERRED`, `UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`.
- `heuristic_support_score` ($S \in [0.0, 1.0]$) is a continuous measure of data consistency and pattern density.
- **AMBIGUOUS Columns Do Not Imply $S < 0.80$:** A column can have high homogeneity ($H = 1.0$) and high support ($S = 1.0$) but still be fundamentally `InferenceState.AMBIGUOUS`:
  - *Example 1 (Date Ambiguity):* 100 rows containing `"01/02/03"`. Homogeneity is $1.0$, but date format is unresolvable between MM/DD/YY (US), DD/MM/YY (UK), and YY/MM/DD (ISO).
  - *Example 2 (Boolean vs Integer):* 100 rows containing exclusively `0` and `1`. Homogeneity is $1.0$, but semantic classification is ambiguous between `BOOLEAN` and `INTEGER`.
  - *Example 3 (Competing Detectors):* Both Currency and Decimal detectors match 100% of rows with equal score.

### 4.2 State Precedence Hierarchy
When evaluating a column, the following strict precedence order determines `InferenceState`:
1. **Precedence 1 — No Populated Values ($N_{\text{pop}} = 0$):**
   - Condition: Column contains 0 populated cells (all empty, whitespace, or null markers).
   - Outcome: `state = InferenceState.UNKNOWN`, `candidate_type = None`, `heuristic_support_score = 0.0`.
2. **Precedence 2 — Insufficient Sample Count ($1 \le N_{\text{pop}} < N_{\text{min}} = 5$):**
   - Condition: Column contains at least 1 populated cell, but total populated cells $< 5$.
   - Outcome: `state = InferenceState.INSUFFICIENT_DATA`, `candidate_type = T_{\text{pred}}` (provisional), `heuristic_support_score = S` (computed from available cells), `requires_human_review = True`.
3. **Precedence 3 — Unresolved Competing Interpretations:**
   - Condition: High homogeneity ($H \ge 0.80$), but semantic ambiguity exists (date format ambiguity, boolean vs integer `0/1`, or competing detectors).
   - Outcome: `state = InferenceState.AMBIGUOUS`, `candidate_type = None` (or provisional), `heuristic_support_score = S`, `requires_human_review = True`.
4. **Precedence 4 — Low Homogeneity ($H < 0.80$):**
   - Condition: Bimodal or multi-type distribution with predominant type frequency below provisional threshold ($H < 0.80$).
   - Outcome: `state = InferenceState.AMBIGUOUS`, `candidate_type = None`, `heuristic_support_score = S < 0.80`, `requires_human_review = True`.
5. **Precedence 5 — Confident Type Inference:**
   - Condition: High homogeneity ($H \ge 0.80$) and support ($S \ge 0.70$) without semantic conflict.
   - Outcome: `state = InferenceState.INFERRED`, `candidate_type = T_{\text{pred}}`, `heuristic_support_score = S`, `requires_human_review = False`.

### 4.3 Explicit Examples for Each State

| State | Concrete Data Example | Homogeneity ($H$) | Support ($S$) | Candidate Type | M01 Projection |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`UNKNOWN`** | 100 cells, all empty, `""`, or `"N/A"`. | $0.0$ | $0.0$ | `None` | `ColumnType.STRING`, `type_confidence = 0.0`, `nullable = True` |
| **`INSUFFICIENT_DATA`** | 2 populated cells: `42`, `100`; 98 empty cells. | $1.0$ | $0.75$ | `INTEGER` (prov.) | `ColumnType.STRING`, `type_confidence = 0.75`, `nullable = True` |
| **`AMBIGUOUS` (Low Homog)** | 55 cells dates (`2024-01-01`), 45 cells integers (`12345`). | $0.55$ | $0.41$ | `None` | `ColumnType.STRING`, `type_confidence = 0.41`, `nullable = True` |
| **`AMBIGUOUS` (Semantic)** | 100 cells containing `"01/02/03"` (unresolved date order). | $1.0$ | $1.0$ | `None` | `ColumnType.STRING`, `type_confidence = 1.0`, `nullable = True` |
| **`INFERRED`** | 98 cells integers, 2 empty cells. | $1.0$ | $1.0$ | `INTEGER` | `ColumnType.INTEGER`, `type_confidence = 1.0`, `nullable = True` |

### 4.4 Operation Gating Policy
- Columns with `InferenceState.UNKNOWN`, `AMBIGUOUS`, or `INSUFFICIENT_DATA` are **strictly excluded from automated schema matching or record mutation**.
- They require explicit Human-in-the-Loop (HITL) review / approval before any type-dependent transformation can proceed.

---

## 5. Complete Deterministic 2D Sampling Budget & Matrix Realities

### 5.1 Hard Maximum of 10,000 Sampled Cells per Region
To guarantee memory boundedness across arbitrarily wide or deep worksheets:
- **Strict Cell Budget:** $B_{\text{cells}} = 10,000$ cells per region.
- **Deterministic 2D Dimension Slicing Formulation:**
  Let a detected region's `SemanticZoneType.BODY` zone span $R$ rows and $C$ columns.
  1. *Column Budget ($C_{\text{sample}}$):*
     - If $C \le 100$: sample all columns ($C_{\text{sample}} = C$).
     - If $C > 100$: allocate column budget $C_{\text{sample}} = \min(C, 1,000)$.
     - When $C > C_{\text{sample}}$: Deterministic 3-band column selection across table width:
       - Left band: first $\lfloor 0.40 \times C_{\text{sample}} \rfloor$ columns.
       - Middle band: centered $\lfloor 0.20 \times C_{\text{sample}} \rfloor$ columns.
       - Right band: last $\lfloor 0.40 \times C_{\text{sample}} \rfloor$ columns.
       - *Guarantee:* Trailing columns are **never systematically excluded**.
     - If $C > 10,000$: $C_{\text{sample}} = 10,000$, and $R_{\text{sample}} = 1$.
  2. *Row Budget ($R_{\text{sample}}$):*
     - Given chosen $C_{\text{sample}}$ columns:
       $$R_{\text{sample}} = \min\left(R, \left\lfloor \frac{B_{\text{cells}}}{C_{\text{sample}}} \right\rfloor\right)$$
     - When $R > R_{\text{sample}}$: Deterministic 3-band row selection:
       - Head band: first $\lfloor 0.40 \times R_{\text{sample}} \rfloor$ rows.
       - Middle band: centered $\lfloor 0.20 \times R_{\text{sample}} \rfloor$ rows.
       - Tail band: last $\lfloor 0.40 \times R_{\text{sample}} \rfloor$ rows.
  3. *Mathematical Proof of Boundedness:*
     $$\text{Total Sampled Cells} = C_{\text{sample}} \times R_{\text{sample}} = C_{\text{sample}} \times \min\left(R, \left\lfloor \frac{10,000}{C_{\text{sample}}} \right\rfloor\right) \le C_{\text{sample}} \times \frac{10,000}{C_{\text{sample}}} = 10,000$$
     - *Conclusion:* Total sampled cells is **strictly $\le 10,000$** under any geometry ($R \ge 1, C \ge 1$).

### 5.2 Sample Coverage & Truncation Metadata
The sampling output explicitly records:
- `sampled_row_count: int` ($R_{\text{sample}}$)
- `total_row_count: int` ($R$)
- `sampled_col_count: int` ($C_{\text{sample}}$)
- `total_col_count: int` ($C$)
- `sampled_cell_count: int` ($R_{\text{sample}} \times C_{\text{sample}} \le 10,000$)
- `is_truncated: bool` ($R > R_{\text{sample}}$ or $C > C_{\text{sample}}$)
- `truncation_details: Optional[str]`
- If truncated, report status is marked `TENTATIVE` and requires review if confidence is marginal.

### 5.3 Zero Full Matrix Allocation
- Streaming row ingestion via `StreamingWorkbookReader.stream_sheet(chunk_size=1000)` only reads populated cells into streaming dictionaries. Empty cells are skipped without allocating memory matrices.

---

## 6. Formula Dependency Graph: Node, Edge & Cycle Semantics

### 6.1 Exact Node and Edge Semantics
- **Node Semantics ($V$):**
  - `CellNode`: Discrete cell coordinate `Sheet!ColRow` (e.g. `Sheet1!A1`).
  - `RangeNode`: Rectangular coordinate block `Sheet!StartColStartRow:EndColEndRow` (e.g. `Sheet1!A1:B10`).
  - `NamedRangeNode`: Workbook or sheet-scoped defined name (e.g. `Workbook!TaxRate`).
  - `ExternalNode`: Reference to external workbook (e.g. `[Budget.xlsx]Sheet1!A1`).
  - `UnresolvedNode`: Unparseable or unresolvable formula reference.
- **Edge Semantics ($E$):**
  - Directed edge $(U \rightarrow V)$ signifies: **Node $V$ depends on Precedent $U$** ($U$ is an input to $V$; $V$ is a dependent of $U$).

### 6.2 Bounded Range Expansion Mechanics
- **Discrete Expansion Threshold ($K_{\text{expand}} = 1,000$):**
  - If a formula references a range $R = \text{start}:\text{end}$ with finite row and column bounds where $(\text{end\_row} - \text{start\_row} + 1) \times (\text{end\_col} - \text{start\_col} + 1) \le 1,000$:
    - The range is expanded into individual directed edges $(c \rightarrow V)$ for every discrete cell $c \in R$.
- **Hyper-Edge / Range Node Preservation:**
  - If the range is unbounded (`A:A`, `1:5`) or has cell count $> 1,000$:
    - Stored as a single `RangeNode` with a hyper-edge $(R \rightarrow V)$, strictly bounding memory complexity to $O(1)$ per range reference.

### 6.3 Cycle Detection Involving Range Nodes
- **Direct Range Containment Cycle:**
  - If a formula residing in cell $V = (s_v, r_v, c_v)$ references range $R = (s_r, r_{\min}..r_{\max}, c_{\min}..c_{\max})$, and $s_v = s_r$ with $r_{\min} \le r_v \le r_{\max}$ and $c_{\min} \le c_v \le c_{\max}$:
  - Cell $V$ is contained within its own precedent range!
  - Emits an immediate direct circular reference: `V -> R(contains V) -> V`.
- **Transitive Cycles via Tarjan's SCC:**
  - Standard Tarjan's SCC traversal across the directed graph. When traversing outgoing edges from RangeNode $R$, edges connect to any cell $W$ whose coordinates fall inside $R$. Any cycle path is recorded in `circular_paths: list[list[str]]`.
- **Incomplete Dependency Handling:**
  - External workbook references are represented as leaf `ExternalNode`s.
  - Unsupported formulas are captured as `UnsupportedFormulaNode` with edges marked `UNKNOWN_DEPENDENCY`.
  - **Incomplete Graph Invariant:** If `is_complete = False` or any unresolved dependency exists, the report **STRICTLY CANNOT claim `has_cycles = False` with certainty**; it must report `cycle_status = UNCERTAIN_INCOMPLETE_DEPENDENCIES` and `is_complete = False`.
- **Static Analysis Disclaimer:**
  - Formula AST parsing and dependency graph analysis are **strictly static structural evaluations**. **They do NOT calculate formula values, evaluate expressions, or execute calculation trees.**

---

## 7. M01 Contract Compatibility & Lossy Projection Audit

M01 contracts are frozen. The table below audits compatibility, distinguishing internal M05 preservation, field-level schema compatibility, and information lost during M01 projection:

| Proposed M05 Analytical Output | Target M01 Contract Model & Field | Field Compatibility | Information Lost During M01 Projection |
| :--- | :--- | :---: | :--- |
| `ColumnTypeProfile.inferred_type` | `ColumnMetadata.inferred_type: ColumnType` | **Schema Compatible** | **Lossy Projection:** Fine-grained `CURRENCY` and `PERCENTAGE` are collapsed into `ColumnType.DECIMAL`. `UNKNOWN`, `AMBIGUOUS`, and `INSUFFICIENT_DATA` states are projected to `ColumnType.STRING` carrier. |
| `ColumnTypeProfile.heuristic_support_score` | `ColumnMetadata.type_confidence: float` | **Schema Compatible** | Preserves score in $[0.0, 1.0]$. (Support score $< 0.80$ conveys ambiguity; $0.0$ conveys unknown). |
| `ColumnTypeProfile.nullability_ratio` | `ColumnMetadata.nullable: bool` | **Schema Compatible** | **Lossy Projection:** Quantitative ratio ($N_{\text{null}} / N_{\text{total}}$) is collapsed into binary boolean flag (`nullable = True`). |
| `ColumnTypeProfile.formula_pattern` | `ColumnMetadata.formula_pattern: Optional[str]` | **Schema Compatible** | Preserves canonical parameterized pattern string. |
| `TableTypeReport` + `SpatialTableRegion` | `TableMetadata` (`sheet_name`, `bounding_box`, `header_row`, `columns`, `is_list_object`) | **Schema Compatible** | Full conversion via M04 `export_to_table_metadata_list()`. |
| `FormulaGraphReport.node_count` | `FormulaGraphMetadata.node_count: int` | **Schema Compatible** | Populated directly. |
| `FormulaGraphReport.edge_count` | `FormulaGraphMetadata.edge_count: int` | **Schema Compatible** | Populated directly. |
| `FormulaGraphReport.has_cycles` | `FormulaGraphMetadata.has_cycles: bool` | **Schema Compatible** | **Lossy Projection:** Exact cycle paths (`circular_paths: list[list[str]]`) and cycle status are collapsed into a single boolean `has_cycles`. |
| `FormulaGraphReport.volatile_cells` | `FormulaGraphMetadata.volatile_cells: list[str]` | **Schema Compatible** | Populated directly from volatile function index. |
| Complete M05 Manifest | `DiscoveryManifest` (`manifest_id`, `workbook_path`, `sha256`, `tables`, `formula_graph`) | **Schema Compatible** | **Lossy Projection:** Rich AST node trees, dependency edge lists, and category counts are omitted from M01 manifest. |

### Safe Two-Tier Projection Policy:
1. **Tier 1 (Internal M05 Analytical Manifest):** Emits complete `SemanticAnalysisManifest` retaining full AST trees, cycle paths, category distribution counts, exact nullability ratios, and `InferenceState`.
2. **Tier 2 (Canonical M01 Projection):** Emits canonical M01 `DiscoveryManifest` conforming strictly to frozen schemas. Downstream consumers in Phase 1 must verify `type_confidence` and reference Tier 1 metadata before executing type-dependent mutations.

---

## 8. Unresolved Architectural Decisions Requiring Approval

The following decisions are submitted for Project Owner formal sign-off:

1. **Provisional 0.80 Homogeneity Threshold:**
   - *Issue:* Is the $H \ge 0.80$ threshold acceptable as a provisional rule until formal empirical calibration against the extended benchmark corpus in Phase 1?
   - *Recommendation:* Approved as provisional. Columns with $H < 0.80$ are marked `state = InferenceState.AMBIGUOUS`, `requires_human_review = True`, and strictly excluded from automated mutations.
2. **Ambiguous / Unknown / Insufficient Type Representation in M01 Projection:**
   - *Issue:* M01 `ColumnType` has no `AMBIGUOUS`, `UNKNOWN`, or `INSUFFICIENT_DATA` enum values.
   - *Recommendation:* Projected to `ColumnType.STRING` carrier with `type_confidence = 0.0` (for UNKNOWN/INSUFFICIENT_DATA) or `type_confidence = S` (for AMBIGUOUS), with downstream consumers checking M05 Tier 1 inference states.
3. **Range Node Hyper-Edge Threshold ($K_{\text{expand}} = 1,000$):**
   - *Issue:* Expanding ranges $> 1,000$ cells or whole columns (`A:A`) risks exhausting memory.
   - *Recommendation:* Approved. Ranges $> 1,000$ cells or unbounded columns remain Range Nodes without individual cell edge expansion.
