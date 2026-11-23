# BACKEND ARCHITECTURE & CAPABILITY AUDIT (MILESTONE B0)

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration (B0–B7)  
**Date:** 2026-11-23  
**Auditor / Architect:** Autonomous Backend Architecture Sentinel  
**Status:** COMPLETE — REVISED & HARMONIZED AUDIT BASELINE

---

## 1. Executive Summary

Frontend milestones **F0 through F5** are formally accepted, frozen, and verified across all 9 application routes. The frontend currently operates against an in-memory Mock Service Worker (MSW) harness and mock adapter layer.

The existing backend consists of:
1. **Deterministic Rust Engine (`crates/excel_intel_rs`)**: A high-performance, memory-bounded OpenXML parsing engine with PyO3 bindings (`_rs.pyd`), featuring streaming worksheet parsing, LRU-managed shared strings cache with disk spill, IEEE 754 floating-point serial date conversion, zip decompression bomb guards, and scratch file memory management (60/60 unit tests passing).
2. **Python Core Engine (`excel_intel/`)**: Milestones M01 through M05 established core domain models, streaming readers, workbook inspection facades (M03), 2D spatial table region detection (M04), semantic type inference (M05), formula AST parsing with Tarjan SCC cycle detection (M05 Prompt 4), and canonical `DiscoveryManifest` synthesis adapters (362/362 pytest suites passing).
3. **Missing Integration Layer**: There is currently **zero HTTP / REST / WebSocket service layer**. Downstream execution engines (6-phase WAL, physical atomic replacement), Cognitive Orchestration (semantic schema mapping), Server-Side HMAC approval token issuance, and SQLite audit ledger persistence exist strictly as abstract Python `Protocol` interfaces without concrete implementations.

This document provides a line-by-line capability audit of what exists, what is stubbed, and the exact delta required to connect the backend to the production frontend.

---

## 2. Complete Inventory of Existing Backend (`excel_intel/` & `crates/`)

### 2.1 Rust Deterministic Core (`crates/excel_intel_rs/`)
The Rust crate provides memory safety, uncompressed byte limits, and streaming XML performance. Compiled into `excel_intel/_rs.pyd` via Maturin / PyO3:

| Rust Module | Implementation Status | Concrete Capabilities | Missing / Gaps |
|---|:---:|---|---|
| `cell_validator.rs` | **COMPLETE** | Validates UTF-8 / UTF-16 byte boundaries, rejects buffer overflow attempts, checks cell coordinate syntax. | None. |
| `dates.rs` | **COMPLETE** | Converts Excel serial numbers to ISO 8601 strings; handles 1900 and 1904 calendar systems; handles the historical 1900 leap year bug (serial 60.0). | None. |
| `error.rs` | **COMPLETE** | Custom Rust error types mapped to Python exceptions (`ZipBombError`, `MemoryCeilingError`, `CellValidationError`). | None. |
| `memory_guard.rs` | **COMPLETE** | OS-level working set memory tracking on Windows (`GetProcessMemoryInfo`); enforces soft ceiling (235 MiB) and hard ceiling (250 MiB). | None. |
| `scratch.rs` | **COMPLETE** | Process-isolated scratch bin creation (`0600` permissions), PID lock scavenging, atomic scratch file creation. | Fsync and directory sync are local to scratch; no atomic replacement into target destination. |
| `shared_strings.rs`| **COMPLETE** | 2-tier shared strings cache: Tier 1 in-memory LRU arena (40-byte slots), Tier 2 memory-mapped disk spill file; 2M entry ceiling; generation counter overflow defense. | Read-only; does not write new shared strings to disk. |
| `styles.rs` | **COMPLETE** | Parses cell XF records and number formatting strings (`numFmtId`). | Complex custom currency/locale format strings not fully evaluated. |
| `worksheet.rs` | **COMPLETE** | Low-level streaming pull-parser for `sheetN.xml` using `quick-xml`; zero DOM buffering; streams raw cell coordinates, types, values, and formulas. | Read-only parser; no streaming XML writer implemented in Rust. |
| `zip_handler.rs` | **COMPLETE** | Secure OpenXML ZIP reader; compression ratio quota (100:1); cumulative quota (1 GiB); member count limit (10,000 files); path traversal prevention (`..`). | Read-only; no ZIP packaging/writer engine in Rust. |

### 2.2 Python Backend Packages (`excel_intel/`)

