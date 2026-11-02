# Autonomous Excel Intelligence Platform
## System Architecture Specification — V1.2 Baseline (SYSTEM_ARCHITECTURE.md)

**Status:** Architecture Design Baseline  
**Implementation Status:** Strictly Not Authorized (Design Phase Only)  
**Governing Standard:** Section 8 & Section 9 Development-Agent Governance

---

## 1. Architectural Overview & Design Philosophy

The **Autonomous Excel Intelligence Platform** implements a decoupled four-subsystem architecture designed to achieve autonomous, domain-agnostic spreadsheet data consolidation into an existing Master Workbook while enforcing absolute determinism, zero data loss, and an inviolable air-gap between cognitive deliberations and physical file persistence.

```
+===================================================================================+
|                                    USER INTERFACE                                 |
|            (Workbook Selection, Mapping Review, HITL Approvals, Audit)            |
+===================================================================================+
                                         |
                                         v
+===================================================================================+
|                     SUBSYSTEM 1: INSPECTION & PROFILING SERVICE                   |
|                                (DETERMINISTIC)                                    |
|   - OpenXML / Binary Reader                 - Bounding Box & Table Segmenter      |
|   - Sparse Cell Coordinate AST              - Data Type & Distribution Profiler   |
|   - Formula & Protected Range Cataloger     - Source Provenance Extractor         |
+===================================================================================+
                                         |
                  [Extracted Topology, Statistics & Sample Evidence]
                                         |
                                         v
+===================================================================================+
|                  SUBSYSTEM 2: CONSOLIDATION REASONING ENGINE                      |
|                                (LLM-ASSISTED)                                     |
|   - Dynamic Semantic Field Mapper           - Candidate Key Discoverer            |
|   - Contextual Record Identity Evaluator    - Duplicate Assessment Classifier     |
|   - Blank-Field Enrichment Detector         - Unmapped Source Data Sentinel       |
+===================================================================================+
                                         |
                          [Proposed Consolidation Package]
                                         |
                                         v
+===================================================================================+
|                   SUBSYSTEM 3: HITL & APPROVAL COORDINATOR                        |
|                                (DETERMINISTIC)                                    |
|   - Risk-Gated Escalation Evaluator         - Structured Approval Presentation    |
|   - Scoped HMAC Approval Token Signer       - Non-Response / Rejection Enforcer   |
+===================================================================================+
                                         |
                       [Fully Authorized C-Op Plan Package]
                                         |
                                         v
+===================================================================================+
|             SUBSYSTEM 4: DETERMINISTIC EXECUTION & VERIFICATION LAYER             |
|                                (AIR-GAPPED)                                       |
|   - C-Op Contract Schema Validator          - Pre-Condition State Checker         |
|   - In-Memory Shadow Dry Run                - Atomic OpenXML Mutation Engine      |
|   - Table Boundary Expander & Styler        - Write-Ahead Log (WAL) & Rollback    |
|   - Post-Flight Invariant Verifier          - Audit Ledger Generator              |
+===================================================================================+
                                         |
                                         v
                        [Verified Consolidated Master Workbook]
```

---

## 2. Detailed Subsystem Specifications

### 2.1 Subsystem 1: Inspection & Profiling Service (Deterministic)
* **Exact Responsibilities**:
  - Ingest raw Master and source workbooks (`.xlsx`, `.xlsm`, `.xlsb` within compatibility scope).
  - Extract sparse coordinate cell models, header hierarchies, cell data types, number formats, and styling signatures.
  - Dynamically segment discrete tabular blocks, summary rows, and unmanaged worksheet regions using spatial bounding boxes.
  - Catalog existing formulas, calculate cell dependency graphs, and identify protected calculation zones.
  - Attach immutable source provenance (file hash, sheet, row/col coordinates) to every extracted record.
* **Inputs & Outputs**:
  - *Inputs*: File paths to Master and $N$ Source workbooks.
  - *Outputs*: Strongly-typed `MasterStructureManifest` and `SourceInspectionManifest` objects.
