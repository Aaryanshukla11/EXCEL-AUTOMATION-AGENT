# BACKEND ARCHITECTURE & INTEGRATION PLAN (MILESTONE B0)

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration (B0–B7)  
**Date:** 2026-11-23  
**Auditor / Architect:** Autonomous Backend Architecture Sentinel  
**Status:** COMPLETE — REVISED AUTHORITATIVE BLUEPRINT APPROVED

---

## 1. Architectural Baseline & Design Philosophy

### 1.1 Context & Scope
Frontend milestones **F0 through F5** are formally accepted, frozen, and verified across all 9 application routes. The frontend currently operates against an in-memory Mock Service Worker (MSW) harness and mock adapter layer.

The backend core **M01 through M05** is accepted and frozen, comprising:
- A high-performance, memory-bounded Rust OpenXML engine (`crates/excel_intel_rs`) providing streaming pull-parsing, IEEE 754 date calculations, zip decompression bomb defenses, and LRU shared strings caching (60/60 tests passing).
- A deterministic Python core (`excel_intel/`) providing workbook inspection (`WorkbookInspector`), spatial table region detection (`SpatialDetector`), semantic type profiling (`TypeInferenceEngine`), and static formula dependency graphs (`FormulaGraph`) (362/362 tests passing).

The purpose of the **B-Series Workstream (B0–B7)** is to construct the backend web service layer, storage engines, cognitive recommendation services, server-side approval authority, and physical 6-phase Write-Ahead Logging (WAL) execution engine that replaces frontend MSW mock harnesses with a live, deterministic, production-grade backend.

```
+=================================================================================================+
|                                      FRONTEND APPLICATION (F0-F5)                               |
|   Staging Queue | Spatial Viewer | Schema Studio | Quality Console | Approvals | Execution | Audit   |
+=================================================================================================+
                                                  │
                                   HTTP / REST & WebSocket (/api/v1)
                                                  ▼
+=================================================================================================+
|                                  FASTAPI WEB SERVICE LAYER (B1)                                 |
|   Admission Control Semaphore │ Request Validation │ RFC 7807 Error Handlers │ Auth & Security   |
+=================================================================================================+
           │                              │                              │
           ▼                              ▼                              ▼
+──────────────────────+       +──────────────────────+       +──────────────────────+
|   INGESTION SERVICE  |       |  ANALYSIS & MAPPING  |       |   EXECUTION & AUDIT  |
|       (B2, B3)       |       |       (B4, B5)       |       |       (B6, B7)       |
| • Multipart Upload   |       | • Spatial Detection  |       | • HMAC-SHA256 Token  |
| • Quota & Bomb Check |       | • Type Inference     |       | • 6-Phase WAL Engine |
| • Staging Storage    |       | • Formula Cycle DAG  |       | • Atomic Win32/POSIX |
| • Manifest Synthesis |       | • Schema Matcher     |       | • SQLite Audit Vault |
+──────────────────────+       +──────────────────────+       +──────────────────────+
           │                              │                              │
           └──────────────────────────────┼──────────────────────────────┘
                                          ▼
+=================================================================================================+
|                              DETERMINISTIC CORE ENGINE (M01-M05)                                |
|   Python Inspection Facades │ In-Process PyO3 Rust Engine (_rs.pyd) │ 250 MiB Hard Memory Ceiling |
+=================================================================================================+
```

### 1.2 Core Architectural Principles
1. **Strict Determinism & Invariant Preservation**: Every operation from inspection to physical mutation must produce bit-for-bit reproducible outcomes given identical inputs. No stochastic behavior in the execution path.
2. **Memory Ceiling (ADR-001)**: The process must strictly respect the 235 MiB soft warning threshold and 250 MiB hard memory ceiling enforced by `memory_guard.rs`. Large workbooks must be processed via streaming pull-parsers without in-memory DOM expansion.
3. **Inviolable Air-Gap (ADR-006)**: Cognitive deliberations, fuzzy mapping heuristics, and LLM reasoning components have **zero access** to physical filesystem handles, database transaction managers, or physical file persistors.
4. **Physical Durability over Virtual Promises**: Simulated WAL execution or client-side approvals must never be presented as physical filesystem durability. The physical execution engine must enforce pre-state byte backups, journal sync barriers, and atomic directory flushes.
5. **Zero Duplicate Engines**: The service layer wraps existing, verified M01–M05 modules and Rust bindings. No second Excel engine or duplicate parsers shall be created.

---

## 2. Memory and Concurrency Architecture

