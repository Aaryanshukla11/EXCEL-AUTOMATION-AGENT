# FRONTEND-BACKEND CANONICAL API CONTRACT SPECIFICATION (MILESTONE B0)

**Project:** Autonomous Excel Intelligence Platform  
**Version:** 1.0.0 (API v1 Canonical Specification)  
**Status:** FROZEN SPECIFICATION — SOURCE OF TRUTH  
**Auditor / Architect:** Autonomous Backend Architecture Sentinel  

---

## 1. Overview & Architectural Principles

This document establishes the authoritative, canonical HTTP API contract bridging the accepted frontend (**Milestones F0–F5**) and the backend service layer (**Milestones B0–B7**).

### 1.1 Source of Truth
- **Frontend Source of Truth**: TypeScript contract interfaces in `frontend/src/contracts/` (`discovery.ts`, `spatial.ts`, `types.ts`, `formulas.ts`, `mapping.ts`, `quality.ts`, `approval.ts`, `execution.ts`, `auditLedger.ts`, `config/clientConfig.ts`).
- **Backend Source of Truth**: Pydantic v2 domain models in `excel_intel.core.types`, `excel_intel.spatial.models`, `excel_intel.types.models`, `excel_intel.formulas.models`, and `excel_intel.inspection.models`.

### 1.2 Capability Classification Taxonomy
Every endpoint and operation in this specification is explicitly classified under one of four discrete capability states:
1. `[CORE_IMPLEMENTED]`: Underlying deterministic engine is fully implemented, verified, and tested in `excel_intel` or `crates/excel_intel_rs`. Requires only thin REST router exposure.
2. `[DATA_MODEL_ONLY]`: Pydantic data schemas and contract types are established and frozen, but business service logic remains to be implemented.
3. `[NEW_SERVICE_REQUIRED]`: Requires authoring new backend service logic, storage managers, or recommendation heuristics.
4. `[FUTURE_EXECUTION_REQUIRED]`: Requires physical OpenXML package mutation, 6-phase WAL write barriers, or atomic OS replacement (Milestone B7).

---

## 2. Global Error Handling Specification (RFC 7807)

All non-2xx responses strictly conform to RFC 7807 Problem Details for HTTP APIs:

```json
{
  "type": "https://excel-intel.internal/errors/INVARIANT_VIOLATION",
  "title": "Invariant Violation",
  "status": 422,
  "detail": "Cannot overwrite formula cell at Revenue!C14 without explicit override authorization.",
  "instance": "/api/v1/execution/jobs/JOB-101/run",
  "code": "FORMULA_OVERWRITE_DISALLOWED",
  "correlation_id": "req-9f8a-42c1-b76e",
  "timestamp": "2026-11-23T15:30:00Z"
}
```

### Standard Error Codes
| HTTP Status | Error Code | Description |
|:---:|---|---|
| `400` | `INVALID_PAYLOAD` | Malformed JSON or request syntax error. |
| `400` | `INVALID_FILE_TYPE` | Uploaded file is not `.xlsx` or `.xlsm`. |
| `400` | `ZIP_BOMB_DETECTED` | Compression ratio > 100:1 or uncompressed size > 1 GiB. |
| `401` | `UNAUTHENTICATED` | Missing or invalid authentication credentials. |
| `403` | `UNAUTHORIZED_OPERATOR` | Caller lacks permission or role for the requested operation. |
| `404` | `RESOURCE_NOT_FOUND` | Target workbook, request, job, or sheet does not exist. |
| `409` | `STATE_CONFLICT` | Invalid state machine transition or lock collision. |
| `422` | `SCHEMA_VALIDATION_ERROR` | Pydantic schema validation failure on input. |
| `422` | `INVARIANT_VIOLATION` | Operation violates deterministic pre-conditions (e.g. formula overwrite). |
| `429` | `ADMISSION_REJECTED` | Memory reservation limit reached; worker throttled. |
| `500` | `INTERNAL_DURABILITY_FAULT` | Physical I/O or filesystem synchronization failure. |

---

## 3. Canonical Endpoint Registry

### 3.1 System Health & Configuration