* **Internal Components**:
  - `OpenXmlStreamReader`: Low-level streaming parser extracting sheet parts without COM automation.
  - `SpatialBoundingBoxSegmenter`: 2D spatial clustering algorithm isolating contiguous data regions.
  - `TypeDistributionProfiler`: Statistical regex and distribution analyzer detecting dates, currencies, codes, and text.
  - `FormulaDependencyCataloger`: Lexer and AST parser mapping formula locations and precedents.
* **Public Interfaces**:
  - `inspect_master(file_path: Path) -> MasterStructureManifest`
  - `inspect_source(file_path: Path) -> SourceInspectionManifest`
* **Error Handling**: Corrupted archives, unreadable formats, or password-protected workbooks trigger immediate `InspectionAbortedError` without crashing the runtime.
* **Dependencies**: Python standard library, `defusedxml`, `openpyxl` (read-only mode), `et_xmlfile`.
* **Security Boundary**: Zero code execution; macro streams are bypassed and quarantined.

---

### 2.2 Subsystem 2: Consolidation Reasoning Engine (LLM-Assisted)
* **Exact Responsibilities**:
  - Dynamically infer semantic relationships between source fields and existing Master columns without hardcoded templates.
  - Synthesize contextual evidence (value distributions, candidate unique keys) to classify incoming records into: Confident New, Confident Duplicate, Blank-Field Enrichment Candidate, or Ambiguous/Conflicting.
  - Detect cross-source duplicate collisions and attribute discrepancies.
  - Formulate structured proposals for field mappings and record actions.
* **Inputs & Outputs**:
  - *Inputs*: `MasterStructureManifest`, `SourceInspectionManifest` (compacted topological summaries + representative samples).
  - *Outputs*: Candidate C-Op Proposal Package (`PROPOSED` state).
* **Internal Components**:
  - `SemanticFieldMapper`: Multi-shot reasoning agent pairing source headers with Master fields.
  - `CandidateKeyDiscoverer`: Heuristic + semantic engine identifying identifying field composites.
  - `RecordIdentityEvaluator`: Contextual comparison engine matching source rows against Master records.
  - `EnrichmentDetector`: Identifies existing Master records with blank destination cells where source records contain values.
  - `ConflictSentinel`: Detects inter-source value divergence for identical entity keys.
* **Public Interfaces**:
  - `propose_consolidation(master_manifest, source_manifests, user_hints) -> ConsolidationProposal`
* **Error Handling**: Malformed LLM outputs trigger automated schema repair or retry; unresolved schema violations escalate to human.
* **Dependencies**: Model-agnostic LLM interface (JSON mode enabled).
* **Security Boundary**: Strict Air-Gap. Zero filesystem write handles. Evaluates extracted metadata only.

---

### 2.3 Subsystem 3: HITL & Approval Coordinator (Deterministic)
* **Exact Responsibilities**:
  - Enforce mandatory approval gates for:
    1. Blank-field enrichments (FR-09 mandatory rule).
    2. Populated cell overwrites (FR-10 mandatory rule).
    3. Ambiguous duplicate matches or field mappings.
    4. Cross-source value conflicts.
  - Present structured, explainable decision requests to the user with empirical evidence and side-by-side diff previews.
  - Collect explicit user choices and generate cryptographically signed, record-scoped `ApprovalToken` objects.
  - Enforce non-response and rejection policies: unapproved proposals are stripped from executable plans.
* **Inputs & Outputs**:
  - *Inputs*: Candidate C-Op Proposal Package.
  - *Outputs*: Authorized C-Op Package (`AUTHORIZED` state) with valid approval tokens.
* **Internal Components**:
  - `RiskEscalationGate`: Rules engine identifying actions requiring explicit sign-off.
  - `ApprovalPresentationFormatter`: Renders before/after diffs, evidence rationales, and action cards.
  - `ScopedTokenSigner`: Generates HMAC-SHA256 signatures binding approval strictly to `{session_id, op_id, record_key, target_cells, approved_values}`.
  - `DecisionLedger`: Records all human inputs, timestamps, rejections, and timeouts.
* **Public Interfaces**:
  - `evaluate_gates(proposal: ConsolidationProposal) -> ReviewManifest`
  - `authorize_operations(proposal, approvals: List[HumanDecision]) -> AuthorizedCOpPackage`