### 2.1 The Process Memory Envelope Challenge
The Rust deterministic engine (`crates/excel_intel_rs/src/memory_guard.rs`) enforces a strict process-level working set memory ceiling via OS API (`GetProcessMemoryInfo` on Windows):
- **235 MiB Soft Warning Ceiling**
- **250 MiB Hard Kill Switch (`MemoryCeilingError`)**

When running the FastAPI service inside the same Python process as Uvicorn and PyO3:
- Base Python runtime + loaded modules: $\approx 20\text{--}25\text{ MiB}$
- Uvicorn server, event loop, and ASGI connection state: $\approx 15\text{--}20\text{ MiB}$
- SQLAlchemy database pool and cached statements: $\approx 10\text{--}15\text{ MiB}$
- **Net Available Memory Budget for Workbook Parsing**: $\approx 175\text{--}190\text{ MiB}$.

Under unconstrained concurrency, two simultaneous inspections of multi-megabyte spreadsheets would cause process RSS to cross 250 MiB, triggering process termination.

### 2.2 Concurrency Policy & Request Admission Control
To guarantee absolute memory safety without weakening the 250 MiB ceiling, the service implements:

1. **Strict Workload Admission Semaphore**:
   - Heavy parsing tasks (`inspect_workbook`, `detect_sheet`, `infer_sheet`, `FormulaGraph.build_graph`) are guarded by an application-level semaphore:
     ```python
     heavy_parsing_semaphore = asyncio.Semaphore(1)
     ```
   - Light operations (metadata retrieval, health checks, approval reviews, audit log reading) run concurrently without semaphores.
2. **Preflight Memory Reservation Check**:
   - Before acquiring the semaphore, the server inspects the current process RSS via `memory_guard.query_working_set()`.
   - If current RSS $> 180\text{ MiB}$, the request is rejected with `HTTP 503 Service Unavailable / 429 Too Many Requests` and a `Retry-After: 5` header rather than risking a process abort.
3. **Cooperative Cancellation**:
   - Between sheet inspections in `WorkbookInspector.inspect_workbook()`, the service inspects `request.is_disconnected()`.
   - If the client drops connection (e.g. user navigates away), inspection terminates immediately, releasing parser references and allocated arenas.
4. **Process Isolation for Future Scaling**:
   - For multi-worker deployments, workers run in dedicated processes (`uvicorn --workers N`), where each worker process owns its independent 250 MiB ceiling and admission semaphore.

---

## 3. Authentication, Authorization & Tenant Identity Architecture

### 3.1 Identity Distinctions
The architecture enforces strict separation between identity dimensions:
1. **Authenticated Principal**: The cryptographically verified caller identity (e.g., verified via local session token or bearer token).
2. **Operator Identity**: The specific actor taking an administrative or consolidation action (e.g., `lead_operator@corp.internal`). Extracted strictly from server-validated credentials, **never trusted from client-submitted JSON body fields**.
3. **Tenant Identity**: The isolated organizational boundary (e.g., `tenant_default`), binding all file storage, workbooks, approvals, and jobs. Derived from server-side session configuration.
4. **Roles & Permissions**: Four discrete roles:
   - `Viewer`: Read-only access to manifests, spatial regions, and audit history.
   - `Operator`: Upload workbooks, stage files, generate mapping drafts, trigger execution.
   - `Approver`: Review risk classifications, approve/reject OperationPlans, issue HMAC tokens.
   - `Admin`: Manage client configuration and platform parameters.
5. **Resource Ownership**: Every resource (`WorkbookRecord`, `ApprovalRecord`, `JobRecord`) is keyed by `(tenant_id, resource_id)`. Cross-tenant access attempts return `404 Not Found`.

### 3.2 Phased Authentication Roadmap
- **Phase 1: Local Development Mode (Current Baseline)**:
  - Active when `ENVIRONMENT == "development"` and bound strictly to localhost (`127.0.0.1` / `::1`).
  - Requests without headers assume `DefaultDevPrincipal` with roles `[Viewer, Operator, Approver, Admin]`.
  - Development operator simulation is permitted via `X-Dev-Operator: <name>` only on localhost.
- **Phase 2: Production Hardening (Required before Exposing Beyond Localhost)**:
  - Exposing the backend beyond localhost requires:
    1. TLS 1.3 encryption mandatory.
    2. Bearer token validation (OAuth2 / OIDC JWT) with signature verification against an identity provider public key.
    3. Revocation checks and expiration enforcement.
    4. Client-submitted `operator_id` fields completely ignored; identity extracted from JWT claims (`sub`, `email`, `roles`).

