# Autonomous Excel Intelligence Platform
## Consolidated Requirements Specification — V1.2 Baseline (Profile 1: Consolidation)

**Document Type:** Consolidation Capability Requirements Specification  
**Baseline Version:** V1.2-Reconciled-v2.6-Context  
**Baseline Status:** Approved Reference Baseline for Capability Profile 1 (Multi-Workbook Consolidation)  
**Implementation Status:** Strictly Not Authorized (Design & Governance Phase)  
**Authority & Lineage Bridge:**
- This document represents the approved baseline for **Capability Profile 1 (Multi-Workbook Data Consolidation)** as established in the V1.2 consolidation requirements consolidation.
- It supersedes historical V1.0 and V1.1 drafts for consolidation-specific behavior.
- The overarching platform charter is defined in [`PRODUCT_REQUIREMENTS_BASELINE.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/PRODUCT_REQUIREMENTS_BASELINE.md) (v2.6), which integrates these Profile 1 requirements into the universal, domain-agnostic platform architecture alongside shared core discovery and future operational profiles.
- Formal platform-wide supersession of all standalone drafts occurs upon project-owner sign-off on PDR-01.

---

## 1. Core Product Objective

The platform is an enterprise-grade, domain-agnostic **Autonomous Multi-Workbook Data Consolidation Engine** (operating as Capability Profile 1 of the Universal Platform).

### 1.1 The Operational Workflow
In a recurring operational period (e.g., monthly business cycle):
1. **One Existing Master Workbook**: Maintained for the period, containing an existing structure, headers, formulas, and baseline data.
2. **Multiple Source Workbooks**: Provided by different users, departments, or external systems (target formats: `.xlsx`, `.xlsm`, and planned read-only `.xlsb` pending EXP-05 empirical verification).
3. **Structural Diversity**: Source workbooks may have completely different layouts, sheet names, column orders, header vocabularies, formatting, and granularity.
4. **Dynamic Discovery**: The system independently inspects the Master Workbook and all source workbooks dynamically without prior assumptions.
5. **Semantic Mapping**: Inactive of pre-baked templates, the system infers semantic relationships between source fields and existing Master fields.
6. **Record Identification & Duplicate Detection**: For every incoming record, the system evaluates contextual evidence against existing Master records.
7. **Selective Transfer**: Confirmed new records are prepared for insertion into existing Master destinations; confirmed duplicate records are skipped.
8. **Enrichment & Overwrite Controls**: Records matching existing Master rows that have missing or blank fields require explicit human authorization before updating.
9. **Zero Redesign**: The system strictly populates existing Master structures. It does not redesign the Master Workbook, nor does it independently create worksheets, business tables, or business columns.

---

## 2. Inviolable Non-Negotiable Requirements

1. **Zero Domain-Specific Hardcoding**: No hardcoded business logic, industry rules, sheet names, column headers, or domain vocabularies.
2. **Zero Fixed Mapping Templates**: No fixed or predefined column/index mapping tables between sources and Master.
3. **Zero Source Standardization Prerequisite**: Source files are not required to follow any uniform template or naming convention.
4. **No Structural Identity Assumption**: Never assume source workbooks share layout or structure with each other or the Master.
5. **No Unauthorized Structural Creation**: Never independently create new worksheets, business tables, or business columns in the Master.
6. **Zero Silent Data Loss or Overwriting**: Populated cells, unmapped source fields, or conflicting records must never be silently discarded or overwritten.
7. **No Unsupported Identity Assumptions**: Record matching must be backed by contextual and semantic evidence, never arbitrary guesses.
8. **Strict Air-Gap Workbook Isolation**: LLMs and cognitive agents are strictly prohibited from directly reading file handles or writing mutations to workbook files. Note: while air-gapping eliminates LLM script generation hazards, the underlying Deterministic Execution Layer, XML parsers, and host environment remain subject to standard software security controls and sandboxing.
9. **Deterministic Validation Gate**: Every write must be validated by a deterministic execution layer against a declarative consolidation plan before commit.
10. **Preservation of Non-Targeted Content**: Formulas, calculated columns, formatting, and unmanaged sheet regions must be protected within the verified compatibility scope.

---

## 3. Functional Requirements

### FR-01: Multiple Source Workbook Ingestion & Provenance
* **FR-01.1**: The system must accept multiple Excel workbooks (`.xlsx`, `.xlsm`, and planned read-only `.xlsb` pending EXP-05 verification) in a single consolidation session.
* **FR-01.2**: Each source workbook must be inspected independently to discover worksheets, tabular blocks, headers, and data types.
* **FR-01.3**: The system must detect irregular layouts, including merged cells, nested headers, and multiple tables per sheet.
* **FR-01.4**: Full source provenance must be maintained for every discovered record (originating file name, SHA-256 hash, sheet name, row/col coordinates).

### FR-02: Existing Master Workbook Discovery
* **FR-02.1**: The system must inspect the existing Master Workbook prior to proposing or planning any consolidation operation.
* **FR-02.2**: The discovery engine must identify existing worksheets, data tables, list ranges, header labels, data types, summary rows, and existing records.
* **FR-02.3**: The system must identify formula columns, calculated fields, and dependencies to ensure formula regions are quarantined from raw data insertion. Formula dependency analysis guarantees are restricted to statically resolvable references; volatile or dynamic references (`INDIRECT`, `OFFSET`, dynamic array spills) must be quarantined.
* **FR-02.4**: The system must determine available contiguous insertion regions (e.g., next available empty row within an existing table or data block).

### FR-03: Dynamic Source-to-Master Semantic Mapping
* **FR-03.1**: The system must deduce field correspondence between each source structure and the existing Master structure using multi-modal evidence (headers, distributions, types, samples, context).
* **FR-03.2**: Mapping must never rely exclusively on exact header string matching or positional indices.
* **FR-03.3**: Source fields that lack an identifiable destination in the Master must be explicitly flagged in the audit report rather than discarded.

### FR-04: Evidence-Based Record Identification and Duplicate Detection
* **FR-04.1**: For every incoming source record, the system must perform an evidence-based comparison against existing Master records.
* **FR-04.2**: The system must not rely on a universally hardcoded primary key; it must dynamically identify candidate identifying keys or contextual composites based on data distribution and semantics.
* **FR-04.3**: Record matching actions must follow strict disposition rules:
  - **Confidently Existing Record**: Skip insertion; log duplicate evidence and source provenance.
  - **Confidently New Record**: Prepare record for insertion into the target Master destination.
  - **Uncertain / Probable Match**: Halt automatic disposition; flag for Human-in-the-Loop (HITL) review.
  - **Conflicting Record**: Flag discrepancies (e.g., matching primary attributes but divergent non-key attributes) for user adjudication.
  - **Insufficient Identifying Evidence**: Do not insert automatically; present record and ambiguity to user.
* **FR-04.4**: All match dispositions must retain their explanatory reasoning, matching scores, and evaluated field sets.

### FR-05: Strict Confinement to Existing Master Structure
* **FR-05.1**: Consolidation is strictly confined to populating the existing Master Workbook layout.
* **FR-05.2**: The system is prohibited from independently:
  - Creating new worksheets or cloning tabs.
  - Creating new business tables or side-by-side tables.
  - Appending new business columns to existing tables.
  - Inventing business formulas or altering calculation logic.
* **FR-05.3**: If source records contain data that cannot fit into the existing Master structure, the system must report structural overflow and request human instructions.

### FR-06: Data Transfer and Consolidation
* **FR-06.1**: For validated new records, values must be mapped to the exact corresponding destination column coordinates.
* **FR-06.2**: Records must be appended to the appropriate existing table or data block without corrupting adjacent data, formulas, or summary blocks.
* **FR-06.3**: When inserting records into an Excel structured table (`ListObject`), the table boundary must be deterministically expanded to encompass the new rows.
* **FR-06.4**: New cells must inherit existing column formatting, number formats, and styling from adjacent precedent rows.

### FR-07: Existing Data, Formula, and Structure Protection
* **FR-07.1**: The system must explicitly differentiate between user-entered literals, headers, summary aggregations, and formulas.
* **FR-07.2**: Under no circumstances may an existing formula be overwritten with a literal value.
* **FR-07.3**: Formula propagation (e.g., copying a calculated column formula downward into a newly appended row) is permitted only when replicating validated, existing Master formula logic.

### FR-08: Uncertainty, Ambiguity, and Human Approval Gates
* **FR-08.1**: Execution must halt and await user confirmation whenever:
  - Source-to-Master column mapping is ambiguous or has multiple viable destinations.
  - Record identity or duplicate status is uncertain.
  - Mandatory destination fields cannot be populated reliably from source data.
  - A proposed operation would modify or overwrite any populated cell.
  - Master structure limitations prevent complete record transfer.
* **FR-08.2**: The approval interface must present:
  - Plain-language explanation of the ambiguity.
  - Supporting empirical evidence and alternative interpretations.
  - Visual before/after diff of affected rows and cells.
  - Explicit action options (Approve, Reject, Remap, Skip).

### FR-09: Existing Records with Blank Fields (Enrichment Approval Protocol)
* **FR-09.1**: When an incoming source record matches an existing Master record, but specific fields in the Master record are blank while the source record contains values:
  1. The system **must not** automatically fill those blank fields.
  2. The system must generate a structured missing-field enrichment proposal detailing the record identity, target blank fields, and proposed source values.
  3. The system must explicitly ask the user whether each proposed blank-field update should be executed.
  4. Only upon receiving explicit user approval may the system prepare and execute the enrichment operation.
  5. If the user rejects the proposal, the update must be skipped and the existing Master record preserved unchanged.
  6. If the user provides no response (timeout or cancellation), the proposed update must not be executed.
* **FR-09.2**: Explicit approval for one record's blank-field enrichment must never be interpreted as blanket approval for other records or future sessions.

### FR-10: Populated Destination Cell Overwrite Protection
* **FR-10.1**: Overwriting any non-blank destination cell requires explicit record-level human approval.
* **FR-10.2**: In the absence of explicit approval, existing values are inviolable.

### FR-11: Dry Run and Consolidation Plan Synthesis
* **FR-11.1**: The cognitive layer must produce a declarative, strongly-typed Consolidation Plan.
* **FR-11.2**: The plan must enumerate:
  - Source workbooks and specific row references.
  - Target Master workbook, worksheet, table, and row/column coordinates.
  - Explicit field-level value mappings.
  - Duplicate analysis results and classifications (Insert New, Skip Duplicate, Enrich Blank, Flag Review).
  - Human approval tokens associated with approved escalations.
  - Pre-execution assertions and post-execution invariants.
* **FR-11.3**: The Deterministic Execution Layer (DEL) must validate the plan against an in-memory shadow model before modifying disk storage.

### FR-12: Post-Execution Verification
* **FR-12.1**: Immediately following execution, the system must run automated verification checks:
  - All approved new records are present at expected coordinates.
  - Skipped duplicate records were not inserted.
  - Approved blank-field enrichments match approved values.
  - Untouched cells, formulas, summaries, and unmanaged tabs match pre-execution hashes.
  - Structured tables and formula spans expanded correctly without introducing formula syntax errors (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, `#N/A`).
* **FR-12.2**: A comprehensive Consolidation Execution Report must be rendered for the user.

### FR-13: Audit, Provenance, and Recovery
* **FR-13.1**: Every consolidation session must produce an append-only, tamper-evident audit trail capturing:
  - Hashes and file identities of Master and all source workbooks.
  - All semantic mapping decisions and duplicate evaluation evidence.
  - All HITL interactions, approvals, and rejections.
  - The complete executed Consolidation Plan.
  - Pre-execution backup and inverse deltas for point-in-time rollback.
* **FR-13.2**: The system must provide a transaction recovery mechanism. On local single-volume filesystems, this combines pre-execution backup persistence, staged writes, explicit file and parent directory flushing (`fsync`/`FlushFileBuffers`), atomic namespace replacement (`os.replace`), and write-ahead logging (WAL) sequencing. Recovery from unhandled aborts restores the pre-execution backup image. Network shares (SMB) and cloud sync folders (OneDrive) are subject to lock contention and sync latency and remain unverified design targets pending EXP-06.

### FR-14: Monthly Reusability & Context Evolution
* **FR-14.1**: The system must support recurring monthly cycles where source workbook configurations vary.
* **FR-14.2**: The system must perform fresh inspection of the current Master Workbook each session.
* **FR-14.3**: Historical mapping decisions may be utilized as contextual evidence to accelerate inference, but must never bypass dynamic validation or structural verification.

---

## 4. Non-Functional Requirements

### NFR-01: Determinism & Idempotency
* **NFR-01.1**: Applying an approved Consolidation Plan to a given Master state must be 100% deterministic and reproducible.
* **NFR-01.2**: Reprocessing the same source files against the resulting Master Workbook must detect all previously imported records as duplicates and result in zero new insertions (idempotency).

### NFR-02: Security & Sandboxing
* **NFR-02.1**: The Deterministic Execution Layer must operate in a restricted process sandbox with zero outbound network egress.
* **NFR-02.2**: Cell contents must be treated strictly as untrusted data; formulas, external link commands (`=cmd|...`, DDE), and web queries (`WEBSERVICE`) must be neutralized.
* **NFR-02.3**: Embedded VBA macros in `.xlsm` workbooks must be quarantined and preserved as opaque binary streams without execution. The platform does NOT execute macros under any circumstances.
* **NFR-02.4**: Threat Model Scope: Air-gapping isolates the cognitive LLM from host file handles and shell commands, preventing malicious prompt-driven code generation. However, security against parser memory vulnerabilities, XML entity expansion (XXE/billion laughs), decompression bombs, and third-party library exploits requires strict input sanitization, safe parsers (`defusedxml`), and OS-level containment.

### NFR-03: Performance & Resource Footprint
* **NFR-03.1 (Multi-Workbook Profiling Latency)**: Ingestion, profiling, and mapping across 5 source workbooks (up to 20,000 rows each) and a Master workbook must complete initial profiling within 60 seconds (verified via `BENCH-PERF-MULTI-5`).
* **NFR-03.2 (Relative Memory Overhead)**: Peak memory utilization during multi-workbook consolidation processing must not exceed 4x the uncompressed OpenXML sheet size.
* **NFR-03.3 (Complementary Streaming Scalability)**: In addition to the multi-workbook profiling constraints above, single-sheet streaming parsing on massive datasets must adhere to REQ-20b (100,000 rows parsed with peak process RSS < 250 MB and latency < 15 seconds, verified via `BENCH-SCALE-100K`). Both requirements are complementary: NFR-03.1/NFR-03.2 govern the end-to-end multi-workbook consolidation lifecycle, while REQ-20b governs low-level single-sheet streaming engine efficiency.

---

## 5. Governance Relationship to Universal Platform Baseline
1. This V1.2 specification remains the authoritative functional definition for **Capability Profile 1 (Consolidation)**.
2. The broader product requirements, architectural invariants, and multi-profile evolution are governed by [`PRODUCT_REQUIREMENTS_BASELINE.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/PRODUCT_REQUIREMENTS_BASELINE.md) (v2.6).
3. Any future modifications to Profile 1 consolidation requirements must update both this document and the unified platform baseline to preserve cross-specification consistency.