* **Error Handling**: User timeout or cancellation automatically marks pending proposals as `REJECTED_TIMEOUT`.
* **Dependencies**: Python standard library (`hmac`, `hashlib`, `secrets`).
* **Security Boundary**: Approval tokens are non-transferable and cannot be reused across records or sessions.

---

### 2.4 Subsystem 4: Deterministic Execution & Verification Layer (Air-Gapped)
* **Exact Responsibilities**:
  - Validate Authorized C-Op Packages against the formal C-Op JSON Schema Draft 2020-12.
  - Verify HMAC approval signatures on every restricted operation (enrichment/overwrite).
  - Execute an in-memory shadow dry run to test pre-conditions, formula dependencies, and spatial non-overlap.
  - Perform atomic OpenXML row appends, table boundary expansions (`ListObject`), and approved field writes.
  - Propagate existing table formulas into appended rows deterministically.
  - Maintain a Write-Ahead Log (WAL) with forward and reverse deltas for point-in-time rollback.
  - Conduct post-flight verification, confirming target coordinates, untouched regions, and formula integrity.
  - Commit final audit ledger.
* **Inputs & Outputs**:
  - *Inputs*: Authorized C-Op Package, Master Workbook file handle.
  - *Outputs*: Verified Master Workbook, Execution Verification Report, Audit Trail.
* **Internal Components**:
  - `ContractSchemaValidator`: Strict JSON schema and token integrity validator.
  - `ShadowDryRunEngine`: In-memory simulator evaluating pre-conditions and cell collision boundaries.
  - `AtomicOpenXmlMutator`: Deterministic writer modifying target sheet XML and table definitions.
  - `FormulaPropagator`: Clones existing table column formulas downward into new rows without inventing logic.
  - `WALRollbackEngine`: Writes inverse patches and restores pre-execution file state on any invariant breach.
  - `PostFlightVerifier`: Re-reads output workbook to verify cell hashes, coordinate targets, and formula health.
* **Public Interfaces**:
  - `validate_and_execute(package: AuthorizedCOpPackage, master_path: Path) -> ExecutionResult`
  - `rollback_transaction(session_id: str, master_path: Path) -> RollbackResult`
* **Error Handling**: Any failure during execution or post-flight verification triggers instant atomic rollback to the pre-state hash.
* **Dependencies**: `openpyxl` / `defusedxml`, `et_xmlfile`, standard library. Zero outbound network egress.
* **Security Boundary**: Completely isolated execution sandbox.

---

## 3. Technology Architecture Decisions (ADRs)

### ADR-01: Low-Level Spreadsheet Manipulation Engine Selection
* **Context**: Need a fast, secure, cross-platform library to parse and write `.xlsx` files while maintaining OpenXML part preservation.
* **Options Considered**:
  - *Option A: Enhanced Python OpenXML (`openpyxl` + `defusedxml`)*: Pure Python, zero native compilation, fully sandboxable, handles tables and formulas well.
  - *Option B: Rust Core via PyO3 (`calamine` + `quick-xml`)*: Extremely fast, but requires custom OpenXML table expansion and style serialization logic.
  - *Option C: Excel COM Automation (`pywin32`)*: Windows-only, requires Excel installation, slow, non-headless, prone to hung processes.
* **Trade-offs**: Option A is robust, immediately portable, and well-understood; Option B offers 10x raw speed on 100k+ row sheets but requires high custom C/Rust maintenance. Option C violates server/sandbox headless invariants.
* **Decision**: **Option A (Enhanced Python OpenXML)** for V1.2. Implement read-only streaming for profiling and selective DOM manipulation for execution.
* **Required Experiment**: Benchmark table append and memory consumption on a 50,000-row Master table.

### ADR-02: OpenXML Parsing & Writing Strategy
* **Context**: Loading entire multi-megabyte OpenXML trees into memory can exceed memory limits and reorders XML attributes on save.
* **Decision**: Two-Phase Access Model:
  1. *Inspection Phase*: Read-only streaming mode (`read_only=True`) extracting only coordinate values, formulas, and headers into a lightweight sparse coordinate model.
  2. *Execution Phase*: Targeted DOM mode loading only the target worksheet and `table1.xml` definition. Non-targeted worksheets and media parts are streamed through unmodified.