---

## 4. SQLite Durability & Storage Strategy

### 4.1 Distinguishing Database WAL from Execution WAL
The system maintains two completely distinct Write-Ahead Logging mechanisms that must never be confused:
1. **SQLite Database WAL**: The database storage engine managing relational tables (workbooks, approvals, jobs, audit blocks).
2. **Workbook Execution WAL**: The application-level, physical 6-phase atomic file replacement protocol managing physical spreadsheet byte mutations on disk.

### 4.2 SQLite Database Durability Configuration
To fulfill the platform's zero-data-loss guarantee:
- **Journal Mode**: `PRAGMA journal_mode = WAL;` (Enables concurrent readers alongside single-writer).
- **Synchronous Setting**: `PRAGMA synchronous = FULL;`
  - *Trade-off Analysis*: While `synchronous = NORMAL` provides higher throughput, an OS crash or power failure can corrupt or lose the latest WAL frames. Because the database records **human approval decisions** and **single-use token nonces**, lost records could result in replay vulnerabilities or orphaned approvals. Setting `synchronous = FULL` guarantees physical disk flushing for every committed approval and audit block.
- **Foreign Keys**: `PRAGMA foreign_keys = ON;` (Mandatory relational integrity).
- **Busy Timeout**: `PRAGMA busy_timeout = 5000;` (Writers wait up to 5 seconds before throwing lock errors).
- **Transaction Boundaries**: All nonce consumption and approval state transitions use explicit `BEGIN IMMEDIATE` transactions to prevent writer lock escalation deadlocks.

---

## 5. Execution Architecture: 6-Phase WAL & Recovery Safety

### 5.1 Physical 6-Phase WAL Protocol

```
+---------------------------------------------------------------------------------+
| Phase 1: PRE_STATE_SNAPSHOT (.bak)                                              |
| Byte-for-byte copy to backup dir; physical fsync; pre_sha256 verified           |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
| Phase 2: WAL_INTENT_RECORDED (Journal)                                          |
| Plan hash, token, target path, pre_sha256 written to .wal; hardware sync barrier|
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
| Phase 3: STAGED_MUTATION_FSYNC (Scratch)                                        |
| Streaming OpenXML modification into scratch on SAME volume; data fsync          |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
| Phase 4: ATOMIC_REPLACE (OS-Level)                                              |
| Win32 MoveFileExW(REPLACE_EXISTING) / POSIX rename(2) atomic swap               |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
| Phase 5: PARENT_DIR_SYNC (Flush)                                                |
| Flush parent directory entry to physical media storage controller               |
+---------------------------------------------------------------------------------+
                                       │
                                       ▼
+---------------------------------------------------------------------------------+
| Phase 6: WAL_COMMITTED (Finalized)                                              |
| Commit marker appended to .wal; locks released; audit block appended to ledger  |
+---------------------------------------------------------------------------------+
```

### 5.2 Concurrency & Verification Safety Invariants
1. **Concurrent Writer Exclusion**:
   - Before taking a pre-state snapshot, the engine acquires an exclusive OS file lock (`LockFileEx` on Windows, `fcntl.flock(LOCK_EX)` on POSIX) on the target workbook. No other process or worker may write concurrently.
2. **Target File Identity & External Mutation Defense**:
   - The engine computes the current target file's SHA-256 hash.
   - If the hash does not match `target_fingerprint.sha256` recorded in the `OperationPlan`, execution is **aborted immediately** with `409 TARGET_MUTATED_EXTERNALLY`.
3. **Backup Verification**:
   - The pre-state snapshot is copied to `${STORAGE_ROOT}/backups/{target_name}_{timestamp}.bak`.
   - The engine hashes the `.bak` file and confirms it matches the target hash before proceeding to write.
4. **Volume Co-Location Invariant**:
   - The scratch file generated during Phase 3 **must reside on the same physical filesystem volume** as the target workbook. Cross-volume replacement degrades to a non-atomic copy-and-delete, which is strictly prohibited.