| Package / Module | Implementation Status | Concrete Capabilities | Gaps / Missing Components |
|---|:---:|---|---|
| `core/parser.py` | **COMPLETE** | `StreamingWorkbookReader`: Coordinates Rust `_rs` parser, extracts package metadata, defined names, sheet dimensions, and cell iterators. | Read-only; no mutation or write capability. |
| `core/types.py` | **COMPLETE** | Frozen Pydantic v2 schemas: `DiscoveryManifest`, `TableMetadata`, `ColumnMetadata`, `BoundingBox`, `FormulaGraphMetadata`, `OperationPlan`, `ApprovalToken`, `ExecutionReport`, `AuditBlock`. | Data models only; no persistence or serialization engines. |
| `inspection/` | **COMPLETE** | `WorkbookInspector` (M03 facade), `PackageStructureInspector`, `SheetTopologyInspector`, `ContentDistributionProfiler`, `ContentAnomalyDetector`. | Inspects topology, dimensions, and layout classification; generates `WorkbookInspectionReport`. |
| `spatial/` | **COMPLETE** | `SpatialDetector` (M04 facade), `GridSegmenter` (2D whitespace corridors), `HeaderResolver` (hierarchical headers), `ZoneClassifier` (6 zones), `BoundarySentinel` (ADR-005 margin clearance). | Emits `SpatialDetectionReport`; exports tables to `TableMetadata`. |
| `types/` | **COMPLETE** | `TypeInferenceEngine` (M05 facade), `PatternDetector`, `sampling.py` (10,000 cell budget). Classifies semantic types, nullability, pattern frequencies. | Emits `RegionTypeReport`; projects to `ColumnType`. |
| `formulas/` | **COMPLETE** | `FormulaParser`, `FormulaLexer`, `CycleDetector` (Tarjan SCC), `FormulaGraph` (M05 Prompt 4). Detects cycles, volatile functions, dynamic array spill anchors. | Emits `FormulaGraphReport`. Does not evaluate runtime cell values. |
| `adapters/` | **COMPLETE** | `manifest_adapter.py`: Synthesizes root `DiscoveryManifest` by unifying M04 spatial tables, M05 semantic types, and M05 formula graphs. | In-memory adapter only. |
| `execution/` | **STUBBED (Protocols)** | `interfaces.py`: `ShadowEngineProtocol`, `HMACAuthorityProtocol`, `TransactionManagerProtocol`, `AuditLedgerProtocol`. | **Zero concrete implementations.** No physical WAL writer, no atomic replacement, no HMAC token signer. |
| `cognitive/` | **STUBBED (Protocols)** | `interfaces.py`: `CognitiveOrchestratorProtocol`. | **Zero concrete implementations.** No field mapping algorithm, no LLM provider connector, no OperationPlan generator. |
| `ui/` | **STUBBED (Protocols)** | `interfaces.py`: `DiffPresenterProtocol`. | Abstract protocol only; CLI output is placeholder. |
| `cli.py` | **PARTIAL** | Command dispatcher with `validate-config`. Subcommands `inspect`, `plan`, `apply`, `rollback`, `audit` exist as CLI stubs. | No execution or API daemon dispatch. |
| `config.py` & `logging.py` | **COMPLETE** | Pydantic configuration loader (`PlatformConfig`), structured JSON/text logging conforming to SAD Section 13.2. | Local environment loading only; no dynamic client config injection. |

---

## 3. Forensic Frontend Integration Mapping

This matrix maps every frontend operation currently serviced by Mock Service Worker (`frontend/src/mocks/handlers.ts`) or mock adapters (`*Adapter.ts`) to backend capabilities.

