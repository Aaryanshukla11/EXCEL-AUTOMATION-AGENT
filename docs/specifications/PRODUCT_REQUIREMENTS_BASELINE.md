# Autonomous Excel Intelligence Platform
## Product Requirements Baseline — Universal Platform Specification

**Document Type:** Formal Product Requirements Baseline  
**Document Version:** 2.6-Approved-Baseline  
**Document Status:** Baseline Approved via PDR-01 by Project Owner (2026-11-21)  
**Governance Gate Status:**  
- **Gate 1 (Product Decisions PDR-01 to PDR-06):** APPROVED (2026-11-21)  
- **Gate 2 (Phase 0 Technical Experiments):** AUTHORIZED (2026-11-21)  
- **Gate 3 (Production Implementation):** STRICTLY NOT AUTHORIZED  
**Governance & Authority Bridge:**
- This document establishes the unified product requirements baseline for the **Universal, Domain-Agnostic Excel Intelligence Platform**, defining its foundational core and extensible capability profiles (Consolidation, Formula Intelligence, Generative Reporting).
- It formally incorporates the consolidation-specific requirements established in [`REQUIREMENTS_SPECIFICATION.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/REQUIREMENTS_SPECIFICATION.md) (V1.2 Approved Reference Baseline for Capability Profile 1) without discarding, weakening, or invalidating them.
- Lineage & Supersession Chain: Historical V1.0/V1.1 drafts $\rightarrow$ V1.2 Reference Specification (Profile 1 Consolidation Baseline) $\rightarrow$ Unified Platform Baseline v2.6 (Core + Multi-Profile Architecture). Platform-wide unification becomes formally authoritative upon project-owner sign-off on PDR-01.

---

## 1. Executive Summary & Universal Mission

The **Autonomous Excel Intelligence Platform** is a universal, domain-agnostic cognitive system designed to dynamically discover, understand, analyze, transform, consolidate, and synthesize operations on arbitrary Microsoft Excel workbooks without hardcoded business rules, domain templates, fixed column coordinates, or fragile human assumptions.

### 1.1 Scope Architecture: Core Foundation and Operational Profiles
Consolidation is an **initial operational capability profile (Profile 1)**, not the permanent product boundary. The platform is architected around a shared **Universal Discovery & Execution Foundation** supporting pluggable operational profiles:
- **Foundational Core:** Universal ingestion of `.xlsx`, `.xlsm`, and planned read-only `.xlsb` (pending EXP-05 empirical verification); topological segmentation; semantic typing; formula AST dependency modeling; static structural & quality auditing; and air-gapped deterministic mutation.
- **Profile 1 (Release 1.0):** Multi-Workbook Data Consolidation (deduplication, blank enrichment approval, table row append).
- **Profile 2 (Release 2.0):** Formula Intelligence, Advanced Model Auditing & Cross-Sheet Relationships (metric synthesis, XLOOKUP links, model auditing).
- **Profile 3 (Release 3.0):** Generative Reporting, Structural Transformation & Conversational Analytics (summary tab creation, unpivoting, conversational Q&A).

---

## 2. Product Scope & Capability Space

```
+==================================================================================================================================+
|                                              CAPABILITY CLASSIFICATION MATRIX                                                    |
+==================================================================================================================================+
| Capability Domain                       | Implementation Tier       | Target Milestone | Operational Profile                     |
+-----------------------------------------+---------------------------+------------------+-----------------------------------------+
| 1. Workbook Understanding & Discovery   | REQUIRED CORE             | Release 1.0      | Shared Foundational Core                |
|    (.xlsx, .xlsm, planned ro-.xlsb)     |                           |                  | (ro-.xlsb pending EXP-05 verification)  |
| 2. Multi-Workbook Data Consolidation    | INITIAL RELEASE CAPABILITY| Release 1.0      | Profile 1: Consolidation                |
| 3. Data Exploration & Schema Summaries  | INITIAL RELEASE CAPABILITY| Release 1.0      | Profile 1: Consolidation (Read-Only)    |
| 4. Static Structural & Quality Auditing | REQUIRED CORE / INITIAL   | Release 1.0      | Shared Core / Profile 1: Consolidation  |
|    (#REF!, #VALUE!, #DIV/0!, #NAME?,    | RELEASE CAPABILITY        |                  | (Validated via PROTOCOL-QA-01 on        |
|    #N/A, cycles, jagged, unmapped, keys)|                           |                  | BENCH-AUDIT-200 pilot & EXTENDED corpus)|
| 5. Formula Generation & Synthesis       | FUTURE CAPABILITY         | Release 2.0      | Profile 2: Formula Intelligence         |
| 6. Cross-Sheet Relationships & Lookups  | FUTURE CAPABILITY         | Release 2.0      | Profile 2: Formula Intelligence         |
| 7. Advanced Formula Model Auditing      | FUTURE CAPABILITY         | Release 2.0      | Profile 2: Formula Intelligence         |
|    (Orphaned islands, calc chains)      |                           |                  |                                         |
| 8. Summary Generation & Reporting       | FUTURE CAPABILITY         | Release 3.0      | Profile 3: Generative Reporting         |
| 9. Data Transformation & Restructuring  | FUTURE CAPABILITY         | Release 3.0      | Profile 3: Generative Reporting         |
| 10. Structural Modification (Intent-Led)| FUTURE CAPABILITY         | Release 3.0      | Profile 3: Generative Reporting         |
| 11. Macro Execution (.xlsm VBA execution| EXPLICITLY UNSUPPORTED    | N/A              | None (Quarantine & Preserve Binary Only)|
| 12. External Shell / DDE Protocol Calls | EXPLICITLY UNSUPPORTED    | N/A              | None (Blocked as Security Vulnerability)|
+==================================================================================================================================+
```

---

## 3. Universal Invariants vs. Capability-Specific Constraints

### 3.1 Universal Platform Invariants (Inviolable Across All Operations)

* **INV-01 (Zero Domain Assumptions):** No hardcoded business logic, industry rules, sheet names (`Sheet1`, `Summary`), column headers (`Date`, `Amount`), or domain vocabularies.
* **INV-02 (Dynamic Empirical Discovery):** All boundaries, headers, orientations, data types, and relationships must be derived dynamically from workbook evidence.
* **INV-03 (Air-Gap Execution & Security Boundary):** Cognitive models reason strictly over extracted structural and semantic metadata; only the Deterministic Execution Layer (DEL) accesses physical file descriptors. Cognitive models are strictly prohibited from generating executable code or interacting directly with OS processes.
  - *Threat Model Boundary:* The air-gap isolates the LLM from executing shell commands or arbitrary scripts, neutralizing prompt injection leading to code generation. However, the system boundary is not entirely immune to lower-level threats: raw XML parser exploits (XXE, entity bombs), ZIP compression bombs, dependency CVEs, and host execution of preserved VBA macros (if opened externally in desktop Excel) remain potential risks that must be mitigated via `defusedxml`, strict container quotas, and sandboxed process environments.
* **INV-04 (Untrusted Content Boundary):** Workbook cell content is untrusted data. Neutralization of prompt injections, formula injections (`=cmd|...`), and Dynamic Data Exchange (DDE) is mandatory.
* **INV-05 (Formula Dependency & Cycle-Detection Scope):** Static formula dependency DAG construction and circular reference detection are strictly guaranteed for *statically resolvable* formula references (e.g., explicit cell coordinates `A1`, 2D ranges `B2:D10`, cross-sheet coordinates `Sheet2!A1`, structured table references `Table1[Col]`). Formulas containing dynamic, volatile, or runtime-evaluated references (`INDIRECT`, `OFFSET`, dynamic array spills `#`, `EVALUATE`) cannot be statically resolved and must be classified as `UNRESOLVED_DYNAMIC_DEPENDENCY` and quarantined from automatic layout mutation.
* **INV-06 (Format Preservation Dual-Standard):**
  - *Rollback Standard:* Exact bitwise pre-state restoration via pre-execution backup image.
  - *Successful Mutation Standard:* Semantic OpenXML Parity across non-targeted workbook regions (verifying AST nodes, cell values, formulas, styles, comments, drawings, and VBA streams).
* **INV-07 (Deterministic Validation Gate):** Every proposed plan must pass dry-run schema validation and pre-condition checks prior to committing changes to disk.
* **INV-08 (Transactional Recovery & Storage Guarantee Precision):**
  - *Atomic Namespace Replacement vs. Crash Durability:* Standard OS file replacement (`os.replace` on POSIX / Win32 `MoveFileEx`) guarantees atomic directory entry / namespace replacement within a single volume, preventing partial file overwrites in the directory listing. However, `os.replace` alone does NOT provide complete transaction durability or crash recovery.
  - *Full Transaction Protocol Requirements:* Durability and crash-consistent recovery require a multi-step sequence:
    1. Staging write into an isolated temporary directory on the same filesystem volume.
    2. Explicit file flushing and sync to physical media (`flush()` followed by `os.fsync()` on POSIX or `FlushFileBuffers()` on Win32).
    3. Directory metadata durability (`os.fsync()` on the parent directory file descriptor on POSIX; metadata flush on NTFS).
    4. Write-Ahead Logging (WAL) ordering: the intent and WAL commit record must be flushed to disk *prior* to executing the atomic namespace swap.
    5. Pre-state backup image persisted in an isolated staging location prior to commit.
    6. Crash recovery protocol: on startup, the engine scans the WAL to detect interrupted transactions, rolling back to the bitwise backup image if an incomplete swap is detected.
  - *Storage Rigor Classification:*
    - *Local Filesystem:* Atomic namespace swap is an established OS filesystem primitive. The end-to-end multi-step transaction and crash recovery protocol is an architectural design whose integration and power-failure resilience remain subject to empirical verification under EXP-06.
    - *Network Shares (SMB/CIFS) & Cloud-Synchronized Directories (OneDrive/SharePoint):* Lack POSIX/NTFS atomic swap semantics across mount boundaries, experience delayed write-backs, and suffer lock contention from background synchronization daemons. They are classified as **Design Targets / Unverified Hypotheses** pending empirical testing in EXP-06.

### 3.2 Capability-Specific Operational Constraints

#### Profile 1: Multi-Workbook Data Consolidation (Release 1.0)
* **CON-01 (Strict Confinement to Existing Target):** The consolidation engine populates the existing Master Workbook structure only. Automated creation of worksheets, business tables, or business columns is prohibited.
* **CON-02 (Deduplication First):** Confirmed existing Master records must be skipped from insertion.
* **CON-03 (Blank-Field Enrichment Gate - FR-09):** Populating blank cells in an existing Master record requires explicit human approval; never execute automatically.
* **CON-04 (Populated Cell Overwrite Gate - FR-10):** Overwriting any populated cell requires explicit human approval.
* **CON-05 (Multi-Source Co-Provenance & Conflict Adjudication):** Identical new records from multiple sources are inserted once with co-provenance; divergent attribute values halt for human review (DR-A1 / DR-A2).
* **CON-06 (Non-Table Boundary Safety - DR-A3):** If destination is an ordinary data range with summary rows below and zero spare rows, automated row shifting is prohibited; halt and prompt for space or table conversion.
* **CON-07 (Release 1.0 Static Structural & Quality Audit):** Prior to proposing or executing operations, the system must statically audit Master and source workbooks, cataloging five explicit defect categories:
  1. Formula evaluation errors (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, `#N/A`).
  2. Formula circular reference dependency cycles (statically resolvable).
  3. Jagged rows (structural row length variance violating table boundary).
  4. Unmapped source fields (source columns with no destination in target Master).
  5. Candidate key collision anomalies (partial matches or duplicate keys with divergent attributes).
  All discovered defects must be cataloged in the audit manifest and quarantined. Verification is governed by dedicated protocol `PROTOCOL-QA-01` on `BENCH-AUDIT-200` (acceptance gate pilot) and `BENCH-AUDIT-EXTENDED`.

#### Profile 2: Formula Intelligence & Relationships (Release 2.0)
* **FOR-01 (Formula AST Verification):** Synthesized formulas must be parsed into an AST, verified against a safe function whitelist, and checked for circular references.
* **FOR-02 (Non-Destructive Column Allocation):** Injected formula metrics must be placed in validated empty columns or designated calculation zones.
* **FOR-03 (Advanced Model Auditing):** Cross-sheet calculation chain audits, orphaned calculation islands, and column formula consistency.

#### Profile 3: Generative Reporting & Transformation (Release 3.0)
* **GEN-01 (Intent-Authorized Creation):** The platform is authorized to create new worksheets, summary tables, and formula blocks **only when explicitly instructed by user prompt** and confirmed via human approval preview.
* **GEN-02 (Source Data Immobility):** Generative reporting must write to new sheets or empty regions, leaving source data tables completely unaltered.

---

## 4. Technical Boundary Specifications

### 4.1 Storage & Transaction Guarantees by Environment (Rigor Classification)
1. **Local Filesystem (NTFS / APFS / ext4):**
   - *Rigor Classification:* **ESTABLISHED OS PRIMITIVES / INTEGRATION PENDING VERIFICATION (EXP-06)**.
   - *Mechanism:* Staged copy created in `.staging/<session_id>/`; flushed via `fsync()`; parent directory entry synced; atomic namespace replacement executed via `os.replace` within the same volume; WAL ordered and flushed prior to commit. Provides atomic namespace swap and crash recovery upon validation in EXP-06.
2. **Network File Shares (SMB / CIFS / NFS):**
   - *Rigor Classification:* **DESIGN TARGET / UNVERIFIED HYPOTHESIS** (Subject to EXP-06).
   - *Mechanism:* Network file shares may not support atomic rename across mounts or handle concurrent client locking cleanly. Staged write with explicit file locking; stage-copy-swap with exponential backoff on lock contention.
3. **Cloud-Synchronized Directories (OneDrive / SharePoint / Dropbox):**
   - *Rigor Classification:* **DESIGN TARGET / UNVERIFIED HYPOTHESIS** (Subject to EXP-06).
   - *Mechanism:* Cloud sync daemons hold transient read locks on files. Staging in local OS temporary directory outside sync tree; sync-daemon-aware swap with retry and pre-state backup before replacement. Universal sync-safe atomicity is explicitly unverified pending empirical testing in EXP-06.

### 4.2 Scoped HMAC-SHA256 Human Approval Security Specification
To prevent authorization tampering, replay attacks, or scope creep:
* **Token Structure:**
  $$\text{Token} = \text{HMAC-SHA256}(K_{\text{session}}, \text{session\_id} \parallel \text{op\_id} \parallel \text{record\_key} \parallel \text{target\_cell} \parallel \text{approved\_value} \parallel \text{approver\_identity} \parallel \text{timestamp} \parallel \text{nonce})$$
* **Secret Management:** Ephemeral cryptographically secure 256-bit key ($K_{\text{session}}$) generated in memory per session via OS CSPRNG (`secrets.token_bytes(32)`). Never persisted to disk.
* **Approver Identity Binding:** Token binds to `approver_identity` (user ID or session role); cannot be executed by unauthorized roles.
* **Token Expiry (TTL):** Absolute Time-To-Live of 15 minutes. Expired tokens are rejected automatically.
* **Atomic Single-Use Replay Prevention:** In-memory mutex-protected set tracks consumed nonces. Token consumption is an atomic check-and-insert operation. A token presented more than once is rejected immediately.
* **Session Lifecycle & Invalidation:** All tokens issued during a session are instantly invalidated upon session termination, timeout, or explicit addition to an in-memory Revocation Blacklist.
* **Key Rotation:** Session keys rotate automatically on session close, timeout, or after 1,000 signed operations.
* **Scope Binding:** Execution layer recomputes HMAC using exact cell coordinate, value, and record ID. Any mismatch aborts execution.

---

## 5. Realistic Workbook Compatibility & Safe Failure Matrix

The platform establishes an explicit compatibility matrix. Ingestion in Release 1.0 supports `.xlsx`, `.xlsm`, and planned read-only `.xlsb` (pending EXP-05 empirical verification). Writing is restricted to `.xlsx` and `.xlsm`:

```
+==================================================================================================================================+
|                                        WORKBOOK COMPATIBILITY & SAFE FAILURE MATRIX                                              |
+==================================================================================================================================+
| Workbook Feature / Element | Support Level              | Read | Write | Safe Failure / Quarantine Behavior                      |
+----------------------------+----------------------------+------+-------+---------------------------------------------------------+
| .xlsx (Standard OpenXML)   | Supported (Established)    | YES  | YES   | Parsing error raises InspectionAborted; file untouched. |
| .xlsm (Macro-Enabled)      | Supported with Limitations | YES  | YES   | VBA binary (vbaProject.bin) preserved as opaque blob.   |
|                            | (Pending EXP-05)           |      |       | Macro execution is STRICTLY UNSUPPORTED.                |
| .xlsb (Binary Workbook)    | Planned Read-Only Source   | YES  | NO    | Ingestion planned for source files (pending EXP-05);   |
|                            | (Pending EXP-05)           |      |       | Master .xlsb unsupported for writing (requires .xlsx).  |
| Structured Tables (ListObj)| Supported                  | YES  | YES   | Table definition updated; boundary expanded.            |
| Formulas (Static Resolv.)  | Supported with Limitations | YES  | YES   | Preserved; calc deferred via fullCalcOnLoad="1".        |
| Dynamic Arrays & Volatile  | Limited / Quarantined      | YES  | NO    | Classed as UNRESOLVED_DYNAMIC_DEPENDENCY; quarantined in|
| (INDIRECT, OFFSET, Spills#)| (Subject to EXP-04)        |      |       | EXP-04; layout mutations blocked in spill zones.        |
| Merged Cells               | Supported with Limitations | YES  | NO    | Source merged cells unmerged into logical matrix;       |
|                            |                            |      |       | Master active insertion range cannot have merged cells. |
| Named Ranges               | Supported                  | YES  | YES   | Preserved; expanded if bound to expanding table.        |
| Conditional Formatting     | Supported with Limitations | YES  | YES   | Preserved; rule ranges expanded across appended rows.   |
| Charts, Shapes & Drawings  | Read-Only Preservation     | YES  | NO    | Drawing XML parts preserved verbatim as opaque streams. |
| Comments & Threaded Notes  | Supported                  | YES  | YES   | Comment XML parts preserved; new notes appended.        |
| Data Validation Rules      | Supported                  | YES  | YES   | Validated in shadow dry-run; rule violation halts plan. |
| External Links & DDE       | Explicitly Blocked         | YES  | NO    | DDE (=cmd|...) stripped or plan rejected as attack.     |
| Encrypted / Password Files | Unsupported                | NO   | NO    | Rejection with clear prompt: Password not supported.    |
| Legacy Excel 4.0 Macros    | Explicitly Blocked         | NO   | NO    | File quarantined; execution rejected for security.      |
| Custom XML Parts           | Read-Only Preservation     | YES  | NO    | Custom XML parts preserved verbatim in OpenXML package. |
+==================================================================================================================================+
```

---

## 6. Measurable Acceptance Criteria & Verification Benchmarks

```
+==================================================================================================================================+
|                                              MEASURABLE ACCEPTANCE CRITERIA MATRIX                                               |
+==================================================================================================================================+
| Criterion ID | Target Capability               | Benchmark Corpus                | Metric & Measurement Method | Minimum Threshold |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-MAP-01    | Semantic Field Mapping          | BENCH-MAP-100 (100 pairs with   | Precision & Recall against  | Precision >= 98%  |
|              |                                 | synonymous/shuffled headers)    | ground-truth mapping key    | Recall >= 95%     |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-DEDUP-02  | Duplicate Record Identification | BENCH-DEDUP-500 (500 records;   | False Positive Rate (FPR)   | FPR = 0.0% (Zero  |
|              |                                 | subtle duplicates & collisions) | and False Negative Rate     | false overwrites) |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-ENRICH-03 | Blank-Field Enrichment Gate     | BENCH-ENRICH-50 (50 records     | Authorization Enforcement   | 100% halted; zero |
|              |                                 | with blank Master cells)        | Rate on unapproved actions  | unapproved writes |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-AUDIT-04  | Static Quality Auditing (R1.0)  | BENCH-AUDIT-200 (Pilot) &       | Defect Detection Rate &     | Detection >= 98%; |
|              | (5 defect categories)           | BENCH-AUDIT-EXTENDED (Full)     | FPR via clustered bootstrap | FPR <= 1.0% (CI   |
|              |                                 | under PROTOCOL-QA-01            | accounting for correlations | margin <= +-1.2%) |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-ROLL-05   | Local Transaction Rollback &    | FAULT-INJECT-50 (Simulated I/O  | Bitwise SHA-256 match       | 100% bitwise      |
|              | Durability (Single Local Volume)| kill during table append/commit)| against pre-execution image | restoration       |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-PARITY-06 | Semantic OpenXML Preservation   | BENCH-PARITY-50 (Complex sheets | OpenXML AST diff on non-    | 100% AST node &   |
|              |                                 | with charts, VBA, styles)       | targeted XML parts          | style equivalence |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-IDEMP-07  | Multi-Run Idempotency           | BENCH-IDEMP-20 (Reprocessing    | Second-pass mutation delta  | Exactly 0 new row |
|              |                                 | identical source workbooks)     | count                       | insertions        |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-SCALE-08  | Single-Sheet Streaming Memory   | BENCH-SCALE-100K (100,000 rows  | Peak process Resident Set   | Peak RSS < 250MB; |
|              | Scalability                     | × 50 columns sparse grid)       | Size (RSS) via OS probe     | Latency < 15s     |
+--------------+---------------------------------+---------------------------------+-----------------------------+-------------------+
| AC-PERF-09   | V1.2 Multi-Workbook Profiling   | BENCH-PERF-MULTI-5 (5 sources   | Wall-clock profiling time   | Latency <= 60s;   |
|              | & Memory (Profile 1 Baseline)   | up to 20k rows each + Master)   | and relative memory ratio   | RAM <= 4x uncomp. |
+==================================================================================================================================+
```
