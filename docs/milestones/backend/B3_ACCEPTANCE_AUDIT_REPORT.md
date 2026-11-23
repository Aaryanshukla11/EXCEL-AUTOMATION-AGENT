# MILESTONE B3 ACCEPTANCE AUDIT REPORT — SPATIAL DISCOVERY & SEMANTIC MANIFEST API

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration  
**Milestone Audited:** B3 — Spatial Discovery & Semantic Manifest API  
**Auditor:** Principal Backend Auditor & Security Verification Engineer  
**Date:** 2026-11-23  
**Final Decision:** `B3_ACCEPTED_WITH_DOCUMENTED_LIMITATIONS`  

---

## 1. Executive Summary & Audit Scope

An independent forensic acceptance audit of **Milestone B3 (Spatial Discovery & Semantic Manifest API)** was conducted against the canonical specifications in [`docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md) Section 3.3, [`docs/architecture/BACKEND_ARCHITECTURE_PLAN.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/BACKEND_ARCHITECTURE_PLAN.md), and the implementation claims set forth in [`docs/milestones/backend/B3_IMPLEMENTATION_REPORT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/milestones/backend/B3_IMPLEMENTATION_REPORT.md).

### Audit Scope:
- Complete inspection of discovery service orchestration: [`excel_intel/server/services/discovery_service.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/discovery_service.py).
- Verification of FastAPI routing and parameter handling: [`excel_intel/server/routers/discovery.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/routers/discovery.py).
- Verification of dependency injection and application lifespan: [`excel_intel/server/dependencies.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/dependencies.py) and [`excel_intel/server/app.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/app.py).
- Verification of frozen core integration (M03 `WorkbookInspector`, M04 `SpatialDetector`, M05 `TypeInferenceEngine`, M05 `FormulaDependencyGraph`, and `build_discovery_manifest`).
- Verification of Pydantic v2 schemas against TypeScript contracts in `frontend/src/contracts/`.
- Dynamic verification of memory admission throttling, tenancy constraints, information hiding, and edge-case resilience (circular references, merged cells, empty sheets, missing physical files).

---

## 2. Verified Implementation Capabilities

The audit confirmed that B3 successfully wraps the deterministic spreadsheet intelligence core:
1. **Workbook Inspection (M03):** Extracts declared OpenXML facts (`dimensions`, `merge_cells`, `declared_tables`, `defined_names`, `calc_pr`) and structural anomalies via `WorkbookInspector`.
2. **Spatial Detection (M04):** Performs 2D whitespace corridor segmentation, hierarchical header resolution, semantic zone classification (Title, Header, Body, Summary, Totals, Footnotes), and ADR-005 margin clearance via `SpatialDetector`.
3. **Semantic Type Inference (M05):** Samples values strictly within `SemanticZoneType.BODY` of discovered regions and calculates discrete states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`) and bounded heuristic support scores via `TypeInferenceEngine`.
4. **Formula Dependency Graph (M05):** Constructs calculation dependency graphs, catalogs volatile functions, and detects circular reference cycles via Tarjan's SCC cycle detector in `FormulaDependencyGraph`.
5. **Canonical Manifest Synthesis (M01 / M05):** Projects verified types and spatial regions losslessly into `DiscoveryManifest` via `build_discovery_manifest`.
6. **Bounded Resource Utilization:** All discovery operations are mediated by the B1 `AdmissionController` semaphore and memory guards, preserving the 250 MiB process RSS ceiling.
7. **Strict Information Hiding:** Response payloads are sanitized so that internal host directories, drive letters, and staging storage paths are never leaked to API callers.

---

## 3. Endpoint-by-Endpoint Contract Results

| Endpoint | Method | Expected Status | Implemented Status | RFC 7807 on Error | Sensitive Paths Leaked |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `/api/v1/workbooks/{workbook_id}/manifest` | `GET` | 200 OK | 200 OK | Yes (`404 RESOURCE_NOT_FOUND`, `429 ADMISSION_REJECTED`) | None (Sanitized) |
| `/api/v1/workbooks/{workbook_id}/inspection` | `GET` | 200 OK | 200 OK | Yes (`404 RESOURCE_NOT_FOUND`, `429 ADMISSION_REJECTED`) | None (Sanitized) |
| `/api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/spatial` | `GET` | 200 OK | 200 OK | Yes (`404 RESOURCE_NOT_FOUND`, `429 ADMISSION_REJECTED`) | None (Sanitized) |
| `/api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/types` | `GET` | 200 OK | 200 OK | Yes (`404 RESOURCE_NOT_FOUND`, `429 ADMISSION_REJECTED`) | None (Sanitized) |

