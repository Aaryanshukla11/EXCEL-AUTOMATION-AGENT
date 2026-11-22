# Autonomous Excel Intelligence Platform V2
## Engineering Requirements Specification (REQUIREMENTS_SPECIFICATION.md)
### Status: Proposed Capability Specification (Pending Governance Sign-Off — M01–M05 Baselines Authoritative)

---

### 1. Purpose, Scope & Governance Precedence

This specification establishes the functional, non-functional, and structural requirements for the **Autonomous Excel Intelligence Platform V2**.

> [!IMPORTANT]
> **GOVERNANCE & PRECEDENCE CHARTER:**
> - This document is a **proposed capability specification**. It does NOT supersede, alter, or replace the approved Release 1.0 baselines (`PRODUCT_REQUIREMENTS_BASELINE.md`, `ARCHITECTURE_DECISION_RECORD.md` ADR-001–ADR-007, or `R1_0_SYSTEM_ARCHITECTURE_DESIGN.md`).
> - Milestone implementations **M01 through M05** remain authoritative, frozen, and binding. Specifically:
>   - **M05 Prompt 3 (Formula Lexer, Parser & Strongly-Typed AST)** remains authoritative strictly for lexical analysis, recursive-descent parsing, AST model generation, and root parse status categorization (`PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, `PARSE_ERROR`). Prompt 3 produces typed AST nodes and reference nodes only.
>   - **M05 Prompt 4 (Precedent Extraction, Dependency Graph & Manifest Integration)** is a distinct, future milestone stage. Precedent extraction belongs exclusively to Prompt 4.
> - Implementation of any requirement herein remains strictly subject to formal Gate review and project owner sign-off.

The platform is designed to ingest, comprehend, validate, and manipulate Microsoft Excel workbooks of arbitrary, previously unknown layouts across diverse business verticals without human-configured templates, hardcoded column/sheet names, or fixed mappings.

---

### 2. Core Architectural Principles & Invariants

1. **Zero Domain-Specific Hardcoding (INV-01):**
   The platform strictly prohibits hardcoding domain-specific vocabularies, column nomenclatures, sheet names, or business logic. All structural boundaries, data types, and entity relationships must be discovered dynamically using empirical evidence.
2. **Declarative Execution Isolation (INV-02):**
   The cognitive orchestration tier operates under strict declarative execution isolation: it possesses zero direct file system write handles, cannot execute operating system commands, and emits only strongly-typed, schema-validated declarative operation plans (Workbook Operation Intermediate Representation — WO-IR). This is an application-level isolation boundary, distinct from physical or network air-gapping.
3. **Lossless OpenXML Preservation (INV-03):**
   Under experimentally verified conditions (local NTFS filesystem with targeted OpenXML package patching), non-targeted package parts (`vbaProject.bin`, drawings, shapes, slicers, themes, and unedited worksheets) must be preserved without corruption or alteration. Modified worksheets undergo schema-conformant OpenXML serialization. Universal preservation across arbitrary unverified package features is explicitly disclaimed.
4. **Context-Gated Human Authority (INV-04):**
   Automated mutations are restricted to non-destructive operations. Any operation involving ambiguous targets, low heuristic support scores, all-null-marker columns, or potential destructive overwrites must halt for interactive Human-in-the-Loop (HITL) authorization.
5. **Multi-Layered Recovery & Durability (INV-05):**
   Mutations must provide transactional durability through staged writes, Write-Ahead Logging (WAL) where durable transaction intent strictly precedes file mutation, and exact pre-state backup snapshots (`.bak`) for recovery under verified backup integrity and successful restore conditions on tested local NTFS filesystems. Universal disaster recovery across power loss or arbitrary storage targets is disclaimed.

---

### 3. Functional Requirements (FR)

#### FR-1: Domain-Agnostic Ingestion & 2D Spatial Discovery
* **FR-1.1 (Multi-Format Streaming Ingestion):** Ingest `.xlsx` and `.xlsm` workbooks via the high-performance streaming parser (M02 baseline) under sampled, event-driven memory guard enforcement:
  - Warning tripwire at exactly **235,000,000 bytes** working set (`WARNING_TRIPWIRE_WORKING_SET_BYTES`).
  - Typed hard-error ceiling at exactly **250,000,000 bytes** working set (`HARD_CEILING_WORKING_SET_BYTES`).
  - Attributable allocation burst delta trigger at **8,000,000 bytes** (`EVENT_DRIVEN_DELTA_THRESHOLD_BYTES = 8_000_000` in `crates/excel_intel_rs/src/memory_guard.rs`).
  Enforcement is an application-level guard evaluated via dual-cadence telemetry (sampled every 1,000 rows or on burst allocation); it is not an instantaneous kernel-enforced RSS cap.
* **FR-1.2 (2D Spatial Segmentation):** Decompose unconstrained worksheets into discrete tabular regions (`SpatialTableRegion`) pursuant to M04 spatial contracts, identifying:
  - Multi-tier hierarchical headers.
  - Transposed row-oriented records.
  - Subtotal and summary boundary vectors.
  - Disjoint tables separated by irregular whitespace.
* **FR-1.3 (Zone Separation):** Explicitly isolate `SemanticZoneType.BODY` from header, title, subtotal, and footnote zones.

#### FR-2: Statistical Semantic Profiling & Dynamic Typing (M05 Prompt 2)
* **FR-2.1 (Zone-Constrained Sampling):** Evaluate column data types exclusively within the `BODY` zone of detected tables under the deterministic $B_{\text{cells}} \le 10,000$ budget.
* **FR-2.2 (Explicit Inference States):** Classify every column into one of four discrete states:
  - `INFERRED`: Predominant candidate type identified with high homogeneity ($H \ge 0.80$) and heuristic support score ($S \ge 0.70$) without semantic ambiguity.
  - `UNKNOWN`: Column contains zero populated cells ($N_{\text{pop}} = 0$; 100% genuinely blank/empty).
  - `AMBIGUOUS`: Bimodal distributions, competing type candidates, low homogeneity ($H < 0.80$), or columns composed entirely of null markers (`N/A`, `-`, `None`, `#N/A`).
  - `INSUFFICIENT_DATA`: Populated cell count is below statistical threshold ($1 \le N_{\text{pop}} < 5$).
* **FR-2.3 (Heuristic Support Score Formulation):** Compute support scores strictly via approved M05 FR-1.6:
  $$S = \max\left(0.0, \min\left(1.0, H \times (1.0 - \text{Penalty}_{\text{ambiguity}})\right)\right)$$
  where:
  $$\text{Penalty}_{\text{ambiguity}} = \begin{cases} 
  0.0 & \text{if } H \ge 0.95 \\ 
  0.10 & \text{if } 0.80 \le H < 0.95 \\ 
  0.25 & \text{if } H < 0.80 
  \end{cases}$$
  The metric $S$ is explicitly a *heuristic support score* derived from token frequency distributions, NOT a calibrated Bayesian or frequentist probability.
* **FR-2.4 (M01 Carrier Projection):** Columns in non-inferred states (`UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`) project to M01 `ColumnType.STRING` solely as a schema carrier with `nullable=True`, preserving the true support score $S$ and requiring mandatory HITL review before mutation.

#### FR-3: Formula Syntactic Analysis & Static Dependency Modeling
* **FR-3.1 (M05 Prompt 3 Scoped EBNF Parsing Scope):** Parse formula strings from `<f>` tags using the authorized M05 Prompt 3 recursive-descent parser and lexical analyzer. Prompt 3 produces typed AST nodes and reference nodes only. Precedent extraction is strictly deferred to Prompt 4.
* **FR-3.2 (Approved Root Parse Statuses):** The parser contract emits one of three explicit root statuses (`FormulaParseStatus`):
  1. `PARSED_COMPLETE`: Formula fully recognized by the scoped EBNF grammar, emitting a complete AST.
  2. `UNSUPPORTED_SYNTAX`: Recognized unsupported constructs (e.g. dynamic array spill `#`, `LAMBDA` parameters) emitting `UnsupportedFormulaNode` without fabricating AST semantics.
  3. `PARSE_ERROR`: Syntactically malformed expressions, extra unconsumed tokens, or nesting depth overflows emitting `UnparsedFormulaNode`.
  Subordinate syntax classifications (Category A: Supported, Category B: Unsupported Syntax, Category C: Parse Error) map directly to these three root statuses and must never replace them.
* **FR-3.3 (Separation of Syntax Parsing from Security Allowlist Policy):** Syntactic AST parsing is strictly separated from formula security allowlisting. A syntactically recognized function (e.g. `CMD(...)` or `WEBSERVICE(...)` or custom functions) that is valid under standard function syntax `IDENTIFIER '(' args ')'` parses with root status `PARSED_COMPLETE`. It is rejected subsequently by the Deterministic Security Policy Layer in Tier 3 DEL, not misclassified as unsupported parser syntax.
* **FR-3.4 (M05 Prompt 4 Dependency Graph & Bounded Range-Nodes):** Prompt 4 ingests AST reference nodes to extract precedents and construct a static Directed Acyclic Graph (DAG). Range references (e.g. `A1:A10000`) must be preserved as bounded range-nodes / hyperedges rather than expanded into thousands of individual cell edges.
* **FR-3.5 (Bounded Static Error Detection):** Static dry-run and DAG analysis detect direct circular cycles (Tarjan SCC), explicit `#REF!` tokens, and spatial boundary collisions. Dynamic runtime errors (e.g. runtime `#VALUE!` from type coercion inside nested functions, dynamic `#DIV/0!`, or spill collisions) **cannot** be statically predicted without full formula recalculation and are explicitly disclaimed.
* **FR-3.6 (Zero Runtime Formula Recalculation):** Formula inspection is purely static. In accordance with ADR-003, formula text is written to `<f>` tags and `<calcPr fullCalcOnLoad="1"/>` is set, delegating computation to Excel upon opening.

#### FR-4: Plan Synthesis & Declarative WO-IR Contracts
* **FR-4.1 (Strict Discriminated Operation Primitives):** The Cognitive Orchestrator emits declarative Workbook Operation Intermediate Representation (WO-IR) JSON payloads adhering to JSON Schema 2020-12 with discriminated union schemas and `additionalProperties: false`. Supported primitives are strictly reconciled:
  - `APPEND_ROWS`: Appends records to an existing detected table.
  - `INSERT_COLUMN`: Inserts a new attribute or formula column.
  - `SET_CELL_VALUE`: Sets a literal scalar value at a coordinate.
  - `SET_CELL_FORMULA`: Inserts a validated formula at a coordinate.
  - `BATCH_SET_FORMULA`: Applies a formula template across a range.
  - `APPLY_STYLE`: Applies styling from a source cell or style rule.
  - `CREATE_SHEET`: Allocates a new worksheet (Profile 3 / Generative only).
* **FR-4.2 (Operation-Specific Validation):** Each primitive enforces strict operation-specific required properties and rejects unexpected fields. Specifically, `CREATE_SHEET` requires only `op_id`, `primitive`, and `sheet_name`, rejecting irrelevant cell or range coordinates.
* **FR-4.3 (Downstream Integration Contract / M01 Adapter):** Defines a proposed M01 adapter contract converting discovered metadata into canonical `DiscoveryManifest` structures for downstream consolidation planning.

#### FR-5: Deterministic Execution, Durability & Rollback
* **FR-5.1 (Execution Layer Architecture):** The Deterministic Execution Layer (DEL) is a sandboxed Python execution engine with targeted Rust extensions where specified; it is not an arbitrary fully compiled binary.
* **FR-5.2 (COR-01 Reconciled Durability Sequence):** Durable transaction intent must strictly precede file mutation. Durability follows the authoritative COR-01 sequence:
  1. *Establish Pre-State Backup:* Create pre-state backup snapshot (`.bak`) of target workbook on local filesystem.
  2. *Persist and Flush Durable WAL Intent:* Append `INTENT_RECORDED` to the WAL log and flush to disk.
  3. *Write Staged Replacement:* Write staged replacement workbook copy to `.staging/<session_id>/` on the same filesystem volume.
  4. *Fsync Staged File:* Flush staged file data and metadata via `fsync()`.
  5. *Atomic Replacement:* Execute atomic replacement using `os.replace` on the same volume.
  6. *Parent-Directory Durability Step:* Synchronize parent directory metadata where supported by the operating system. Explicitly note that Windows NTFS does not provide POSIX directory `fsync()`, and NTFS journal persistence does not provide an equivalent guaranteed durability primitive for immediate directory entry synchronization. On Windows NTFS, directory entry durability remains subject to OS filesystem metadata caching and lazy flushes, presenting an explicit platform durability limitation during sudden host power loss or crash immediately following atomic replacement (staged file content is durable, but directory entry pointer updates may lag).
  7. *Commit WAL:* Mark transaction as `COMMITTED` in the WAL ledger.
* **FR-5.3 (Three-Tier Recovery Engine):**
  - *Tier A (Exact Snapshot Restoration):* Atomic `.bak` swap provides exact restoration when backup integrity is verified and restore succeeds on local NTFS under tested conditions.
  - *Tier B (WAL In-Session Rollback):* Forward and reverse delta patches logged for transactional undo/redo within the active session.
  - *Tier C (Semantic vs. Bitwise OpenXML Preservation):* Target-specific XML part mutation with schema-conformant semantic preservation, leaving non-targeted package parts (`vbaProject.bin`, drawings, slicers, media, themes, unedited sheets) byte-for-byte untouched under experimentally verified local NTFS conditions. Universal bitwise preservation across arbitrary package features is explicitly disclaimed.

#### FR-6: Human-in-the-Loop (HITL) Governance
* **FR-6.1 (Mandatory Escalation Triggers):** Execution must halt and prompt for human approval when:
  - Column inference state is `AMBIGUOUS` (including all-null-marker columns), `INSUFFICIENT_DATA`, or `UNKNOWN`.
  - Heuristic support score $S < 0.70$ or homogeneity $H < 0.80$.
  - Target operation entails destructive overwrite of non-empty cells.
  - ADR-005 boundary collisions occur (appending to plain range with adjacent summary formulas).
  - Any proposed Tier 0 autonomous execution is triggered (governed by Decision 8; blocked pending explicit human sign-off).
* **FR-6.2 (Structured Approval Presentation):** Escalation cards must present natural language rationale, empirical evidence, side-by-side cell diff previews, and alternative interpretations.

---

### 4. Non-Functional Requirements (NFR)

* **NFR-1 (Sampled Event-Driven Memory Guard):** Streaming ingestion memory enforcement is sampled and event-driven via M02 dual-cadence polling:
  - Warning tripwire at exactly **235,000,000 bytes** working set (`WARNING_TRIPWIRE_WORKING_SET_BYTES`).
  - Typed hard-error ceiling at exactly **250,000,000 bytes** working set (`HARD_CEILING_WORKING_SET_BYTES`).
  - Attributable burst allocation delta trigger at **8,000,000 bytes** (`EVENT_DRIVEN_DELTA_THRESHOLD_BYTES = 8_000_000` in `crates/excel_intel_rs/src/memory_guard.rs`).
  Enforcement is an application-level guard evaluated via dual-cadence telemetry (sampled every 1,000 rows or on attributable $\ge 8,000,000\text{ bytes}$ burst deltas); it is not an instantaneous kernel-level RSS cap. Peak RSS guarantees are explicitly disclaimed.
* **NFR-2 (Determinism):** Execution of an identical WO-IR package against an identical workbook state must yield byte-for-byte identical output for targeted XML parts.
* **NFR-3 (Declarative Execution Isolation):** The cognitive tier must be isolated from file write operations. All mutations occur via the deterministic execution pipeline. Tier 3 outbound network policy is governed as an open decision (Decision 7).
* **NFR-4 (Restored PROTOCOL-QA-01 Statistical Certification):** Release certification must satisfy the approved PROTOCOL-QA-01 standard:
  - Five defect categories evaluated across explicit structural units.
  - Minimum sample size: $N_{\text{pos}} = 898$ positive defect units per category across at least 1,000 positive-corpus workbooks (`BENCH-AUDIT-EXTENDED`).
  - Negative corpus: Approved 308-workbook clean control corpus ($K_{\text{clean}} \ge 308, N_{\text{neg}} \ge 3,080$).
  - Mandatory workbook-level cluster-aware inference (Cluster Bootstrap $B \ge 2,000$, GEE, or GLMM with design effect $DEFF = 1.60, \text{ICC} = 0.15$).
  - Acceptance criterion: One-sided 95% sensitivity Lower Confidence Bound $\text{LCB}_{95\%, 1\text{-sided}} \ge 98.00\%$ (preliminary effective-sample-size planning threshold $\ge 889 / 898$ detections).