#### `GET /api/v1/health`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B1)
- **Description**: Returns server liveness, memory telemetry, and version.
- **Auth**: None (Public/Internal)
- **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "version": "0.1.0",
    "env": "development",
    "max_rss_mb": 250,
    "current_rss_mb": 52.4,
    "active_parsing_jobs": 0,
    "admission_semaphore_available": 1
  }
  ```

#### `GET /api/v1/config/client`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B1)
- **Description**: Retrieves client configuration, branding, theme, and terminology.
- **Auth**: Authenticated Principal (Default in dev mode)
- **Response `200 OK`**: Matches frontend `ClientConfig` contract.

#### `PUT /api/v1/config/client`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B1)
- **Description**: Updates client configuration with strict Pydantic validation.
- **Auth**: Admin Role
- **Request Body**: `ClientConfig` JSON.
- **Response `200 OK`**: Updated `ClientConfig`.

---

### 3.2 Workbook Management & Staging

#### `POST /api/v1/workbooks/upload`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B2)
- **Description**: Multipart upload of `.xlsx` / `.xlsm` workbook. Performs magic-byte inspection (`PK\x03\x04`), quota check, and Rust zip-bomb validation.
- **Auth**: Operator Role
- **Request**: `multipart/form-data`, file key `file`.
- **Response `201 Created`**:
  ```json
  {
    "workbook_id": "wb-550e8400-e29b-41d4-a716-446655440000",
    "filename": "financial_model_q4.xlsx",
    "file_size_bytes": 1458200,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "staged_at": "2026-11-23T15:30:00Z",
    "package_type": "xlsx",
    "has_macros": false,
    "status": "staged"
  }
  ```

#### `GET /api/v1/workbooks`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B2)
- **Description**: Returns list of all staged workbooks within the tenant's workspace.
- **Auth**: Viewer Role
- **Response `200 OK`**: Array of `StagedWorkbook` objects.

#### `GET /api/v1/workbooks/{workbook_id}`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Wrapped in Milestone B2)
- **Description**: Retrieves detailed workbook catalog, sheet names, package properties.
- **Auth**: Viewer Role
- **Response `200 OK`**: Detailed workbook summary.

#### `DELETE /api/v1/workbooks/{workbook_id}`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B2)
- **Description**: Removes staged workbook from disk and unregisters from SQLite.
- **Auth**: Operator Role
- **Response `204 No Content`**

---

### 3.3 Inspection, Spatial Discovery & Manifest Synthesis

#### `GET /api/v1/workbooks/{workbook_id}/manifest`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Exposed in Milestone B3)
- **Underlying Module**: `excel_intel.adapters.manifest_adapter.build_discovery_manifest`
- **Description**: Emits the root canonical `DiscoveryManifest` losslessly unifying spatial tables, semantic types, and formula graph metadata.
- **Auth**: Viewer Role
- **Response `200 OK`**: Matches frontend `DiscoveryManifest` contract.

#### `GET /api/v1/workbooks/{workbook_id}/inspection`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Exposed in Milestone B3)
- **Underlying Module**: `excel_intel.inspection.inspector.WorkbookInspector` (M03)
- **Description**: Returns workbook topology facts, declared tables, merge cells, dimensions, and anomalies.
- **Auth**: Viewer Role
- **Response `200 OK`**: Matches frontend `WorkbookDiscoveryResult` contract.

#### `GET /api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/spatial`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Exposed in Milestone B3)
- **Underlying Module**: `excel_intel.spatial.detector.SpatialDetector` (M04)
- **Description**: Returns detected 2D tabular regions, semantic zones (Title, Header, Body, Summary, Totals, Footnotes), and ADR-005 margin clearances for a worksheet.
- **Auth**: Viewer Role
- **Response `200 OK`**: Matches frontend `SpatialTableRegion[]` contract.

#### `GET /api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/types`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Exposed in Milestone B3)
- **Underlying Module**: `excel_intel.types.type_inferrer.TypeInferenceEngine` (M05)
- **Description**: Returns semantic type profiles, nullability, pattern frequencies, and heuristic confidence scores for a worksheet's body cells.
- **Auth**: Viewer Role
- **Response `200 OK`**: Matches frontend `RegionTypeReport` contract.

---

### 3.4 Formulas & Data Quality Audit

#### `GET /api/v1/workbooks/{workbook_id}/formulas/graph`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Exposed in Milestone B4)
- **Underlying Module**: `excel_intel.formulas.graph.FormulaGraph` (M05 Prompt 4)
- **Description**: Static dependency graph analysis, Tarjan SCC circular reference cycle detection, volatile functions, and dynamic array spill anchors.
- **Auth**: Viewer Role
- **Response `200 OK`**: Matches frontend `FormulaGraphReport` contract.

#### `GET /api/v1/workbooks/{workbook_id}/quality/findings`
- **Capability Status**: `[CORE_IMPLEMENTED]` (Aggregated in Milestone B4)
- **Underlying Modules**: `excel_intel.inspection.anomaly_detector`, `excel_intel.formulas.graph`
- **Description**: Comprehensive triage across all 5 defect categories: Structural Anomalies, Volatile Functions, Unsupported Formulas, Type Ambiguities, Dynamic Array Spills.
- **Auth**: Viewer Role
- **Response `200 OK`**: Matches frontend `QualityAuditReport` contract.

---

### 3.5 Schema Mapping Studio

#### `GET /api/v1/schema-mapping/targets`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B5)
- **Description**: Returns catalog of available Master workbook schemas and consolidation targets.
- **Auth**: Viewer Role
- **Response `200 OK`**: Array of target schema models.

#### `POST /api/v1/schema-mapping/recommendations`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B5)
- **Description**: Generates automated column mapping candidate recommendations using normalized token matching, exact header matching, and semantic type compatibility heuristics.
- **Auth**: Operator Role
- **Request Body**:
  ```json
  {
    "source_workbook_id": "wb-550e8400",
    "source_sheet": "Revenue",
    "target_id": "master_target_1"
  }
  ```
- **Response `200 OK`**: Array of `MappingCandidate` matching frontend contract.

---

### 3.6 Human-in-the-Loop Approvals

#### `GET /api/v1/approvals`
- **Capability Status**: `[DATA_MODEL_ONLY]` (Service required in Milestone B6)
- **Description**: Lists pending, approved, and historical approval requests.
- **Auth**: Viewer / Operator / Approver Role
- **Response `200 OK`**: Array of `ApprovalRequest` matching frontend contract.

#### `GET /api/v1/approvals/{request_id}`
- **Capability Status**: `[DATA_MODEL_ONLY]` (Service required in Milestone B6)
- **Description**: Retrieves full approval request with operation plan diffs, risk assessment, and decision history.
- **Auth**: Viewer / Operator / Approver Role
- **Response `200 OK`**: Single `ApprovalRequest`.

#### `POST /api/v1/approvals/{request_id}/decision`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B6)
- **Description**: Records an operator's approval, rejection, or revision decision. If approved, issues a cryptographically signed HMAC-SHA256 `ApprovalToken`.
- **Auth**: Approver Role (Strict Server-Side Validation)
- **Request Body**:
  ```json
  {
    "decision": "APPROVED",
    "rationale": "Verified column mapping and schema integrity for Q4 revenue.",
    "expected_version": 1
  }
  ```
- **Response `200 OK`**: Updated `ApprovalRequest` including issued `approval_token`.

---

### 3.7 Execution & WAL Durability Monitor

#### `GET /api/v1/execution/jobs`
- **Capability Status**: `[DATA_MODEL_ONLY]` (Service required in Milestone B7)
- **Description**: Lists active and completed execution jobs.
- **Auth**: Operator Role
- **Response `200 OK`**: Array of `ExecutionJob` matching frontend contract.

#### `GET /api/v1/execution/jobs/{job_id}`
- **Capability Status**: `[DATA_MODEL_ONLY]` (Service required in Milestone B7)
- **Description**: Retrieves detailed 6-phase WAL execution telemetry and post-flight verification data.
- **Auth**: Operator Role
- **Response `200 OK`**: Single `ExecutionJob`.

#### `POST /api/v1/execution/jobs/{job_id}/run`
- **Capability Status**: `[FUTURE_EXECUTION_REQUIRED]` (Milestone B7)
- **Description**: Initiates physical 6-phase atomic WAL write sequence. Requires a valid, unexpired, unconsumed HMAC `approval_token`.
- **Auth**: Operator Role
- **Request Body**:
  ```json
  {
    "approval_token": "hmac_sha256_token_string"
  }
  ```
- **Response `202 Accepted`**: Initiates execution task; returns initial job status.

#### `POST /api/v1/execution/jobs/{job_id}/rollback`
- **Capability Status**: `[FUTURE_EXECUTION_REQUIRED]` (Milestone B7)
- **Description**: Triggers emergency abort, halting active mutations and atomically restoring the pre-state `.bak` backup file.
- **Auth**: Operator Role
- **Request Body**:
  ```json
  {
    "reason": "Lock contention detected on shared network drive."
  }
  ```
- **Response `200 OK`**: Updated `ExecutionJob` in `ROLLED_BACK` state.

---

### 3.8 Cryptographic Audit Ledger

#### `GET /api/v1/audit/blocks`
- **Capability Status**: `[DATA_MODEL_ONLY]` (Service required in Milestone B6)
- **Description**: Retrieves sequential audit blocks from the SQLite append-only ledger.
- **Auth**: Viewer / Auditor Role
- **Response `200 OK`**: Array of `AuditBlock` matching frontend contract.

#### `POST /api/v1/audit/verify-chain`
- **Capability Status**: `[NEW_SERVICE_REQUIRED]` (Milestone B6)
- **Description**: Computes server-side cryptographic SHA-256 verification across the full historical block chain.
- **Auth**: Auditor Role
- **Response `200 OK`**:
  ```json
  {
    "is_valid": true,
    "total_blocks": 8,
    "verified_blocks": 8,
    "checked_at": "2026-11-23T15:30:00Z"
  }
  ```