### Contract Details & Findings:

#### 1. `GET /api/v1/workbooks/{workbook_id}/manifest`
- **Payload Conformity:** Validated against `frontend/src/contracts/discovery.ts`. Returns `manifest_id` (UUID), `workbook_path` (sanitized filename), `sha256` (64-char hex), `file_size_bytes`, `tables` (array of `TableMetadata`), and `formula_graph` (`FormulaGraphMetadata`).
- **Formula Graph Investigation:** The manifest exposes `node_count`, `edge_count`, `has_cycles`, and `volatile_cells`. Audit verified that circular formulas correctly toggle `has_cycles: True`. Deep graph diagnostic lists (`circular_paths`, `unparsed_cells`, `unresolved_dependencies`) are omitted from this top-level summary, strictly adhering to the M01 `DiscoveryManifest` specification; they are scheduled for full exposure in Milestone B4.

#### 2. `GET /api/v1/workbooks/{workbook_id}/inspection`
- **Payload Conformity:** Validated against `excel_intel/inspection/models.py`. Returns `package_type`, `is_1904`, `has_macros`, `calc_pr`, `defined_names`, `sheets` (with `DeclaredOpenXmlFacts`, merge cells, dimensions), and `workbook_anomalies`.
- **Sanitization:** `workbook_path` is sanitized to the client filename or `{workbook_id}.xlsx`, preventing directory exposure.

#### 3. `GET /api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/spatial`
- **Payload Conformity:** Validated against `frontend/src/contracts/spatial.ts`. Returns `SpatialTableRegion[]` with `bounding_box` (`min_row`, `max_row`, `min_col`, `max_col`), `region_type`, `heuristic_confidence`, `zones`, and `margin`.
- **Missing Sheet Handling:** Requesting an invalid sheet name returns HTTP 404 (`RESOURCE_NOT_FOUND`) with informative error detail. Empty worksheets return `[]` with HTTP 200 OK.

#### 4. `GET /api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/types`
- **Payload Conformity:** Validated against `frontend/src/contracts/types.ts`. Returns `RegionTypeReport` with `region_id`, `sheet_name`, body coordinates, `columns` map (`ColumnTypeProfile`), and `sampling` diagnostics.
- **Region Filtering:** Correctly filters by query parameter `?region_id=...`. If omitted on a sheet with multiple regions, defaults to the primary region. Empty worksheets return a valid default `RegionTypeReport` with `columns: {}` and `sampled_rows: 0`.

---

## 4. Security and Resource Audit

### 4.1 Tenancy & Ownership
- All queries strictly enforce `tenant_id == "default"`.
- Forensically verified: Workbooks reassigned in the database to `tenant_id="foreign_tenant_xyz"` return HTTP 404 `RESOURCE_NOT_FOUND` across all 4 discovery endpoints.
- Unauthenticated clients cannot override or spoof `tenant_id`.

