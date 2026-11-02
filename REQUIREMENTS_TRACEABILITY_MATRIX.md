# Autonomous Excel Intelligence Platform
## Requirements Traceability Matrix (RTM)

**Document Type:** Formal Requirements Traceability Matrix  
**Document Version:** 2.6-Final-Reconciled-Draft  
**Document Status:** DRAFT — Subject to Project-Owner Review  
**Implementation Authorization:** STRICTLY NOT GRANTED  

---

## 1. Traceability Architecture & Status Taxonomy

This matrix links every functional (FR) and non-functional (NFR) requirement to its operational profile, release milestone, priority, verification method, dependencies, and measurable acceptance criteria. It explicitly incorporates the governance authority bridge connecting `REQUIREMENTS_SPECIFICATION.md` (V1.2 Frozen Baseline for Profile 1: Multi-Workbook Consolidation) to `PRODUCT_REQUIREMENTS_BASELINE.md` (v2.6 Universal Platform Baseline).

```
+==================================================================================================================================+
|                                              REQUIREMENTS TRACEABILITY MATRIX                                                    |
+==================================================================================================================================+
| Req ID    | Requirement Statement                | Type | Prio | Profile & Milestone  | Measurable Acceptance Criteria    | Verification    |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-01    | Zero-Template Workbook Ingestion     | FR   | P0   | Core / Release 1.0   | Ingest .xlsx, .xlsm, and planned  | BENCH-INGEST-50 |
|           | (Arbitrary Layout Ingestion)         |      |      |                      | read-only .xlsb (pending EXP-05); | test harness    |
|           |                                      |      |      |                      | 0 process crashes.                |                 |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-02    | Topological Region Segmentation      | FR   | P0   | Core / Release 1.0   | Detect multiple tables/summaries; | Bounding-box    |
|           |                                      |      |      |                      | IoU >= 0.98 on BENCH-LAYOUT-100.  | spatial diff    |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-03    | Dynamic Semantic Type Inference      | FR   | P0   | Core / Release 1.0   | Infer data types & codes;         | Statistical F1  |
|           |                                      |      |      |                      | Precision >= 98%, Recall >= 95%.  | score benchmark |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-04    | Air-Gap Barrier & Threat Boundary    | NFR  | P0   | Core / Release 1.0   | 0 direct file handles or OS shell | Sandboxed audit |
|           | (LLM Code Generation Isolation)      |      |      |                      | calls by LLM; parser risks secured| & fuzzing suite |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-05    | Formula AST Dependency Mapping       | FR   | P0   | Core / Release 1.0   | Build precedent DAG for static    | AST cycle test  |
|           | & Static Cycle Detection             |      |      |                      | formulas; 100% static cycle detect| suite (50 cases)|
|           |                                      |      |      |                      | (volatile formulas quarantined).  | & EXP-04        |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-06    | OpenXML Semantic Parity Preservation | NFR  | P0   | Core / Release 1.0   | 100% AST node & style parity on   | OpenXML AST diff|
|           |                                      |      |      |                      | non-targeted workbook regions.    | test suite      |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-07    | Multi-Source Consolidation Ingestion | FR   | P0   | Profile 1 / Rel 1.0  | Ingest N source files (.xlsx,.xlsm| Multi-workbook  |
|           |                                      |      |      |                      | ro-.xlsb) into 1 Master; 0 bleed. | pipeline test   |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-08    | Dynamic Source-to-Master Mapping     | FR   | P0   | Profile 1 / Rel 1.0  | Map divergent headers to Master;  | Ground-truth key|
|           |                                      |      |      |                      | Precision >= 98%, Recall >= 95%.  | BENCH-MAP-100   |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-09    | Evidence-Based Deduplication         | FR   | P0   | Profile 1 / Rel 1.0  | Identify existing Master records; | BENCH-DEDUP-500 |
|           |                                      |      |      |                      | False Positive Rate = 0.0%.       | test harness    |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-10    | Missing-Field Enrichment Gate (FR-09)| FR   | P0   | Profile 1 / Rel 1.0  | Master blank cells require human  | HITL isolation  |
|           |                                      |      |      |                      | sign-off; 0 unapproved writes.    | test suite      |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-11    | Populated Cell Overwrite Gate (FR-10)| FR   | P0   | Profile 1 / Rel 1.0  | Overwrite of any non-empty cell   | Overwrite gate  |
|           |                                      |      |      |                      | blocked without HMAC token.       | test suite      |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-12    | Cross-Source Conflict Review (DR-A2) | FR   | P0   | Profile 1 / Rel 1.0  | Divergent values for same key halt| Conflict card UI|
|           |                                      |      |      |                      | for HITL; non-response=quarantine.| test suite      |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-13    | Confinement to Existing Master Target| FR   | P0   | Profile 1 / Rel 1.0  | 0 new sheets, tables, or columns  | Schema diff &   |
|           |                                      |      |      |                      | created during consolidation.     | OpenXML audit   |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-14    | Non-Table Insertion Safety (DR-A3)   | FR   | P0   | Profile 1 / Rel 1.0  | Halt append if ordinary range has | Spatial limit   |
|           |                                      |      |      |                      | summary rows below and 0 space.   | collision test  |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-15    | Full Provenance Audit Logging        | FR   | P0   | Core / Release 1.0   | Append-only SHA-256 chained log   | Audit ledger    |
|           |                                      |      |      |                      | linking every cell to source row. | verification    |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-16    | Scoped Cryptographic Approval Tokens | NFR  | P0   | Core / Release 1.0   | HMAC-SHA256 tokens; 15-min TTL;   | Concurrent race |
|           |                                      |      |      |                      | atomic nonce; approver ID binding.| & replay harness|
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-17    | Transaction Durability & Rollback    | NFR  | P0   | Core / Release 1.0   | • Local FS: Staged write, fsync,  | FAULT-INJECT-50 |
|           |                                      |      |      |                      |   parent dir sync, atomic swap,   | & EXP-06 Spike  |
|           |                                      |      |      |                      |   WAL sequencing, bitwise rollback| (Local FS / SMB |
|           |                                      |      |      |                      | • SMB & Cloud Sync: staging retry | / OneDrive)     |
|           |                                      |      |      |                      |   (Unverified targets in EXP-06). |                 |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-18    | Multi-Run Idempotency                | NFR  | P0   | Profile 1 / Rel 1.0  | Reprocessing identical sources    | BENCH-IDEMP-20  |
|           |                                      |      |      |                      | results in exactly 0 insertions.  | 2-pass regr.    |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-19    | Untrusted Data & Injection Defense   | NFR  | P0   | Core / Release 1.0   | Neutralize formula injection,     | Security fuzzing|
|           |                                      |      |      |                      | DDE commands, and prompt hacks.   | test suite      |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-20a   | V1.2 Multi-Workbook Profiling Perf.  | NFR  | P0   | Profile 1 / Rel 1.0  | Profile 5 sources (up to 20k rows)| BENCH-PERF-     |
|           | (Consolidation Baseline Performance) |      |      |                      | + Master in <=60s; peak RAM <=4x  | MULTI-5         |
|           |                                      |      |      |                      | uncompressed OpenXML sheet size.  | harness         |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-20b   | Single-Sheet Streaming Memory Scale  | NFR  | P0   | Core / Release 1.0   | Parse 100k-row sheet with peak    | Process RSS via |
|           |                                      |      |      |                      | process RSS < 250MB; latency < 15s| psutil (EXP-02) |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-21    | Natural Language Intent Translation  | FR   | P1   | Profile 2 / Rel 2.0  | Parse operational user goals into | Intent benchmark|
|           |                                      |      |      |                      | validated, grounded DAG plans.    | suite (50 tasks)|
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-22    | User-Directed Formula Synthesis      | FR   | P1   | Profile 2 / Rel 2.0  | Synthesize valid calculation rules| Formula AST &   |
|           |                                      |      |      |                      | from descriptions (e.g., Margin). | syntax tests    |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-23    | Intent-Authorized Structural Create  | FR   | P1   | Profile 3 / Rel 3.0  | Create summary sheets/tables when | Plan validation |
|           |                                      |      |      |                      | explicitly instructed by user.    | & diff test     |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-24    | Cross-Sheet Relationship Generation  | FR   | P2   | Profile 2 / Rel 2.0  | Construct automated XLOOKUP links | Relation graph  |
|           |                                      |      |      |                      | across disparate workbook tabs.   | validation test |
+-----------+--------------------------------------+------+------+----------------------+-----------------------------------+-----------------+
| REQ-25    | Static Structural & Quality Audit    | FR   | P0   | Core / Release 1.0   | Catalog pre-existing defects:     | PROTOCOL-QA-01  |
|           |                                      |      |      |                      | (1) #REF!, #VALUE!, #DIV/0!,      | on BENCH-       |
|           |                                      |      |      |                      |     #NAME?, #N/A formula errors   | AUDIT-200 pilot |
|           |                                      |      |      |                      | (2) static circular ref cycles    | & EXTENDED      |
|           |                                      |      |      |                      | (3) jagged rows violating bounds  | corpus (cluster-|
|           |                                      |      |      |                      | (4) unmapped source fields        | robust standard |
|           |                                      |      |      |                      | (5) candidate key collisions.     | error evaluation|
+==================================================================================================================================+
```

