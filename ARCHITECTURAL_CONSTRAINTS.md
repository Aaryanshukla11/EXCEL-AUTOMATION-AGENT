# Autonomous Excel Intelligence Platform V2
## Architectural Constraints & Invariants (ARCHITECTURAL_CONSTRAINTS.md)

---

### 1. Inviolable System Invariants ("The Golden Rules")

The following constraints are non-negotiable architectural invariants of the Autonomous Excel Intelligence Platform V2. Any component, PR, or configuration that violates these invariants must be rejected automatically.

```
+-----------------------------------------------------------------------------------+
|                        THE INVIOLABLE SYSTEM INVARIANTS                           |
+-----------------------------------------------------------------------------------+
| INVARIANT 1: THE AIR-GAP INVARIANT                                                |
| Under no circumstances may an LLM, prompt, or cognitive agent directly open,     |
| write, or execute code against a physical workbook file. All mutations must be    |
| expressed exclusively as schema-validated Intermediate Representation (WO-IR).    |
+-----------------------------------------------------------------------------------+
| INVARIANT 2: THE ZERO-ASSUMPTION INVARIANT                                        |
| No component may contain hardcoded sheet names ("Sheet1", "Data", "Summary"),     |
| column names ("Date", "ID", "Amount"), business formulas, or domain templates.    |
| All structural and semantic properties must be derived from empirical evidence.  |
+-----------------------------------------------------------------------------------+
| INVARIANT 3: THE NON-DESTRUCTIVE PRESERVATION INVARIANT                           |
| Non-targeted workbook data, cell formatting, font palettes, borders, comments,   |
| charts, drawing parts, metadata, and embedded macro streams must remain bitwise   |
| unharmed during any execution.                                                    |
+-----------------------------------------------------------------------------------+
| INVARIANT 4: THE DETERMINISTIC COMPILATION INVARIANT                              |
| The execution of a validated WO-IR package against an identical workbook state     |
| must be 100% reproducible and deterministic, producing identical outputs.         |
+-----------------------------------------------------------------------------------+
| INVARIANT 5: THE MANDATORY HITL ESCALATION INVARIANT                              |
| Any operation with inference confidence below threshold (< 0.85), destructive    |
| data overwrite, or ambiguous targets must halt and require explicit human sign-off.|
+-----------------------------------------------------------------------------------+
| INVARIANT 6: THE REVERSIBLE TRANSACTION INVARIANT                                 |
| Every committed mutation must be accompanied by an inverse delta patch enabling   |
| instant, guaranteed point-in-time rollback.                                       |
+-----------------------------------------------------------------------------------+
```

---

### 2. Architectural Boundary Constraints

#### 2.1 LLM & Cognitive Tier Constraints
1. **No Direct Code Generation for Execution**:
   - The LLM must never generate arbitrary Python, VBA, Bash, or PowerShell scripts intended to be executed against the workbook.
   - The LLM's sole executable output format is the declarative WO-IR schema.
2. **Context Independence**:
   - Agents must not depend on global session memory or shared in-memory mutable state.
   - Each agent must function as a pure, stateless function of its input JSON payload.

#### 2.2 Execution Tier Constraints
1. **Network Egress Block**:
   - The Deterministic Execution Layer must run in an environment with zero outbound network access to prevent data exfiltration.
2. **Formula Isolation**:
   - External links, DDE commands, and unwhitelisted functions are strictly prohibited in synthesized formulas.
3. **Memory Footprint**:
   - Ingestion and mutation operations must not hold full uncompressed XML document trees in memory indefinitely; streaming or indexed chunking must be used for large datasets (>100,000 cells).

---

### 3. Explicit Documentation of Unresolved Architectural Decisions

The following architectural trade-offs are explicitly flagged as open decisions requiring engineering consensus:

---