| # | Frontend Operation / Route | MSW Endpoint / Adapter Call | Capability Status | Existing Backend Module | Canonical API Route | Delta / Missing Implementation |
|---|---|---|:---:|---|---|---|
| **1** | Staging: File Upload | `stagingStore.ts` (in-memory `File`) | `[NEW_SERVICE_REQUIRED]` | `core/parser.py` (reads paths only) | `POST /api/v1/workbooks/upload` | Multipart file upload endpoint, temporary spooling, disk quota verification, virus/magic-byte scan. |
| **2** | Staging: Queue Inventory | Local state | `[NEW_SERVICE_REQUIRED]` | None | `GET /api/v1/workbooks` | Session/tenant workbook registry, file metadata store, staging inventory service. |
| **3** | Overview & Manifest | `GET /api/v1/manifest` | `[CORE_IMPLEMENTED]` | `adapters/manifest_adapter.py` | `GET /api/v1/workbooks/{id}/manifest` | REST endpoint wrapping `build_discovery_manifest` for staged workbook. |
| **4** | Spatial: Workbook Topology | `GET /api/v1/spatial/discovery` | `[CORE_IMPLEMENTED]` | `inspection/inspector.py` | `GET /api/v1/workbooks/{id}/inspection` | REST endpoint exposing `WorkbookInspector.inspect_workbook()`. |
| **5** | Spatial: Sheet Regions | `GET /api/v1/spatial` | `[CORE_IMPLEMENTED]` | `spatial/detector.py` | `GET /api/v1/workbooks/{id}/sheets/{sheet}/spatial` | REST endpoint exposing `SpatialDetector.detect_sheet()`. |
| **6** | Semantic Types | `GET /api/v1/types` | `[CORE_IMPLEMENTED]` | `types/type_inferrer.py` | `GET /api/v1/workbooks/{id}/sheets/{sheet}/types` | REST endpoint exposing `TypeInferenceEngine.infer_sheet()`. |
| **7** | Formula Graph & DAG | `GET /api/v1/formulas/dag`<br>`GET /api/v1/formulas/graph` | `[CORE_IMPLEMENTED]` | `formulas/graph.py` | `GET /api/v1/workbooks/{id}/formulas/graph` | REST endpoint exposing `FormulaGraph.build_graph()` and cycle reports. |
| **8** | Schema Mapping: Targets | `GET /api/v1/schema-mapping/targets` | `[NEW_SERVICE_REQUIRED]` | `core/types.py` (`TableMetadata`) | `GET /api/v1/schema-mapping/targets` | Stored master workbook catalog or target schema database table. |
| **9** | Schema Mapping: Candidates | `GET /api/v1/schema-mapping/candidates` | `[NEW_SERVICE_REQUIRED]` | `cognitive/interfaces.py` (Protocol) | `POST /api/v1/schema-mapping/recommendations` | Heuristic & semantic column recommendation service (token, fuzzy, type matchers). |
| **10**| Quality Audit Findings | `GET /api/v1/quality/findings` | `[CORE_IMPLEMENTED]` | `inspection/anomaly_detector.py` & `formulas/graph.py` | `GET /api/v1/workbooks/{id}/quality/findings` | Aggregation service combining structural anomalies, formula cycles, and type sparsity. |
| **11**| Client Settings | `GET /api/v1/config/client` | `[NEW_SERVICE_REQUIRED]` | `config.py` (`PlatformConfig`) | `GET /api/v1/config/client`<br>`PUT /api/v1/config/client` | Schema mapping between frontend `ClientConfig` and backend settings; persistent tenant config store. |
| **12**| Approval Queue | `GET /api/v1/approvals`<br>`GET /api/v1/approvals/:id` | `[DATA_MODEL_ONLY]` | `core/types.py` (`OperationPlan`, `ApprovalToken`) | `GET /api/v1/approvals`<br>`GET /api/v1/approvals/{id}` | Approval request repository, plan risk classification engine, SQLite storage. |
| **13**| Approval Decision | `DecisionActionDialog.tsx` | `[NEW_SERVICE_REQUIRED]` | `execution/interfaces.py` (`HMACAuthorityProtocol`) | `POST /api/v1/approvals/{id}/decision` | Server-side decision recorder, state machine transition validator, HMAC token generator. |
| **14**| Execution: Job Queue | `GET /api/v1/execution/jobs`<br>`GET /api/v1/execution/jobs/:id` | `[DATA_MODEL_ONLY]` | `core/types.py` (`ExecutionReport`) | `GET /api/v1/execution/jobs`<br>`GET /api/v1/execution/jobs/{id}` | Job lifecycle queue, state tracking (`PREPARING`, `EXECUTING`, `COMMITTED`, `ROLLED_BACK`). |
| **15**| Execution: Run WAL Pipeline| `executionAdapter.ts` (`runSimulatedJob`) | `[FUTURE_EXECUTION_REQUIRED]` | `execution/interfaces.py` (`TransactionManagerProtocol`) | `POST /api/v1/execution/jobs/{id}/run` | Physical 6-phase WAL engine: byte snapshot `.bak`, journal append, scratch mutation, Win32/POSIX atomic replace, parent dir sync. |
| **16**| Execution: Emergency Abort | `POST /api/v1/execution/jobs/:id/rollback` | `[FUTURE_EXECUTION_REQUIRED]` | `execution/interfaces.py` (`TransactionManagerProtocol`) | `POST /api/v1/execution/jobs/{id}/rollback` | Physical rollback engine restoring pre-state `.bak` file, releasing locks. |
| **17**| Audit Ledger Blocks | `GET /api/v1/audit/blocks` | `[DATA_MODEL_ONLY]` | `core/types.py` (`AuditBlock`) | `GET /api/v1/audit/blocks` | SQLite audit block repository with monotonic indexing. |
| **18**| Audit Chain Verification | `POST /api/v1/audit/verify-chain` | `[NEW_SERVICE_REQUIRED]` | `execution/interfaces.py` (`AuditLedgerProtocol`) | `POST /api/v1/audit/verify-chain` | Server-side cryptographic SHA-256 chain verification engine. |