---

## 2. Status Tracking & Approval State

* **P0 Requirements (Release 1.0 Core & Consolidation Baseline):** REQ-01 through REQ-19, REQ-20a, REQ-20b, and REQ-25 (22 requirements) are mandatory for the initial operational release. REQ-01 and REQ-07 incorporate planned read-only `.xlsb` ingestion pending EXP-05 empirical verification. REQ-20a explicitly preserves approved V1.2 NFR-03 multi-workbook consolidation performance (5 workbooks $\le 20\text{k}$ rows + Master in $\le 60$s, $\le 4\times$ uncompressed sheet size RAM), while REQ-20b governs single-sheet 100k-row streaming efficiency ($< 250$MB RSS). REQ-25 is verified via `PROTOCOL-QA-01` utilizing category-specific denominators, intra-workbook cluster-robust estimation, and phased corpus evaluation (`BENCH-AUDIT-200` pilot and `BENCH-AUDIT-EXTENDED`).
* **P1 Requirements (Release 2.0 Formula Intelligence & Release 3.0 Reporting):** REQ-21 through REQ-23 (3 requirements).
* **P2 Requirements (Release 2.0 Relational Lookups):** REQ-24 (1 requirement).
* **Current Formal Status across all Requirements:** `DRAFT v2.6 — SUBJECT TO PROJECT-OWNER REVIEW`.
