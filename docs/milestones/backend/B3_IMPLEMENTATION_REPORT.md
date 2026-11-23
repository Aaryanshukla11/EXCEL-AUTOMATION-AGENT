# MILESTONE B3 IMPLEMENTATION REPORT — SPATIAL DISCOVERY & SEMANTIC MANIFEST API

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration  
**Milestone:** B3 — Spatial Discovery & Semantic Manifest API  
**Date:** 2026-11-23  
**Final Status:** `B3_IMPLEMENTATION_COMPLETE — READY_FOR_ACCEPTANCE_AUDIT`  

---

## 1. Executive Summary

Milestone **B3** exposes the deterministic spreadsheet intelligence capabilities established in core milestones **M03 (Structural Inspection)**, **M04 (Spatial Detection)**, and **M05 (Semantic Type Inference & Formula Dependency Graph)** through production-quality FastAPI services and RESTful endpoints conforming strictly to Section 3.3 of [`FRONTEND_BACKEND_API_CONTRACT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md).

All four canonical discovery endpoints have been implemented without altering frozen M01–M05 core algorithms or F0–F5 frontend components. Heavy workbook processing is mediated by the B1 `AdmissionController` semaphore and memory guards, preserving the 250 MiB process RSS ceiling.

---

## 2. Files Created and Modified

### Created Files:
1. [`excel_intel/server/services/discovery_service.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/discovery_service.py)
   - Unified discovery facade coordinating `WorkbookInspector`, `SpatialDetector`, `TypeInferenceEngine`, `FormulaDependencyGraph`, and `build_discovery_manifest`.
   - Enforces information hiding by stripping internal filesystem paths and emitting sanitized public identifiers.
2. [`excel_intel/server/routers/discovery.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/routers/discovery.py)
   - Fast-API router mounted under `/api/v1/workbooks/{workbook_id}`.
   - Implements endpoints for manifest synthesis, structural inspection, worksheet spatial regions, and semantic types.
3. [`tests/server/test_discovery_api.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/server/test_discovery_api.py)
   - 13 comprehensive integration tests covering successful discovery, empty workbooks, missing workbooks/sheets, invalid regions, admission throttling, tenant isolation, and sensitive path sanitization.

### Modified Files:
1. [`excel_intel/server/dependencies.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/dependencies.py)
   - Added dependency provider `get_discovery_service(request: Request) -> DiscoveryService`.
2. [`excel_intel/server/app.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/app.py)
   - Registered `DiscoveryService` in application lifespan state.
   - Included `discovery_router` under `config.api_prefix` (`/api/v1`).

---

## 3. Endpoints Implemented

Conforms to [`docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md) Section 3.3:

| Endpoint | Method | Response Model | HTTP Status | Description |
| :--- | :---: | :--- | :---: | :--- |
| `/api/v1/workbooks/{workbook_id}/manifest` | `GET` | `DiscoveryManifest` | `200 OK` | Synthesizes root canonical manifest losslessly unifying spatial tables, types, and formula graph. |
| `/api/v1/workbooks/{workbook_id}/inspection` | `GET` | `WorkbookInspectionReport` | `200 OK` | Emits package topology facts, dimensions, merge cells, defined names, and anomalies. |
| `/api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/spatial` | `GET` | `List[SpatialTableRegion]` | `200 OK` | Returns 2D whitespace corridor regions, semantic zones (Title, Header, Body, Summary), and ADR-005 margin clearances. |
| `/api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/types` | `GET` | `RegionTypeReport` | `200 OK` | Returns semantic type profiles, nullability ratios, heuristic support scores, and sampling diagnostics. Supports optional query param `?region_id=...`. |

---

## 4. Existing Algorithms Reused

No core logic was duplicated or rewritten. B3 acts strictly as an orchestration and REST serialization layer over the frozen core:

- **M03 Workbook Inspection:** Reuses [`WorkbookInspector`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/inspection/inspector.py) for package properties, sheet topology, declared OpenXML facts (`DeclaredOpenXmlFacts`), and content anomaly detection.
- **M04 Spatial Detection:** Reuses [`SpatialDetector`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/spatial/detector.py) (`detect_sheet`, `detect_workbook`, `export_to_table_metadata_list`) for 2D corridor segmentation, hierarchical header resolution, and ADR-005 boundary evaluation.
- **M05 Type Inference:** Reuses [`TypeInferenceEngine`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/types/type_inferrer.py) (`infer_sheet`, `infer_region`) for sampling cell values in `SemanticZoneType.BODY` and computing discrete inference states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`).
- **M05 Formula Dependency Graph:** Reuses [`FormulaDependencyGraph`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/formulas/graph.py) and AST parser for static formula dependency tracking, volatile function cataloging, and cycle evaluation.
- **M01 / M05 Manifest Synthesis:** Reuses [`build_discovery_manifest`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/adapters/manifest_adapter.py) to assemble the canonical `DiscoveryManifest` model.

---

## 5. Tests Executed and Exact Results