### 4.2 Information Hiding & Path Traversal
- Responses from all four endpoints were analyzed for internal path substrings (`C:\`, `Users`, storage directory name). No filesystem paths, disk mount points, or staging directory structures are leaked.
- Missing physical files on disk (even if registered in SQLite) return HTTP 404 `RESOURCE_NOT_FOUND` without exposing server paths.

### 4.3 Admission Control & Concurrency Protection
- All endpoints acquire `admission_controller.acquire(task_name=...)`.
- Simulated memory pressure ($\ge 180.0\text{ MB}$) correctly returns HTTP 429 `ADMISSION_REJECTED` with header `Retry-After: 5` and RFC 7807 problem details.
- Parsing and analysis run in the Python threadpool via `asyncio.to_thread(...)`, keeping the asyncio event loop responsive for concurrent requests and health checks.

---

## 5. Functional Integration Evidence on Diverse Workbook Structures

Dynamic integration probes were executed against complex workbook structures in [`run_b3_audit_probes.py`](file:///c:/Users/Aaryan%20shukla/.gemini/antigravity/brain/be106fff-805b-4a35-847d-7e56945a2036/scratch/run_b3_audit_probes.py):

1. **Multi-Sheet Workbook with Merged Cells:**
   - Sheet 1 contained merged header cells (`A1:B1`).
   - `GET /inspection` accurately extracted `merge_cells: 1` in `facts`.
2. **Circular Formula Calculation Cycle:**
   - Sheet 2 contained circular dependencies (`A1 = B1 + 1`, `B1 = A1 + 1`) and unsupported functions (`UNSUPPORTED_FN_XYZ()`).
   - `GET /manifest` executed cleanly, evaluated calculation cycles, and populated `has_cycles: True` without throwing unhandled exceptions.
3. **Empty Worksheet:**
   - Sheet 3 contained 0 rows and 0 cells.
   - `GET /sheets/Empty/spatial` returned `[]` (HTTP 200 OK).
   - `GET /sheets/Empty/types` returned clean empty report with `columns: {}` (HTTP 200 OK).
4. **Deleted Physical File / Inconsistent State:**
   - Physical `.xlsx` file deleted from disk while record persisted in SQLite.
   - `GET /manifest` returned HTTP 404 `RESOURCE_NOT_FOUND` ("Staged workbook file for ID ... is missing from storage").

---

## 6. Test Execution Evidence

All test suites were independently executed and verified:

### 6.1 Server Test Suite (B1 + B2 + B3)
- **Command:** `py -3.12 -m pytest tests/server -v`
- **Result:** **51 passed, 0 failed, 3 warnings in 14.30s** (Exit Code: `0`)

### 6.2 Full Python Regression Suite (M01–M05 + B1–B3)
- **Command:** `py -3.12 -m pytest -q`
- **Result:** **413 passed, 0 failed, 3 warnings in 9.94s** (Exit Code: `0`)

### 6.3 Rust Core Engine Suite (M01/M02)
- **Command:** `cargo test --manifest-path crates/excel_intel_rs/Cargo.toml`
- **Result:** **60 passed, 0 failed in 1.14s** (Exit Code: `0`)

### 6.4 Frontend Typecheck Suite (F0–F5)
- **Command:** `cd frontend && npm run typecheck`
- **Result:** **0 errors (clean)** (Exit Code: `0`)

---

## 7. Defect Register

| Defect ID | Severity | Component | Description & Impact | Recommendation |
| :--- | :---: | :--- | :--- | :--- |
| **B3-OBS-01** | Low | `services/discovery_service.py:147` | When a worksheet has multiple table regions and `?region_id=...` is omitted, `infer_sheet_types` returns the primary region. Secondary regions require explicit `?region_id=...`. | Add multi-region array endpoint in future milestone if frontend requires all regions simultaneously. |
| **B3-OBS-02** | Info | `routers/discovery.py:38` | Tenancy context is hardcoded to `"default"`. Awaits user authentication in Milestone B7. | Implement JWT tenancy context in B7. |
| **B3-OBS-03** | Info | `services/discovery_service.py:228` | Manifest `FormulaGraphMetadata` exposes summary stats (`node_count`, `edge_count`, `has_cycles`, `volatile_cells`); detailed cycle paths remain deferred to B4. | Expose full `FormulaGraphReport` via `/api/v1/workbooks/{id}/formulas/graph` in B4. |

---

## 8. Frozen-Component Preservation Verification

- **M01–M05 Core:** Verified untouched. No edits in `excel_intel/core/`, `spatial/`, `types/`, `formulas/`, `inspection/`, or `crates/`.
- **F0–F5 Frontend:** Verified untouched. No edits in `frontend/`. TypeScript strict typecheck passed with 0 errors.
- **B1 / B2 Foundation:** Lifespan, middlewares, Alembic migrations, database models, and workbook staging endpoints remain intact.

---

## 9. Final Acceptance Decision

```text
================================================================================
FINAL DECISION: B3_ACCEPTED_WITH_DOCUMENTED_LIMITATIONS
================================================================================
```

### Rationale:
Milestone B3 satisfies all architectural and functional requirements defined in the B0 architecture plan and API contract. It exposes the deterministic capabilities of M03, M04, and M05 over standard REST interfaces, maintains process memory bounds via admission control, sanitizes internal host paths, and passes all 413 Python tests, 60 Rust tests, and frontend typechecks without regression. The documented observations (default single-region selection on multi-region sheets, single-tenant default context, and summary formula metadata in manifest) are consistent with the milestone roadmap and do not block platform evolution.

---

## 10. Recommended Next Action

Milestone B3 is formally accepted.

**Exact Next Action:**  
Awaiting explicit operator authorization to proceed to **Milestone B4: Formulas & Data Quality Audit Service** (exposing `FormulaGraphReport` and Data Quality findings aggregation under `/api/v1/workbooks/{id}/formulas/graph` and `/api/v1/workbooks/{id}/quality/findings`).