5. **Crash Recovery Protocol (`startup_recovery`)**:
   - On server startup, the recovery engine inspects all unfinalized WAL journals in `${STORAGE_ROOT}/wal/*.wal`:
     - **Case A (Target hash == `post_sha256`)**: Atomic replacement completed before crash, but commit marker was interrupted. The engine logs completion and updates the ledger.
     - **Case B (Target hash == `pre_sha256`)**: Crash occurred before Phase 4. Target is untouched. Scratch file is purged; job marked `ROLLED_BACK`.
     - **Case C (Target hash matches partial/corrupt state)**: Crash occurred during replacement. The engine atomically restores the `.bak` file and logs a recovery audit event.
     - **Case D (Target hash is unknown and timestamp indicates external edit)**: Target was modified out-of-band by an external user during crash. The engine **never blindly overwrites** the file; it quarantines the file and raises a critical operator alert (`AUDIT_RECOVERY_COLLISION`).

---

## 6. OpenXML Writer Strategy for Milestone B7

### 6.1 The Technical Challenge
The existing Rust OpenXML parser (`crates/excel_intel_rs`) and Python readers (`StreamingWorkbookReader`) are strictly read-only pull-parsers. Excel workbooks (`.xlsx` / `.xlsm`) contain dozens of interrelated XML parts:
- `[Content_Types].xml`
- `_rels/.rels` and `xl/_rels/workbook.xml.rels`
- `xl/workbook.xml`
- `xl/sharedStrings.xml`
- `xl/styles.xml`
- `xl/worksheets/sheetN.xml`
- VBA project binaries (`xl/vbaProject.bin` in `.xlsm`)
- Charts, drawings, pivot tables, slicers, and custom XML properties.

A naive full DOM re-generation would strip out unsupported parts, destroy VBA macros, or corrupt custom styles.

### 6.2 Pass-Through ZIP Stream Mutation Strategy
Milestone B7 will implement a **Pass-Through ZIP Stream Mutation Engine**:

```
[Source Workbook (.xlsx/.xlsm)]
              │
              ▼ (Iterate through ZIP members)
+─────────────────────────────────────────────────────────────────────────────+
| Unmodified Parts (Verbatim Byte Pass-Through):                              |
| • [Content_Types].xml, _rels, styles.xml, themes                            |
| • Non-target sheets (sheet2.xml, sheet3.xml...)                             |
| • Charts, drawings, pivot tables, VBA macros (vbaProject.bin)               |
|                                                                             |
| ──► Copied raw byte-for-byte to Scratch ZIP without parsing                 |
+─────────────────────────────────────────────────────────────────────────────+
              │
              ▼ (Only target sheet & string parts are transformed)
+─────────────────────────────────────────────────────────────────────────────+
| Transformed Parts:                                                          |
| 1. xl/sharedStrings.xml: Append new unique strings; update count & uniqueCount|
| 2. xl/worksheets/sheetN.xml: Streaming XML transformation                   |
|    - Stream copy preceding XML nodes                                        |
|    - Inject/update cell nodes (<c r="B14" t="s">...) from CanonicalOperation|
|    - Update <dimension ref="A1:N1420"/>                                     |
|    - Stream copy trailing XML nodes                                         |
+─────────────────────────────────────────────────────────────────────────────+
              │
              ▼
[Scratch Output Workbook (.xlsx/.xlsm)] ──► Ready for Atomic Replacement
```

### 6.3 Semantic Preservation Guarantees
1. **Zero Data Loss on Unsupported Features**: Because unmodified ZIP entries are copied byte-for-byte, VBA macros, chart objects, printer settings, and custom XML parts remain 100% intact.
2. **Formula Integrity**: Formulas in existing cells are never overwritten unless explicitly targeted by a `PROPAGATE_FORMULA` or `UPDATE_CELL` operation.
3. **Shared Strings Consistency**: New string tokens are assigned sequential IDs beyond the existing `uniqueCount`.

---

## 7. Canonical API Contract Alignment

The API routes across all documentation are harmonized to the authoritative specification defined in `docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md`:

