# Milestone M05 — Semantic Type & Formula Analysis
## Document 2 of 4: Detailed Requirements & Specification

**Date:** 2026-11-22  
**Milestone:** M05 — Semantic Type & Formula Analysis  
**Stage:** Prompt 1 of 4 (Architecture Inspection, Requirements Discovery & Planning)  
**Status:** COMPLETE (Planning & Audit Only — Zero Code Modification)  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes)

---

## 1. Primary Purpose & Scope

Milestone M05 delivers the **Semantic Data Type Profiler & Formula Dependency Analyzer** specified in Section 2, Section 5.2, and Section 14.1 of the System Architecture Design (SAD).

Its objective is to transform raw cell tokens, spatial table regions (`SpatialTableRegion`), and formula strings (`<f>`) into:
1. Strongly-typed, statistically evaluated column data types with explicit inference states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`) and heuristic support scores.
2. A formal Abstract Syntax Tree (AST) representing every supported formula in the workbook, with non-fabricating error nodes for unsupported and malformed expressions.
3. A static directed calculation dependency graph (DAG) mapping precedent and dependent relationships across cells, detecting circular references, and cataloging volatile functions.
4. The canonical `DiscoveryManifest` uniting spatial table metadata and formula graph metadata.

---

## 2. Functional Requirements (FRs)

### FR-1: Semantic Data Type Inference & Explicit Inference States
- **FR-1.1 (Zone-Constrained Sampling):** Type inference must evaluate cell values strictly within the bounding box of the `SemanticZoneType.BODY` zone of each `SpatialTableRegion`. Cell values in title banners, column headers, subtotals, grand totals, and footnotes must be strictly excluded from column data type statistics.
- **FR-1.2 (Explicit Internal Inference States):** Every column must be assigned an explicit `InferenceState`:
  - `INFERRED`: Predominant candidate type identified with high support ($H \ge 0.80$, $S \ge 0.70$) without semantic ambiguity.
  - `UNKNOWN`: Column is 100% empty, blank, or composed entirely of null markers (`N/A`, `-`, `None`).
  - `AMBIGUOUS`: Bimodal, multi-type competing categories, low homogeneity ($H < 0.80$), or semantic ambiguity despite high homogeneity.
  - `INSUFFICIENT_DATA`: Column contains populated cells, but total populated count is below statistical threshold ($1 \le N_{\text{pop}} < 5$).
- **FR-1.3 (State Precedence Order):**
  1. *No Populated Values ($N_{\text{pop}} = 0$):* $\implies$ `UNKNOWN`, `candidate_type = None`, `heuristic_support_score = 0.0`.
  2. *Insufficient Sample Count ($1 \le N_{\text{pop}} < 5$):* $\implies$ `INSUFFICIENT_DATA`, `candidate_type = T_{\text{pred}}` (prov.), `heuristic_support_score = S`, `requires_human_review = True`.
  3. *Unresolved Semantic Ambiguity:* (e.g. date format ambiguity `"01/02/03"`, boolean vs integer `0/1`, or competing detectors) $\implies$ `AMBIGUOUS` regardless of homogeneity ($S$ can be $\ge 0.80$), `requires_human_review = True`.
  4. *Low Homogeneity ($H < 0.80$):* $\implies$ `AMBIGUOUS`, `heuristic_support_score = S < 0.80`, `requires_human_review = True`.
  5. *Confident Inference ($H \ge 0.80, S \ge 0.70$):* $\implies$ `INFERRED`, `candidate_type = T_{\text{pred}}`, `heuristic_support_score = S`.
- **FR-1.4 (Multi-Pattern Value Classification):** Every populated cell in a column must be classified into a primary semantic category:
  - `INTEGER`: Whole numeric values (e.g. `42`, `-100`, `"1001"` stored as text).
  - `DECIMAL`: Fractional floating-point numbers (e.g. `3.14159`, `"-0.05"`).
  - `CURRENCY`: Currency strings (e.g. `"$1,250.50"`, `"€500"`, `"($150.00)"` accounting negative).
  - `PERCENTAGE`: Percentage strings (e.g. `"15.5%"`, `"-0.25%"`).
  - `DATE`: ISO-8601 strings (`"2024-01-15"`), standard date formats (`"01/15/2024"`, `"15-Jan-2024"`), or Excel date serials with date formatting.
  - `BOOLEAN`: Logical truth values (`TRUE`, `FALSE`, `"true"`, `"false"`, `"Yes"`, `"No"`, `"Y"`, `"N"`).
  - `STRING`: Unstructured text, codes, descriptions, and heterogeneous characters.
  - `FORMULA`: Cells whose primary contents are calculation formulas (`<f>` present).
  - `NULL_OR_BLANK`: Empty cells, whitespace strings, or standard null representations (`None`, `""`, `"N/A"`, `"-"`, `"#N/A"`).
- **FR-1.5 (Statistical Metric Aggregation):** For each column in a detected table, compute:
  - `total_cells`: Total row count in `BODY` ($N_{\text{total}}$).
  - `populated_cells`: Count of non-null cells ($N_{\text{pop}}$).
  - `null_cells`: Count of blank/null cells ($N_{\text{null}} = N_{\text{total}} - N_{\text{pop}}$).
  - `nullability_ratio`: $N_{\text{null}} / N_{\text{total}}$.
  - `category_counts`: Dictionary mapping each candidate type to its occurrence count.
  - `predominant_type`: Type with highest frequency among populated cells ($T_{\text{pred}} = \arg\max_T N_T$).
  - `homogeneity_ratio`: $H = N_{T_{\text{pred}}} / N_{\text{pop}}$.
- **FR-1.6 (Heuristic Support Score Formulation):**
  $$S = \max\left(0.0, \min\left(1.0, H \times (1.0 - \text{Penalty}_{\text{ambiguity}})\right)\right)$$
  where:
  $$\text{Penalty}_{\text{ambiguity}} = \begin{cases} 
  0.0 & \text{if } H \ge 0.95 \\ 
  0.10 & \text{if } 0.80 \le H < 0.95 \\ 
  0.25 & \text{if } H < 0.80 
  \end{cases}$$
- **FR-1.7 (M01 Downstream Carrier Projection Policy):**
  - M01's frozen `ColumnType` has no `UNKNOWN`, `AMBIGUOUS`, or `INSUFFICIENT_DATA` enum members.
  - Columns with `UNKNOWN`, `AMBIGUOUS`, or `INSUFFICIENT_DATA` project to `ColumnType.STRING` solely as a schema carrier.
  - Crucially: `type_confidence = S` preserves the true underlying support score (e.g. $0.0$ for UNKNOWN; true calculated score for AMBIGUOUS and INSUFFICIENT_DATA), with `nullable = True`.
  - Downstream consumers in Phase 1 (consolidation planning) must verify `type_confidence` and reference Tier 1 metadata. **A carrier `STRING` with non-inferred state is NEVER treated as a verified semantic string.**
  - *Operation Gating:* Any column with state `UNKNOWN`, `AMBIGUOUS`, or `INSUFFICIENT_DATA` is **strictly excluded from automated schema matching or record mutation**. It requires explicit Human-in-the-Loop (HITL) approval.
- **FR-1.8 (Complete Deterministic 2D Sampling Budget):**
  - Hard cell budget: $B_{\text{cells}} = 10,000$ cells per region.
  - Let region bounds in `SemanticZoneType.BODY` have $R$ rows and $C$ columns.
  - $C_{\text{sample}} = \min(C, 1000)$ if $C > 100$, else $C$. When $C > C_{\text{sample}}$, deterministically sample left ($40\%$), middle ($20\%$), and right ($40\%$) column bands across table width.
  - If $C > 10,000$: $C_{\text{sample}} = 10,000$, and $R_{\text{sample}} = 1$.
  - $R_{\text{sample}} = \min(R, \lfloor 10,000 / C_{\text{sample}} \rfloor)$. When $R > R_{\text{sample}}$, deterministically sample head ($40\%$), middle ($20\%$), and tail ($40\%$) row bands.
  - *Proof:* Total sampled cells $= C_{\text{sample}} \times R_{\text{sample}} \le 10,000$ strictly under all geometries.
  - Output records: `sampled_row_count`, `total_row_count`, `sampled_col_count`, `total_col_count`, `sampled_cell_count`, `is_truncated`, `truncation_details`.
  - Truncated tables marked `TENTATIVE`. Zero full worksheet matrix allocation.

### FR-2: Explicit Formula Grammar & Lexical Tokenization
- **FR-2.1 (Supported Grammar Production Rules - EBNF):**
  ```ebnf
  Expression          ::= ComparisonExpr
  ComparisonExpr      ::= ConcatExpr ( ( "=" | "<" | ">" | "<=" | ">=" | "<>" ) ConcatExpr )*
  ConcatExpr          ::= AdditiveExpr ( "&" AdditiveExpr )*
  AdditiveExpr        ::= MultiplicativeExpr ( ( "+" | "-" ) MultiplicativeExpr )*
  MultiplicativeExpr  ::= PowerExpr ( ( "*" | "/" ) PowerExpr )*
  PowerExpr           ::= PercentExpr ( "^" PercentExpr )*
  PercentExpr         ::= UnaryExpr ( "%" )*
  UnaryExpr           ::= ( "+" | "-" )* PrimaryExpr
  PrimaryExpr         ::= Literal | Reference | FunctionCall | ArrayConstant | "(" Expression ")"
  Literal             ::= NumberLiteral | StringLiteral | BooleanLiteral | ErrorLiteral
  Reference           ::= SingleCellRef | RangeRef | StructuredRef | ExternalRef
  SingleCellRef       ::= ( SheetPrefix )? "$"? [A-Za-z]+ "$"? [0-9]+
  RangeRef            ::= SingleCellRef ":" SingleCellRef
                        | ( SheetPrefix )? "$"? [A-Za-z]+ ":" "$"? [A-Za-z]+
                        | ( SheetPrefix )? "$"? [0-9]+ ":" "$"? [0-9]+
  SheetPrefix         ::= ( SheetName | "'" SheetName "'" ) "!"
                        | ( SheetName ":" SheetName | "'" SheetName ":" SheetName "'" ) "!"
  StructuredRef       ::= ( TableName )? "[" ( StructuredSpecifier "," )? ColumnSpecifier "]"
  ExternalRef         ::= "[" WorkbookName "]" ( SheetPrefix )? ( SingleCellRef | RangeRef )
  FunctionCall        ::= FunctionName "(" ( ArgumentList )? ")"
  ArrayConstant       ::= "{" ArrayRow ( ";" ArrayRow )* "}"
  ArrayRow            ::= Literal ( "," Literal )*
  ```
- **FR-2.2 (Representative Valid and Invalid Constructs):**
  - *Structured references:*
    - **Valid:** `Table1[Sales]`, `Table1[[#Headers],[Sales]]`, `Table1[[#Totals],[Sales]]`, `Table1[@Sales]`, `Table1[#All]`, `[@[Column Name]]`.
    - **Invalid / Unsupported:** Unbracketed column names (`Table1.Sales`), complex multi-table cross-joins without brackets.
  - *3D references:*
    - **Valid:** `Sheet1!A1`, `'Sales Summary'!A1:B10`, `Sheet1:Sheet3!A1`, `'Jan:Dec'!$A$1:$B$10`.
    - **Invalid / Unsupported:** 3D references with sheet wildcards (`Sheet*!A1`), references across disconnected external files.
  - *External workbook references:*
    - **Valid:** `[Budget.xlsx]Sheet1!A1`, `'[Corporate Budget 2024.xlsx]Q1 Summary'!$B$10`.
    - **Invalid / Unsupported:** Dynamic indirect external links (`INDIRECT("[" & A1 & "]Sheet1!A1")`), DDE/OLE links (`=Excel|Sheet1!'A1'`).
  - *Array constants:*
    - **Valid:** `{1, 2, 3; 4, 5, 6}`, `{"a", "b"; "c", "d"}` (strictly rectangular matrices of literal constants).
    - **Invalid / Unsupported:** Ragged arrays (`{1, 2; 3}`), arrays containing cell references or formulas (`{A1, B1}`).
- **FR-2.3 (Separation of Syntax Recognition from Semantic Interpretation):**
  - The AST parser recognizes syntax structure only; it does not evaluate cell values or calculate results.
- **FR-2.4 (Recognized but Unsupported Syntax):**
  - Dynamic array spill hash (`A1#`), third-party UDFs (`=Bloomberg.BDP(...)`), complex nested external link chains, and lambda helpers (`LAMBDA`, `MAP`, `REDUCE`).
  - *Policy:* Tokenized and bounded via character span tracking. Preserved as `UnsupportedFormulaNode` containing raw text, span, and classification. Dependency recorded as `UNKNOWN_DEPENDENCY`; graph marked `is_complete = False`. Never fabricates placeholder AST semantics.
- **FR-2.5 (Malformed Syntax):**
  - Unmatched parentheses, dangling operators, unclosed string literals.
  - *Policy:* Wraps in `UnparsedFormulaNode` capturing raw text, error message, and offset. Never throws unhandled exceptions.

### FR-3: Formula Abstract Syntax Tree (AST) Parsing
- **FR-3.1 (Recursive-Descent Parser):** Implement an operator-precedence recursive-descent parser emitting frozen Pydantic v2 AST nodes.
- **FR-3.2 (Typed AST Nodes):**
  - `LiteralNode`: Numeric, string, boolean, or error literal.
  - `CellReferenceNode`: Single cell reference with sheet name, column, row, and absolute/relative flags.
  - `RangeReferenceNode`: 2D/3D rectangular range with top-left and bottom-right cell bounds.
  - `StructuredReferenceNode`: Excel Table structured reference with table name, column specifiers, and row context (`@`).
  - `FunctionCallNode`: Function name and list of argument AST nodes.
  - `UnaryOpNode`: Prefix operator (`+`, `-`) and operand AST.
  - `BinaryOpNode`: Infix operator and left/right operand ASTs.
  - `PostfixOpNode`: Postfix operator (`%`) and operand AST.
  - `ArrayLiteralNode`: 2D matrix of argument expressions.
  - `UnsupportedFormulaNode`: Recognized but unsupported syntax with exact span and raw text.
  - `UnparsedFormulaNode`: Malformed syntax with error offset and raw text.
- **FR-3.3 (Prevention of Partial Parsing Conflation):** The parser returns `FormulaParseResult` with explicit status: `PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, or `PARSE_ERROR`. Partially parsed expressions are never reported as `PARSED_COMPLETE`.

### FR-4: Formula Dependency Graph Construction
- **FR-4.1 (Directed Graph & Edge Semantics):** Construct directed graph $G = (V, E)$ where:
  - Nodes $V$: `CellNode` (`Sheet1!A1`), `RangeNode` (`Sheet1!A1:B10`), `NamedRangeNode`, `ExternalNode`.
  - Directed edge $(U \rightarrow V)$ denotes that Node $V$ depends on Precedent $U$ ($U$ is an input to $V$; $V$ is a dependent of $U$).
- **FR-4.2 (Bounded Range Expansion):**
  - Compact ranges ($\le 1,000$ cells) with finite row/col bounds are expanded into individual cell edges $(c \rightarrow V)$.
  - Large ranges ($> 1,000$ cells) or unbounded ranges (`A:A`, `1:5`) are stored as single `RangeNode`s with hyper-edges $(R \rightarrow V)$, strictly bounding memory complexity to $O(1)$ per range.
- **FR-4.3 (Defined Names & External References):**
  - Named ranges are resolved against M03 `DeclaredOpenXmlFacts.defined_names`. If resolvable, mapped to target coordinate; if unresolvable, stored as `NamedRangeNode(is_resolvable=False)`.
  - External workbook references are represented as `ExternalNode(is_external=True)`.

### FR-5: Dependency Analysis, Cycle Sentinels & Volatile Index
- **FR-5.1 (Cycle Detection):**
  - Direct range containment cycles: If formula cell $V = (s_v, r_v, c_v)$ references range $R$ on sheet $s_v$ with $r_{\min} \le r_v \le r_{\max}$ and $c_{\min} \le c_v \le c_{\max}$, detect immediate circular reference: `V -> R(contains V) -> V`.
  - Transitive cycles: Detect directed cycles via Tarjan's SCC algorithm; record exact cycle path in `circular_paths: list[list[str]]` and set `FormulaGraphMetadata.has_cycles = True`.
- **FR-5.2 (Incomplete Graph Invariant):** If `is_complete = False` or any unresolved dependency exists, the report **STRICTLY CANNOT claim `has_cycles = False` with certainty**; it must report `cycle_status = UNCERTAIN_INCOMPLETE_DEPENDENCIES` and `is_complete = False`.
- **FR-5.3 (Volatile Function Cataloging):** Catalog all formula cells calling volatile Excel functions (`NOW`, `TODAY`, `RAND`, `RANDBETWEEN`, `OFFSET`, `INDIRECT`, `INFO`, `CELL`) into `FormulaGraphMetadata.volatile_cells: list[str]`.
- **FR-5.4 (Static Analysis Disclaimer):** Static dependency analysis strictly maps calculation topology; it **does NOT calculate formula results or evaluate expressions**.

### FR-6: Canonical Export & Manifest Synthesis
- **FR-6.1 (TableMetadata Bridge):** Supply verified `inferred_types_by_region` to M04 `export_to_table_metadata_list()`, producing valid canonical M01 `TableMetadata` list with zero fabrication.
- **FR-6.2 (DiscoveryManifest Assembly):** Combine `list[TableMetadata]` and `FormulaGraphMetadata` into the root M01 `DiscoveryManifest`.

---

## 3. Non-Functional Requirements (NFRs)

### NFR-1: Bounded Memory Complexity ($O(W \cdot C + K)$)
- **Active Streaming Memory:** Streaming row ingestion must maintain bounded sliding-window memory $O(W \cdot C)$, where $W \le 50$ rows and $C$ is the active column span.
- **Retained Graph Bounds ($K$):** Multi-tier resource caps strictly bound retained output objects:
  - `max_graph_nodes = 50,000`
  - `max_graph_edges = 100,000`
  - `max_range_expansion = 1,000`
  - `max_sampled_cells_per_region = 10,000`
- **Process Memory Ceiling:** In 100,000-row workloads, peak resident set size (RSS) must remain strictly below the defensive 235 MiB tripwire and 250 MiB hard ceiling.

### NFR-2: Throughput & Latency Budgets
- **Semantic Type Profiling:** Execute in **$< 100\text{ ms}$ per 10,000 populated cells**.
- **Formula Lexing & Parsing:** Parse in **$< 20\text{ \mu s}$ per formula expression** ($> 50,000$ formulas/sec).
- **Graph Construction & Cycle Detection:** Construct DAG and detect cycles in **$< 500\text{ ms}$ for 10,000 formula nodes**.
- **Total Workbook Analysis:** Standard multi-sheet workbooks (< 50 MB, < 100,000 rows) must complete full type inference and formula graph analysis in **$< 3.0\text{ seconds}$**.

### NFR-3: Determinism & Immutability
- Given the same input workbook, M05 must produce bit-for-bit identical column types, support scores, formula ASTs, and dependency edges across multiple runs.
- Source workbook files must remain completely unmodified (SHA-256 integrity strictly verified before and after analysis).

### NFR-4: Zero External Native Dependencies
- All M05 components must be implemented in pure Python with standard Pydantic v2. No external compiler, Java runtime, or binary wheels required.

### NFR-5: Multi-Language & Multi-Python Compatibility
- 100% passing test suites on Python 3.12 and Python 3.13 on Windows x86_64, Linux, and macOS.
