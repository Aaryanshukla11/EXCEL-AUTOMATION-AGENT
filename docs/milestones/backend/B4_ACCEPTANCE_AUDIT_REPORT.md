# MILESTONE B4 ACCEPTANCE AUDIT REPORT — FORMULA INTELLIGENCE & DATA QUALITY AUDIT SERVICE

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration  
**Milestone Audited:** B4 — Formula Intelligence & Data Quality Audit Service  
**Auditor:** Principal Backend Auditor & Security Verification Engineer  
**Date:** 2026-11-24  
**Final Decision:** `B4_ACCEPTED_WITH_DOCUMENTED_LIMITATIONS`  

---

## 1. Executive Summary & Audit Scope

An independent forensic acceptance audit of **Milestone B4 (Formula Intelligence & Data Quality Audit Service)** was conducted against the canonical specifications in [`docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md) Section 3.4, [`docs/architecture/BACKEND_ARCHITECTURE_PLAN.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/BACKEND_ARCHITECTURE_PLAN.md), and the implementation claims set forth in [`docs/milestones/backend/B4_IMPLEMENTATION_REPORT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/milestones/backend/B4_IMPLEMENTATION_REPORT.md).

### Audit Scope:
- Source code inspection:
  - [`excel_intel/server/services/quality_service.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/quality_service.py)
  - [`excel_intel/server/routers/quality.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/routers/quality.py)
  - [`excel_intel/server/services/discovery_service.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/discovery_service.py)
  - [`excel_intel/server/dependencies.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/dependencies.py)
  - [`excel_intel/server/app.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/app.py)
  - [`tests/server/test_quality_api.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/server/test_quality_api.py)
- Domain model and contract inspection:
  - `frontend/src/contracts/formulas.ts` & `frontend/src/contracts/quality.ts`
  - `excel_intel/formulas/models.py` & `excel_intel/formulas/graph.py`
  - `excel_intel/inspection/models.py`, `excel_intel/spatial/models.py`, `excel_intel/types/models.py`
- Integration and regression verification:
  - Formula dependency graph extraction, cycle detection, volatile cells, and completeness tracking.
  - Consolidated data quality audit across all 7 defect categories.
  - B3 regression audit on manifest, inspection, spatial, and semantic types endpoints.
  - Admission controller gating, memory limits, and non-blocking thread offloading.
  - Independent execution of full test suites (Python unit/server/core, Rust engine, TypeScript frontend).

---

## 2. Verified Implementation Capabilities

The audit confirms that Milestone B4 correctly orchestrates and exposes the underlying M03, M04, and M05 intelligence engines:

1. **Formula Calculation Graph (`FormulaDependencyGraph`):**
   - AST tokenization and operator-precedence parsing for standard OpenXML formula expressions.
   - Directed acyclic graph construction tracking directed precedent $\rightarrow$ dependent relationships.
   - Tarjan's Strongly Connected Components (SCC) algorithm for deterministic circular reference cycle detection.
   - Identification of exact circular calculation paths (`circular_paths: list[list[str]]`).
   - Cataloging of volatile functions (`volatile_cells`) recalculated on workbook changes (e.g., `NOW`, `TODAY`, `RAND`, `OFFSET`, `INDIRECT`).
   - Tracking of unsupported functions/syntax (`unsupported_cells`), unparsed formulas (`unparsed_cells`), and unresolved dependencies (`unresolved_dependencies`).
   - Detection of dynamic array spill references (`has_dynamic_spills`).
   - Explicit completeness guard (`is_complete: bool`) with explanatory diagnostic reasons (`incompleteness_reasons: list[str]`).
2. **Consolidated Data Quality Audit (`QualityService`):**
   - Evidence-backed findings aggregation across four distinct subsystems:
     - **M03 Inspection**: Top-level and sheet-level OpenXML structural anomalies (`StructuralAnomaly`).
     - **M04 Spatial Detector**: Boundary clearance violations and margin append collisions (`MARGIN_APPEND_COLLISION`).
     - **M05 Type Inference**: Ambiguous semantic column profiles, review requirements, and unverified type states (`TYPE_AMBIGUOUS`, `TYPE_UNKNOWN`).
     - **M05 Formula Graph**: Critical calculation cycles, unsupported formula constructs, unparsed formula syntax errors, unresolved calculation dependencies, volatile recalculations, and dynamic array spills.
   - Header resolution mapping: Links column type anomalies with resolved hierarchical header names (`disambiguated_name` / `resolved_name`) from `SpatialTableRegion.header_resolution.columns`.
   - Blank / null cell handling: Blank and empty cells are not automatically classified as defects; nullability ratios are tracked without generating spurious defect findings.
3. **Architectural & Resource Guardrails:**
   - Both `/formulas/graph` and `/quality/findings` are gated behind `admission_controller.acquire(task_name=...)`.
   - Memory pressure thresholds trigger `HTTP 429 ADMISSION_REJECTED` with `Retry-After: 5`.
   - Heavy parsing and graph analysis are dispatched to `asyncio.to_thread(...)`, keeping the ASGI event loop unblocked.
   - Strict path sanitization ensures physical host storage paths are never leaked in responses.
   - Multi-tenant isolation filters queries by `tenant_id == "default"`, returning `HTTP 404` for unauthorized resources.
   - Zero workbook mutation: All inspection and graph operations are purely read-only via `StreamingWorkbookReader`.

---

## 3. Endpoint-by-Endpoint Verification Results

| Endpoint | Method | Expected Status | Verified Status | RFC 7807 Error | Sensitive Paths Redacted |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `/api/v1/workbooks/{workbook_id}/formulas/graph` | `GET` | 200 OK | 200 OK | Yes (`404 RESOURCE_NOT_FOUND`, `429 ADMISSION_REJECTED`) | Yes (Redacted) |
| `/api/v1/workbooks/{workbook_id}/quality/findings` | `GET` | 200 OK | 200 OK | Yes (`404 RESOURCE_NOT_FOUND`, `429 ADMISSION_REJECTED`) | Yes (Redacted) |

### Detailed Findings:

#### 1. `GET /api/v1/workbooks/{workbook_id}/formulas/graph`
- **Response Schema:** Conforms 1:1 with `frontend/src/contracts/formulas.ts` (`FormulaGraphReport`).
- **Graph Metrics:** Verified on test workbooks. Valid formulas (e.g., `SUM(...)`) produce `node_count >= 1`, `edge_count >= 1`, `has_cycles: False`, `cycle_status: "NO_CYCLES"`, and `is_complete: True`.
- **Cycle Detection:** Mutually recursive formulas (`A1 = B1 + 1`, `B1 = A1 * 2`) produce `has_cycles: True`, `cycle_status: "CYCLES_DETECTED"`, and `circular_paths` containing the exact cycle paths.
- **Volatiles:** Functions such as `NOW()` and `RAND()` are correctly populated in `volatile_cells`.
- **Incomplete Graph Invariant:** Verified that `is_complete` remains `False` when formulas fail parsing or external dependencies cannot be resolved, strictly fulfilling the rule that incomplete graphs are never represented as verified complete.

#### 2. `GET /api/v1/workbooks/{workbook_id}/quality/findings`
- **Response Schema:** Conforms 1:1 with `frontend/src/contracts/quality.ts` (`QualityAuditReport`).
- **Report Metadata:** Contains unique `report_id` (UUID), sanitized `workbook_path` (filename only), `total_findings == len(findings)`, and embedded `formula_graph`.
- **Defect Categories Verified:**
  - `formula_cycle`: Severity is set to `AnomalySeverity.CRITICAL`, code is `"CIRCULAR_REFERENCE_CYCLE"`, and `details` contains the full cycle path.
  - `volatile_function`: Severity is set to `AnomalySeverity.INFO`, code is `"VOLATILE_FUNCTION_CALL"`.
  - `structural_anomaly`: Correctly imports top-level and sheet-level anomalies from M03 inspection and M04 margin clearance collisions.
  - `type_ambiguity`: Correctly tags ambiguous columns with `AnomalySeverity.WARNING` and unverified columns with `AnomalySeverity.INFO`.
- **Path Leakage:** Verified that no storage root, host drive letter, or temporary directory substring is present in JSON response serialization.

---

## 4. B3 Regression Audit

Because Milestone B4 introduced `analyze_formulas` onto `DiscoveryService` in [`excel_intel/server/services/discovery_service.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/discovery_service.py), a complete regression check of B3 discovery endpoints was conducted:

| B3 Endpoint | Verified Status | Result |
| :--- | :---: | :--- |
| `GET /api/v1/workbooks/{id}/manifest` | 200 OK | Manifest synthesis combining spatial tables, types, and formula graph functions identically to B3 baseline. |
| `GET /api/v1/workbooks/{id}/inspection` | 200 OK | Topology facts, merge cells, defined names, and dimensions remain intact. |
| `GET /api/v1/workbooks/{id}/sheets/{sheet}/spatial` | 200 OK | 2D whitespace corridors, semantic zones, and margin clearances remain intact. |
| `GET /api/v1/workbooks/{id}/sheets/{sheet}/types` | 200 OK | Column profiles, sampling diagnostics, and region filtering remain intact. |

All 13 integration tests in [`tests/server/test_discovery_api.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/server/test_discovery_api.py) passed cleanly in 7.28s with zero regressions.

---

## 5. Security and Architecture Audit

1. **Multi-Tenancy & Authorization:**
   - Both B4 endpoints resolve workbook records using `StagedWorkbookRecord.tenant_id == "default"`.
   - Access attempts against records belonging to foreign tenants (`tenant_beta`) return `HTTP 404 RESOURCE_NOT_FOUND`.
2. **Admission Controller & Memory Guard:**
   - Concurrency semaphore and process RSS checks are evaluated before workbook parsing begins.
   - Forcing memory threshold saturation (`ctrl._throttle_threshold_mb = 0.0`) immediately yields `HTTP 429 ADMISSION_REJECTED` with `Retry-After: 5` header and RFC 7807 problem details.
3. **Event Loop Responsiveness:**
   - Asynchronous endpoints delegate synchronous `openpyxl` / Rust streaming operations to worker threads via `asyncio.to_thread`. The ASGI event loop remains free to serve health probes (`/health/live`, `/health/ready`).
4. **Information Hiding:**
   - Response payloads replace internal staging paths (e.g. `C:\Users\...\b4_storage\UUID\model.xlsx`) with `sanitized_filename` (e.g. `model.xlsx`).
5. **Core Engine Immutability:**
   - Frozen M01–M05 core directories (`excel_intel/core/`, `excel_intel/spatial/`, `excel_intel/types/`, `excel_intel/formulas/`, `excel_intel/inspection/`, `crates/excel_intel_rs/`) and frontend components (`frontend/src/`) were not modified.

---

## 6. Forensic Investigation of Implementation Issues

During development of B4, an initial integration failure was identified and resolved:
- **Issue:** Task `task-4711` encountered `AttributeError: 'HeaderResolutionReport' object has no attribute 'resolved_columns'` during quality audit of tables with resolved headers.
- **Root Cause Analysis:** The M04 domain model `HeaderResolutionReport` stores columns in attribute `columns: list[ResolvedHeaderColumn]`, where each column object has `disambiguated_name` and `resolved_name`. The initial implementation incorrectly referenced `resolved_columns` and `canonical_header`.
- **Resolution:** Updated `excel_intel/server/services/quality_service.py` to iterate over `target_reg.header_resolution.columns` and use `matched_col.disambiguated_name or matched_col.resolved_name`.
- **Verification:** Re-executed test suite in `task-4755` and subsequent runs; all 11 tests passed cleanly.

---

## 7. Independent Test Verification Evidence

All test suites were independently executed and captured:

### 1. Focused B4 Integration Tests
```powershell
Set-Location "C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2"
py -3.12 -m pytest tests/server/test_quality_api.py -v
```
- **Exit Code:** `0`
- **Output:**
```text
============================= test session starts =============================
platform win32 -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2
configfile: pyproject.toml
plugins: anyio-4.3.0, asyncio-1.4.0
collected 11 items

tests\server\test_quality_api.py ...........                             [100%]

============================= 11 passed in 5.86s ==============================
```

### 2. Complete Server Test Suite
```powershell
Set-Location "C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2"
py -3.12 -m pytest tests/server -v
```
- **Exit Code:** `0`
- **Output:**
```text
============================= test session starts =============================
collected 62 items

tests\server\test_admission.py ....                                      [  6%]
tests\server\test_alembic_migrations.py .                                [  8%]
tests\server\test_database.py .......                                    [ 19%]
tests\server\test_discovery_api.py .............                         [ 40%]
tests\server\test_errors.py ......                                       [ 50%]
tests\server\test_health_and_ready.py .......                            [ 61%]
tests\server\test_quality_api.py ...........                             [ 79%]
tests\server\test_workbooks_api.py .............                         [100%]

======================= 62 passed, 3 warnings in 22.66s =======================
```

### 3. Full Python Regression Test Suite
```powershell
Set-Location "C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2"
py -3.12 -m pytest -q
```
- **Exit Code:** `0`
- **Output:**
```text
........................................................................ [ 16%]
........................................................................ [ 33%]
........................................................................ [ 50%]
........................................................................ [ 67%]
........................................................................ [ 84%]
................................................................         [100%]
424 passed, 3 warnings in 23.51s
```

### 4. Rust Engine Test Suite
```powershell
Set-Location "C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2"
cargo test --manifest-path crates/excel_intel_rs/Cargo.toml
```
- **Exit Code:** `0`
- **Output:**
```text
running 60 tests
test result: ok. 60 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 1.66s
```

### 5. Frontend TypeScript Verification
```powershell
Set-Location "C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2\frontend"
npm run typecheck
```
- **Exit Code:** `0`
- **Output:**
```text
> excel-intel-frontend@0.1.0 typecheck
> tsc --noEmit
```

---

## 8. Documented Limitations

The following non-blocking design limitations are noted for Milestone B4:

1. **Formula Parsing Scope:** Formula AST parsing is performed on formulas present in the OpenXML `<f>` element. Inlined calculation engines (e.g., custom VBA macros or external COM add-ins) are outside the OpenXML formula graph scope and are correctly reported as unparsed/unsupported cells.
2. **Quality Audit Multi-Pass Execution:** `QualityService.audit_workbook_quality` runs sequential passes over the streaming reader (inspection, spatial detection, type inference, and formula extraction). For massive workbooks near the 250 MiB limit, batching these passes or caching intermediate structural facts will provide future throughput optimization in Milestone B7.
3. **Starlette Deprecation Warnings:** 3 minor Starlette deprecation warnings (`HTTP_422_UNPROCESSABLE_ENTITY` and `HTTP_413_REQUEST_ENTITY_TOO_LARGE`) are emitted in error tests due to Starlette's upcoming status code naming updates. These do not affect functionality.

---

## 9. Current Git Status

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
	modified:   .gitignore
	modified:   docs/milestones/m05/M05_FINAL_CLOSURE_REPORT.md
	modified:   docs/milestones/m05/M05_PROMPT_4_EVIDENCE_REPORT.md
	modified:   pyproject.toml

Untracked files:
	alembic.ini
	alembic/
	docs/architecture/BACKEND_ARCHITECTURE_PLAN.md
	docs/architecture/BACKEND_CAPABILITY_AUDIT.md
	docs/architecture/BACKEND_MILESTONE_ROADMAP.md
	docs/architecture/FRONTEND_ARCHITECTURE_PLAN.md
	docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md
	docs/milestones/backend/
	docs/milestones/frontend/
	excel_intel/server/
	frontend/
	tests/server/
```

- M01–M05 milestone branches (`m01`, `m02`, `m03`, `m04`, `m05`) have been created and pushed to `origin`.
- Pre-existing uncommitted changes in `.gitignore` and `docs/milestones/m05/` have been strictly preserved.

---

## 10. Final Decision

Based on the verified dynamic evidence, contract matching, comprehensive defect triage, non-blocking execution, and zero regressions across all 424 Python tests, 60 Rust tests, and frontend typecheck:

```text
B4_ACCEPTED_WITH_DOCUMENTED_LIMITATIONS
```

*Audit complete. Stopping as instructed and awaiting operator authorization before further work or starting Milestone B5.*