| Category | Canonical HTTP Route | Method | Capability State |
|---|---|:---:|:---:|
| **Health** | `/api/v1/health` | GET | `[NEW_SERVICE_REQUIRED]` |
| **Config** | `/api/v1/config/client` | GET / PUT | `[NEW_SERVICE_REQUIRED]` |
| **Workbooks** | `/api/v1/workbooks/upload` | POST | `[NEW_SERVICE_REQUIRED]` |
| **Workbooks** | `/api/v1/workbooks` | GET | `[NEW_SERVICE_REQUIRED]` |
| **Workbooks** | `/api/v1/workbooks/{id}` | GET / DELETE | `[CORE_IMPLEMENTED]` |
| **Manifest** | `/api/v1/workbooks/{id}/manifest` | GET | `[CORE_IMPLEMENTED]` |
| **Inspection**| `/api/v1/workbooks/{id}/inspection` | GET | `[CORE_IMPLEMENTED]` |
| **Spatial** | `/api/v1/workbooks/{id}/sheets/{sheet}/spatial` | GET | `[CORE_IMPLEMENTED]` |
| **Types** | `/api/v1/workbooks/{id}/sheets/{sheet}/types` | GET | `[CORE_IMPLEMENTED]` |
| **Formulas** | `/api/v1/workbooks/{id}/formulas/graph` | GET | `[CORE_IMPLEMENTED]` |
| **Quality** | `/api/v1/workbooks/{id}/quality/findings` | GET | `[CORE_IMPLEMENTED]` |
| **Mapping** | `/api/v1/schema-mapping/targets` | GET | `[NEW_SERVICE_REQUIRED]` |
| **Mapping** | `/api/v1/schema-mapping/recommendations` | POST | `[NEW_SERVICE_REQUIRED]` |
| **Approvals** | `/api/v1/approvals` | GET | `[DATA_MODEL_ONLY]` |
| **Approvals** | `/api/v1/approvals/{id}` | GET | `[DATA_MODEL_ONLY]` |
| **Approvals** | `/api/v1/approvals/{id}/decision` | POST | `[NEW_SERVICE_REQUIRED]` |
| **Execution** | `/api/v1/execution/jobs` | GET | `[DATA_MODEL_ONLY]` |
| **Execution** | `/api/v1/execution/jobs/{id}` | GET | `[DATA_MODEL_ONLY]` |
| **Execution** | `/api/v1/execution/jobs/{id}/run` | POST | `[FUTURE_EXECUTION_REQUIRED]` |
| **Execution** | `/api/v1/execution/jobs/{id}/rollback` | POST | `[FUTURE_EXECUTION_REQUIRED]` |
| **Audit** | `/api/v1/audit/blocks` | GET | `[DATA_MODEL_ONLY]` |
| **Audit** | `/api/v1/audit/verify-chain` | POST | `[NEW_SERVICE_REQUIRED]` |

---

## 8. Milestone Roadmap Alignment (B1–B7)

The implementation sequence is structured into 7 sequential milestones:
- **B1**: Backend Foundation & FastAPI Application Shell (Server, SQLite WAL, RFC 7807, `/health`, `/config`).
- **B2**: Workbook Staging & Ingestion Service (Secure upload, size quota, Rust zip-bomb defense, `/workbooks`).
- **B3**: Spatial Discovery & Semantic Manifest API (Bridge M03 inspection, M04 spatial detection, M05 types).
- **B4**: Data Quality, Formula Graph & Defect Scanner Service (Formula cycles, anomaly triage, `/quality`).
- **B5**: Schema Mapping & Recommendation Engine (Heuristic matching, OperationPlan model, `/schema-mapping`).
- **B6**: Server-Side Approval Authority & SQLite Audit Ledger (HMAC tokens, replay defense, SQLite audit).
- **B7**: Deterministic 6-Phase WAL Execution Engine & End-to-End Integration (OpenXML writer, atomic replace, full E2E).

---

## 9. Final B0 Review & Acceptance Declaration

### 9.1 Resolved Architectural Decisions
1. **Memory Safety**: Solved via single-worker admission semaphore (`asyncio.Semaphore(1)`) and preflight RSS queries. The 250 MiB ceiling remains strictly enforced.
2. **Identity**: Operator and tenant identities are strictly resolved server-side from authenticated credentials, never trusted from client JSON.
3. **Database Durability**: SQLite configured with `journal_mode = WAL` and `synchronous = FULL` to eliminate lost approvals or phantom nonces on power failure.
4. **Canonical Endpoints**: All endpoint ambiguities resolved into a single canonical path registry matching frontend contracts.
5. **Recovery Safety**: Replaced blind backup overwriting with hash-verified recovery and collision quarantining.
6. **Writer Strategy**: Selected pass-through ZIP streaming mutation to preserve 100% of unsupported OpenXML parts and VBA macros.

### 9.2 Acceptance Decision
All architectural ambiguities have been resolved with strict mathematical and physical rigor. The architecture documents (`BACKEND_ARCHITECTURE_PLAN.md`, `FRONTEND_BACKEND_API_CONTRACT.md`, `BACKEND_CAPABILITY_AUDIT.md`, `BACKEND_MILESTONE_ROADMAP.md`) are in full agreement.

**Final Status:**  
`B0_ACCEPTED — READY_FOR_B1`