---

## 4. Architectural Gap Analysis

### 4.1 What Exists and is Production-Ready (Core Engine Tier)
1. **Low-Level Extraction & Bounded Safety**: Rust `quick-xml` reader safely parses massive OpenXML workbooks without exceeding the 250 MiB memory ceiling.
2. **Structural Inspection (M03)**: Deterministic facts (calcPr, defined names, hidden sheets/rows, merge cells, content density) are fully implemented.
3. **Spatial Segmentation (M04)**: Hierarchical header resolution, 2D island clustering, and zone classification are mature and heavily tested.
4. **Semantic Inference (M05)**: 10,000-cell bounded statistical sampling, nullability ratios, regex pattern detection, and heuristic support scores function reliably.
5. **Formula Static Graph (M05 Prompt 4)**: Formula AST lexer/parser, Tarjan SCC cycle detector, volatile function tracker, and range hyperedge expansion operate deterministically.

### 4.2 What is Missing and Must Be Built (Service & Execution Tier)
1. **Web Service Application Layer**: No HTTP server framework is present. FastAPI with Uvicorn must be established (Milestone B1).
2. **File Staging & Storage Management**: No server-side directory structure exists for receiving uploaded files, managing isolated scratch directories, storing `.bak` snapshots, or archiving committed workbooks (Milestone B2).
3. **Cognitive / Recommendation Engine**: Frontend Module 4 (`/schema-studio`) expects column mapping candidate recommendations. Backend currently lacks token, normalized string, and semantic matchers between source and target manifests (Milestone B5).
4. **Operation Plan Generator**: No module translates user mapping drafts into declarative `OperationPlan` contracts (`APPEND_ROWS`, `INSERT_ROW`, `UPDATE_CELL`, `EXTEND_TABLE`, `PROPAGATE_FORMULA`) (Milestone B5).
5. **Human-in-the-Loop Approval Authority**: No server-side engine validates risk classifications, manages the 7-state approval state machine, stores decisions in SQLite, or generates cryptographic HMAC-SHA256 tokens (Milestone B6).
6. **Physical Write-Ahead Logging & Atomic Replacement**: No OpenXML writer or physical file mutator exists. The 6-phase WAL protocol (`PRE_STATE_SNAPSHOT`, `WAL_INTENT_RECORDED`, `STAGED_MUTATION_FSYNC`, `ATOMIC_REPLACE`, `PARENT_DIR_SYNC`, `WAL_COMMITTED`) must be implemented via pass-through OpenXML package streaming (Milestone B7).
7. **Durable Audit Ledger**: No persistent append-only database stores historical audit blocks or validates cryptographic hash chains on disk (Milestone B6).

---

## 5. Risk Assessment & Integration Constraints

1. **Memory Budget Boundary**: The Rust core enforces a 250 MiB process RSS cap. Concurrent workbook parsing must be serialized via admission control semaphores (`asyncio.Semaphore(1)`).
2. **Untrusted Uploads**: All uploaded `.xlsx` files must be treated as hostile inputs subject to compression bomb inspection, XML entity expansion guards, and temporary disk quotas before parsing begins.
3. **Approval vs. Execution Non-Bypass**: The backend must never execute any mutation without a cryptographically verified `ApprovalToken` tied to the exact SHA-256 hash of the `OperationPlan`. Mock approvals must never be accepted by the physical execution engine.
4. **Air-Gap Invariant**: The Cognitive Orchestration layer (LLM or recommendation heuristics) must remain strictly air-gapped from physical filesystem persistence (ADR-006).