### ADR-03: Formula Parsing & Dependency Analysis
* **Context**: The engine must identify formula cells, detect calculated columns, and prevent overwriting formulas with raw values without executing untrusted code.
* **Decision**: Implement an EBNF-based formula lexer/parser in Python. Extract cell coordinates referenced by formulas to construct an in-memory directed acyclic dependency graph (precedent/dependent tracking).

### ADR-04: Formula Recalculation Strategy
* **Context**: When new rows are appended to an existing Master table, how should calculated column values be computed?
* **Decision**: **Flag-Based Deferred Recalculation (`fullCalcOnLoad`)**:
  - The engine copies the validated formula string into the new row's formula tag (`<f>`).
  - The workbook calculation property `<calcPr fullCalcOnLoad="1" forceFullCalc="1"/>` is set in OpenXML.
  - True formula recalculation is deferred to Microsoft Excel upon opening.
  - *Rationale*: Re-implementing Microsoft Excel's full calculation engine in Python introduces unavoidable calculation discrepancies.

### ADR-05: Duplicate Detection Architecture
* **Context**: Incoming source records must be matched against existing Master records without hardcoding business keys.
* **Decision**: **Two-Stage Hybrid Deduplication Pipeline**:
  - *Stage 1 (Deterministic Candidate Pruning)*: The candidate key discoverer identifies high-cardinality non-null field combinations. A fast hash index flags exact key matches as duplicates and selects top candidate matches.
  - *Stage 2 (LLM Contextual Evaluation)*: For records with partial key matches or conflicting non-key attributes, the LLM evaluates row evidence and produces a match confidence classification (`CONFIDENT_NEW`, `CONFIDENT_DUPLICATE`, `ENRICHMENT_CANDIDATE`, `AMBIGUOUS`).

### ADR-06: LLM Provider Abstraction
* **Context**: The platform must remain decoupled from any single proprietary LLM provider.
* **Decision**: Build an abstract `LLMProviderInterface` with strict JSON-schema enforcement. The adapter validates that model responses conform to C-Op schemas before returning data to Subsystem 2.

### ADR-07: Intermediate Storage & Transaction Strategy
* **Context**: Modifications to workbooks must be atomic and reversible.
* **Decision**: **Ephemeral Staging with Write-Ahead Logging (WAL)**:
  - Workbooks are copied to an isolated temporary workspace (`.staging/session_<uuid>/`).
  - Mutations generate forward and reverse cell deltas written to an append-only WAL file.
  - On commit, the staged file replaces the target file via atomic rename (`os.replace`).

### ADR-08: Rollback Implementation
* **Context**: If execution or post-flight verification fails, the Master Workbook must be restored with 100% integrity.
* **Decision**: **Two-Tier Rollback Mechanism**:
  - *Primary (In-Flight)*: Pre-execution Master backup copy is retained in the staging directory. Any failure immediately restores the original file.
  - *Secondary (Post-Flight Undo)*: If user requests a rollback in a subsequent session, the reverse delta from the WAL is applied.

### ADR-09: Audit Storage
* **Context**: Compliance requires full provenance tracking for every cell write.
* **Decision**: Append-only JSON Lines (`audit_trail.jsonl`) accompanied by a SHA-256 hash chain where each entry includes the hash of the preceding entry.

### ADR-10: Scoped Approval Token Security
* **Context**: Approval of one record or field must never authorize unrelated operations or bypass safety gates.
* **Decision**: **Cryptographic HMAC-SHA256 Scoped Tokens**:
  - `token = HMAC_SHA256(secret_key, session_id + op_id + record_id + target_coords + proposed_values)`
  - Subsystem 4 recomputes the HMAC before committing any enrichment or overwrite. Mismatched parameters reject the write.

### ADR-11: Local Deployment & Runtime Architecture
* **Context**: Operating environment must support secure enterprise execution.
* **Decision**: Self-contained local Python application (CLI / Desktop Service) running on Windows/Linux with zero external server dependencies, operating entirely within local filesystem boundaries.