### 5.1 Server Test Suite (B1 + B2 + B3)
- **Command:** `py -3.12 -m pytest tests/server -v`
- **Result:** **51 passed, 0 failed, 3 warnings in 13.05s** (Exit Code: `0`)
- **Key B3 Tests:**
  - `test_get_manifest_success` -> PASSED
  - `test_get_manifest_missing_workbook_404` -> PASSED
  - `test_get_inspection_success` -> PASSED
  - `test_get_inspection_missing_workbook_404` -> PASSED
  - `test_get_sheet_spatial_regions_success` -> PASSED
  - `test_get_sheet_spatial_missing_sheet_404` -> PASSED
  - `test_get_sheet_region_types_success` -> PASSED
  - `test_get_sheet_region_types_with_region_id_filter` -> PASSED
  - `test_discovery_admission_control_throttling` -> PASSED (HTTP 429 + `Retry-After: 5`)
  - `test_get_manifest_empty_sheet` -> PASSED (0 tables, 0 formula nodes)
  - `test_get_sheet_types_empty_sheet` -> PASSED (clean empty report)
  - `test_tenant_isolation_cannot_access_foreign_tenant_workbook` -> PASSED (404)
  - `test_no_internal_paths_leaked_in_any_response` -> PASSED (clean sanitization)

### 5.2 Full Python Regression Suite (M01–M05 + B1–B3)
- **Command:** `py -3.12 -m pytest -q`
- **Result:** **413 passed, 0 failed, 3 warnings in 9.87s** (Exit Code: `0`)

### 5.3 Rust Engine Test Suite (M01/M02)
- **Command:** `cargo test --manifest-path crates/excel_intel_rs/Cargo.toml`
- **Result:** **60 passed, 0 failed in 0.89s** (Exit Code: `0`)

### 5.4 Frontend Typing & Contract Alignment (F0–F5)
- **Command:** `cd frontend && npm run typecheck`
- **Result:** **0 errors (clean)** (Exit Code: `0`)

---

## 6. Failed Commands and Actual Exit Codes During Implementation

During development, two initial unit test failures were encountered and immediately resolved:
1. `test_get_manifest_success`: Raised `TypeError: SpatialDetector.detect_workbook() got an unexpected keyword argument 'reader'`. Fixed by passing `reader` as the positional first argument `reader_or_path`.
2. `test_get_sheet_spatial_regions_success`: Raised `KeyError: 'start_row'` because `SpatialTableRegion.bounding_box` uses `min_row` (from `excel_intel.inspection.models.BoundingBox`), whereas the test asserted `start_row`. Fixed test assertion to inspect `min_row`.

Both fixes were verified and all 51 tests subsequently passed.

---

## 7. Security and Architectural Observations

1. **Information Hiding & Path Sanitization:**
   - Raw disk storage paths (`${STORAGE_ROOT}/staging/...`) are stripped prior to response serialization. `report.workbook_path` is sanitized to the client filename or `{workbook_id}.xlsx`.
2. **Memory Protection & Admission Gating:**
   - All four endpoints enter `admission_controller.acquire(task_name=...)`. Under memory pressure ($\ge 180.0\text{ MB}$) or slot saturation, requests are rejected with HTTP 429 `ADMISSION_REJECTED` and header `Retry-After: 5`, preserving the 250 MiB process RSS ceiling.
3. **Non-Blocking Threadpool Execution:**
   - CPU-bound parsing and FFI calls are dispatched via `asyncio.to_thread(...)`, preventing event-loop starvation for health probes and concurrent endpoints.
4. **Tenant Isolation:**
   - In accordance with the B1/B2 architecture, workbook lookups enforce `tenant_id == "default"`. Cross-tenant lookups fail with HTTP 404 `RESOURCE_NOT_FOUND`.

---

## 8. Known Limitations

1. **Single Tenant Workspace Context:** Tenancy remains bound to `"default"` pending future user authentication milestones (B6/B7).
2. **Region-Level vs Sheet-Level Types:** `GET /workbooks/{id}/sheets/{sheet}/types` returns the primary region's type report by default, or accepts `?region_id=...` for specific regions. Multi-region aggregation can be extended in future milestones if required.

---

## 9. Git Status and Uncommitted Changes

Preserved user files remain untouched:
- `M .gitignore`
- `M docs/milestones/m05/M05_FINAL_CLOSURE_REPORT.md`
- `M docs/milestones/m05/M05_PROMPT_4_EVIDENCE_REPORT.md`
- `M pyproject.toml`

New/modified backend files for B3:
- `excel_intel/server/services/discovery_service.py` (new)
- `excel_intel/server/routers/discovery.py` (new)
- `tests/server/test_discovery_api.py` (new)
- `excel_intel/server/dependencies.py` (modified)
- `excel_intel/server/app.py` (modified)

No changes were made to `excel_intel/core/`, `excel_intel/spatial/`, `excel_intel/types/`, `excel_intel/formulas/`, `excel_intel/inspection/`, `crates/`, or `frontend/`.

---

## 10. Final Milestone Recommendation

```text
================================================================================
FINAL STATUS: B3_IMPLEMENTATION_COMPLETE — READY_FOR_ACCEPTANCE_AUDIT
================================================================================
```

Awaiting operator authorization for the independent acceptance audit of Milestone B3. Milestone B4 remains blocked.
