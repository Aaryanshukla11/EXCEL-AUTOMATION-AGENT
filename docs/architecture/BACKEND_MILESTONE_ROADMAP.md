# BACKEND INTEGRATION MILESTONE ROADMAP (B1–B7)

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration  
**Date:** 2026-11-23  
**Status:** APPROVED ARCHITECTURAL ROADMAP  
**Auditor / Architect:** Autonomous Backend Architecture Sentinel  

---

## 1. Overview & Phasing Strategy

This roadmap defines the implementation path from the accepted foundation (F0–F5, M01–M05, B0) to a fully integrated, live production platform. The workstream is partitioned into 7 sequential milestones. Each milestone is self-contained, individually verifiable, and bounded by strict acceptance criteria.

```
+─────────────────────────────────────────────────────────────────────────────+
| B1: Backend Foundation & FastAPI Application Shell                           |
| Scope: FastAPI app, SQLite WAL database, CORS, RFC 7807 error format, /health|
+─────────────────────────────────────────────────────────────────────────────+
                                       │ 
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| B2: Workbook Staging & File Management Service                              |
| Scope: Multipart upload, Rust ZIP bomb guards, staging storage, /workbooks  |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| B3: Spatial Discovery & Semantic Manifest API                               |
| Scope: Wrap M03 inspection, M04 spatial detection, M05 types into REST APIs |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| B4: Data Quality, Formula Graph & Defect Scanner Service                    |
| Scope: Formula cycle detection, anomaly triage, /quality/findings endpoint  |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| B5: Schema Mapping & Recommendation Engine                                  |
| Scope: Heuristic column matchers, mapping candidates, OperationPlan model    |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| B6: Server-Side Approval Authority & SQLite Audit Ledger                    |
| Scope: 7-state approval engine, HMAC-SHA256 token authority, audit chain   |
+─────────────────────────────────────────────────────────────────────────────+
                                       │
                                       ▼
+─────────────────────────────────────────────────────────────────────────────+
| B7: Deterministic 6-Phase WAL Execution Engine & End-to-End Integration     |
| Scope: OpenXML pass-through writer, atomic MoveFileEx, fsync barriers, E2E  |
+─────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Detailed Milestone Specifications

### Milestone B1 — Backend Foundation & FastAPI Application Shell 

- **Scope**:
  - Author the core FastAPI application factory with dependency injection and lifecycle hooks.
  - Implement request admission control semaphore (`asyncio.Semaphore(1)`) and memory-guard preflight check.
  - Establish SQLite database with WAL journal mode (`PRAGMA journal_mode = WAL; PRAGMA synchronous = FULL; PRAGMA foreign_keys = ON;`).
  - Configure CORS middleware, request tracing correlation IDs (`X-Correlation-ID`), and RFC 7807 error handlers.
  - Implement `/api/v1/health` and `/api/v1/config/client` endpoints.
- **Deliverables**:
  - `excel_intel/server/app.py`
  - `excel_intel/server/dependencies.py`
  - `excel_intel/server/errors.py`
  - `excel_intel/server/routers/health.py`
  - `excel_intel/server/routers/config.py`
  - `excel_intel/server/database/session.py`
  - `excel_intel/server/database/models.py`
- **Dependencies**: M01 configuration and logging modules.
- **Files/Modules Affected**: `excel_intel/server/`, `pyproject.toml` (adding FastAPI, Uvicorn, SQLAlchemy, aiosqlite).
- **Test Requirements**:
  - Health check responds with memory telemetry and status `healthy`.
  - Client configuration endpoints validate with `ClientConfig` schema.
  - Unhandled exceptions format as RFC 7807 problem details with correlation IDs.
  - Database schema initializes with WAL and foreign key PRAGMAs.
- **Acceptance Criteria**: All B1 tests pass; zero modification to M01–M05 or F0–F5; memory footprint of clean server process remains $< 65\text{ MiB}$.
- **Risks**: Uvicorn event loop configuration on Windows Pro (must use ProactorEventLoop).
- **Estimated Effort**: 2 days.

---

### Milestone B2 — Workbook Staging & File Management Service

- **Scope**:
  - Implement secure multipart file upload (`POST /api/v1/workbooks/upload`).
  - Integrate Rust `zip_handler.rs` decompression bomb verification (100:1 ratio, 1 GiB cap, 10,000 members, path traversal rejection).
  - Implement tenant/workspace directory manager allocating files to `${STORAGE_ROOT}/staging/`.
  - Implement workbook inventory endpoints (`GET /api/v1/workbooks`, `GET /api/v1/workbooks/{id}`, `DELETE /api/v1/workbooks/{id}`).
- **Deliverables**:
  - `excel_intel/server/services/storage_service.py`
  - `excel_intel/server/routers/workbooks.py`
  - `tests/server/test_workbooks_api.py`
- **Dependencies**: B1 foundation, `crates/excel_intel_rs/src/zip_handler.rs`.
- **Files/Modules Affected**: `excel_intel/server/services/`, `excel_intel/server/routers/`.
- **Test Requirements**:
  - Uploading `.xlsx` and `.xlsm` stores physical file and computes exact SHA-256 fingerprint.
  - Uploading `.exe`, `.zip`, `.pdf`, or malformed binary rejects with `400 INVALID_FILE_TYPE`.
  - Zip bomb test fixtures trigger immediate rejection before extraction.
  - Deleting a workbook cleanly removes physical files and unregisters from SQLite.
- **Acceptance Criteria**: Multi-file uploads successfully store and register without memory leaks; memory ceiling remains unbreached.
- **Risks**: Windows file lock contention during rapid upload/delete cycles.
- **Estimated Effort**: 2 days.

---

### Milestone B3 — Spatial Discovery & Semantic Manifest API

- **Scope**:
  - Connect existing deterministic facades (`WorkbookInspector`, `SpatialDetector`, `TypeInferenceEngine`) to REST endpoints.
  - Expose `/api/v1/workbooks/{id}/manifest`, `/api/v1/workbooks/{id}/inspection`, `/api/v1/workbooks/{id}/sheets/{sheet}/spatial`, and `/api/v1/workbooks/{id}/sheets/{sheet}/types`.
  - Implement request admission control to ensure heavy parsing tasks run sequentially under the memory ceiling.
- **Deliverables**:
  - `excel_intel/server/services/workbook_service.py`
  - `excel_intel/server/routers/spatial.py`
  - `excel_intel/server/routers/types.py`
  - `tests/server/test_spatial_api.py`
- **Dependencies**: B2 staging service, M03, M04, M05.
- **Files/Modules Affected**: `excel_intel/server/services/`, `excel_intel/server/routers/`.
- **Test Requirements**:
  - Emitted `DiscoveryManifest` JSON exactly matches frontend contract in `frontend/src/contracts/discovery.ts`.
  - Emitted `SpatialTableRegion[]` exactly matches frontend contract in `frontend/src/contracts/spatial.ts`.
  - Concurrent inspection requests queue safely through admission semaphore without exceeding 250 MiB process RSS.
- **Acceptance Criteria**: 100% contract compatibility with frontend spatial viewer; all existing M03–M05 unit tests remain green.
- **Risks**: Serialization overhead of large spatial grid coordinates (> 10,000 cells) into JSON.
- **Estimated Effort**: 3 days.

---

### Milestone B4 — Data Quality, Formula Graph & Defect Scanner Service

- **Scope**:
  - Connect static formula dependency graph (`FormulaGraph`), Tarjan cycle detector, and content anomaly triage to `/api/v1/workbooks/{id}/quality/findings` and `/api/v1/workbooks/{id}/formulas/graph`.
  - Implement triage aggregator combining structural anomalies, volatile formulas, syntax errors, type ambiguities, and dynamic array spills into unified quality findings.
- **Deliverables**:
  - `excel_intel/server/services/quality_service.py`
  - `excel_intel/server/routers/quality.py`
  - `excel_intel/server/routers/formulas.py`
  - `tests/server/test_quality_api.py`
- **Dependencies**: B3 discovery service, `excel_intel/formulas/`.
- **Files/Modules Affected**: `excel_intel/server/services/`, `excel_intel/server/routers/`.
- **Test Requirements**:
  - Triage correctly reports formula cycles with Tarjan SCC node lists.
  - Volatile functions (`NOW`, `TODAY`) are flagged with info severity.
  - Emitted `QualityAuditReport` exactly matches `frontend/src/contracts/quality.ts`.
- **Acceptance Criteria**: Zero regression against existing formula graph tests; JSON responses format in $< 50\text{ ms}$ for typical workbooks.
- **Risks**: Very large formula calculation graphs (> 50,000 nodes) overflowing JSON serializer depth.
- **Estimated Effort**: 2 days.

---

### Milestone B5 — Schema Mapping & Recommendation Engine

- **Scope**:
  - Implement candidate column mapping recommendation service (`POST /api/v1/schema-mapping/recommendations`).
  - Implement exact header matching, normalized token matching, and semantic type compatibility scoring.
  - Provide master schema target catalog (`GET /api/v1/schema-mapping/targets`).
  - Implement `OperationPlan` synthesizer assembling declarative canonical operations (`APPEND_ROWS`, `INSERT_ROW`, `UPDATE_CELL`, `EXTEND_TABLE`, `PROPAGATE_FORMULA`).
- **Deliverables**:
  - `excel_intel/server/services/mapping_service.py`
  - `excel_intel/server/routers/mapping.py`
  - `tests/server/test_mapping_api.py`
- **Dependencies**: B3 spatial/type discovery services, `excel_intel.core.types.OperationPlan`.
- **Files/Modules Affected**: `excel_intel/server/services/`, `excel_intel/server/routers/`.
- **Test Requirements**:
  - Candidate recommendation matches frontend `MappingCandidate` contract.
  - Synthesized `OperationPlan` conforms to SAD Section 14 declarative JSON schema.
  - Benchmark test verifies candidate recommendation generation for 500 column pairs in $< 50\text{ ms}$.
- **Acceptance Criteria**: Domain-agnostic operation; zero hardcoded column names; air-gap invariant strictly verified.
- **Risks**: Heuristic ambiguity resolution when multiple source columns share similar normalized names.
- **Estimated Effort**: 3 days.

---

### Milestone B6 — Server-Side Approval Authority & SQLite Audit Ledger

- **Scope**:
  - Implement the 7-state approval state machine (`DRAFT`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `NEEDS_REVISION`, `EXPIRED`, `CANCELLED`).
  - Implement server-side risk classifier (non-destructive, overwrite/replacement, destructive).
  - Implement `HMACAuthority`: issue HMAC-SHA256 tokens upon approval with 900s TTL; enforce single-use nonces in SQLite.
  - Implement SQLite append-only cryptographic audit ledger (`AuditBlockRecord`) with parent SHA-256 hash chains.
  - Expose `/api/v1/approvals` and `/api/v1/audit` endpoints.
- **Deliverables**:
  - `excel_intel/server/services/approval_service.py`
  - `excel_intel/server/services/audit_service.py`
  - `excel_intel/server/routers/approvals.py`
  - `excel_intel/server/routers/audit.py`
  - `tests/server/test_approvals_and_audit_api.py`
- **Dependencies**: B1 SQLite database, B5 OperationPlan model.
- **Files/Modules Affected**: `excel_intel/server/services/`, `excel_intel/server/routers/`.
- **Test Requirements**:
  - Replay attack rejection test: reusing an approval token nonce fails with `409 CONFLICT`.
  - Expired token test: token timestamp $> 900\text{s}$ fails validation.
  - Server-side cryptographic hash-chain verification (`verify-chain`) catches tampered payloads and broken parent links.
- **Acceptance Criteria**: Decisions submitted from frontend are recorded; approved plans produce valid HMAC tokens; audit chain is cryptographically sound.
- **Risks**: SQLite database locking during concurrent approval decisions under high concurrency.
- **Estimated Effort**: 3 days.

---

### Milestone B7 — Deterministic 6-Phase WAL Execution Engine & End-to-End Integration

- **Scope**:
  - Implement OpenXML pass-through mutation writer: copy unmodified ZIP parts verbatim (VBA macros, themes, charts, styles); stream-mutate target worksheet XML and table dimensions.
  - Implement the physical 6-phase WAL sequence (`PRE_STATE_SNAPSHOT`, `WAL_INTENT_RECORDED`, `STAGED_MUTATION_FSYNC`, `ATOMIC_REPLACE`, `PARENT_DIR_SYNC`, `WAL_COMMITTED`).
  - Implement OS-level atomic replacement (`MoveFileExW` on Windows, `rename()` on POSIX) and parent directory flush.
  - Implement emergency abort and crash recovery (`startup_recovery`).
  - Connect live frontend to backend, replacing all development MSW handlers.
- **Deliverables**:
  - `excel_intel/server/services/execution_service.py`
  - `excel_intel/server/services/openxml_writer.py`
  - `excel_intel/server/routers/execution.py`
  - `tests/server/test_execution_wal_e2e.py`
- **Dependencies**: B1 through B6.
- **Files/Modules Affected**: `excel_intel/server/services/`, `excel_intel/server/routers/`.
- **Test Requirements**:
  - End-to-end execution of `OperationPlan` against real `.xlsx` workbooks.
  - Power-interruption / crash recovery test: verifies recovery restores `.bak` if mutation is incomplete.
  - External modification detection: engine refuses to overwrite externally modified files.
  - Semantic preservation test: VBA macros, charts, styles, and custom XML parts remain 100% intact after mutation.
- **Acceptance Criteria**: Full end-to-end consolidation workflow operates cleanly from frontend UI through live backend to physical disk with zero data loss.
- **Risks**: Antivirus / Windows Defender handle locks interfering with `MoveFileExW`.
- **Estimated Effort**: 4 days.

---

## 3. Summary Schedule & Resource Allocation

| Milestone | Title | Focus Area | Dependencies | Est. Days |
|:---:|---|---|:---:|:---:|
| **B1** | Backend Foundation & FastAPI Shell | Web server, SQLite WAL, RFC 7807, health | M01 | 2 |
| **B2** | Workbook Staging & File Management | Secure upload, quota check, zip-bomb defense | B1, Rust zip | 2 |
| **B3** | Spatial Discovery & Manifest API | REST bridges for M03, M04, M05 | B2, M03–M05 | 3 |
| **B4** | Data Quality & Defect Scanner | Formula cycles, anomaly triage | B3, M05-P4 | 2 |
| **B5** | Schema Mapping & Recommendation Engine | Heuristic matching, OperationPlan | B3 | 3 |
| **B6** | Server Approval Authority & Audit Ledger | HMAC tokens, replay defense, SQLite audit | B1, B5 | 3 |
| **B7** | 6-Phase WAL Execution & E2E Integration | OpenXML writer, atomic replace, full E2E | B1–B6 | 4 |
| **Total**| **Complete Backend Integration Workstream** | | | **19 Days** |