#### Decision 1: Low-Level Spreadsheet Manipulation Engine Selection
* **Current Status**: **PROPOSED (Under Evaluation)**
* **Options Considered**:
  - **Option A: Pure Python OpenXML Engine (e.g., enhanced `openpyxl` / `defusedxml`)**:
    - *Pros*: Cross-platform, headless Linux support, easy sandboxing, no COM dependencies.
    - *Cons*: Slower formula recalculation; limited native support for complex conditional formatting evaluation and dynamic array formula spill calculations.
  - **Option B: Rust-based Core Engine with PyO3 Bindings**:
    - *Pros*: High performance, memory-safe, sub-millisecond AST and spatial indexing, zero GC latency.
    - *Cons*: Higher initial implementation complexity; requires custom OpenXML part preservation logic.
  - **Option C: Headless LibreOffice / Calc Core Integration**:
    - *Pros*: Robust native calculation engine.
    - *Cons*: Heavyweight binary dependency, difficult to sandbox securely, potential formatting shift when re-saving `.xlsx`.
* **Recommendation**: Option B (Rust Core) or Option A (Enhanced OpenXML with dedicated formula graph engine).

---

#### Decision 2: Formula Recalculation Strategy
* **Current Status**: **PROPOSED (Under Evaluation)**
* **Options Considered**:
  - **Option A: Write-Time Recalculation Engine**:
    - The platform includes a built-in formula evaluation engine that calculates and caches cell values into the OpenXML `<v>` tag upon saving.
    - *Pros*: Output workbook has pre-calculated values visible in third-party viewers that do not run Excel's calculation engine.
    - *Cons*: Must re-implement Excel's full calculation engine faithfully to avoid value discrepancies with official Excel.
  - **Option B: Flag-Based Deferred Recalculation (Dirty Tree Tagging)**:
    - The platform writes formulas to the `<f>` tag and sets the OpenXML `<calcPr fullCalcOnLoad="1" forceFullCalc="1"/>` tag, delegating actual computation to Excel when next opened.
    - *Pros*: Guarantees 100% calculation accuracy according to Microsoft Excel's own calculation engine; simplifies execution layer.
    - *Cons*: Headless viewers or downstream scripts that only read the `<v>` value tag without calculating will see blank values until opened in Excel.
* **Recommendation**: Hybrid — Use Option B as primary for OpenXML persistence, paired with a lightweight shadow formula evaluator in Tier 3 for dry-run invariant checking.

---

#### Decision 3: Context Token Window vs. Topological Summarization Fidelity
* **Current Status**: **PROPOSED (Under Evaluation)**
* **Options Considered**:
  - **Option A: Aggressive Topological Summarization**:
    - Only send block bounding boxes, column inferred types, and 3 sample rows to the LLM Orchestrator.
    - *Pros*: Minimal token usage, sub-second latency, handles sheets with 1,000,000 rows easily.
    - *Cons*: May miss subtle semantic anomalies or outliers hidden deep within the data rows.
  - **Option B: Two-Pass Adaptive Retrieval**:
    - Pass 1 sends topological summary. The Orchestrator can dynamically request specific cell range windows from the Ingestion Subsystem before synthesizing the plan.
    - *Pros*: Best balance of token efficiency and precision.
    - *Cons*: Introduces multi-turn latency between Orchestrator and Ingestion Subsystem.
* **Recommendation**: Option B (Two-Pass Adaptive Retrieval).

---

#### Decision 4: Granularity of the Workbook Operation Intermediate Representation (WO-IR)
* **Current Status**: **PROPOSED (Under Evaluation)**
* **Options Considered**:
  - **Option A: Micro-Op AST (Cell-Level Primitives)**:
    - Every change is an individual cell operation (`SET_CELL_VAL(A1, 10)`, `SET_CELL_VAL(A2, 20)`).
    - *Pros*: Extremely simple execution engine; trivial rollback diffs.
    - *Cons*: Huge WO-IR payloads for large column operations; places calculation of row coordinates on the cognitive agents.
  - **Option B: Macro-Op Vector Primitives**:
    - Operations specify block-level and column-level actions (`INSERT_COLUMN(table_id="blk_001", header="Margin", formula_template="{Revenue} - {Cost}")`).
    - *Pros*: Compact payloads, cognitive agents reason at the relational level; execution layer compiles template into individual cell coordinates deterministically.
    - *Cons*: More compilation complexity inside Tier 3 execution layer.
* **Recommendation**: Option B (Macro-Op Vector Primitives) with deterministic expansion to micro-ops during the dry-run phase.
