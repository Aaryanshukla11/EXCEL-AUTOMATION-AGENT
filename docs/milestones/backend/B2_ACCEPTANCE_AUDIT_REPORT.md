# MILESTONE B2 ACCEPTANCE AUDIT REPORT — WORKBOOK STAGING & FILE MANAGEMENT SERVICE

**Project:** Autonomous Excel Intelligence Platform  
**Workstream:** Backend Service Architecture & Integration  
**Milestone Audited:** B2 — Workbook Staging & File Management Service  
**Auditor:** Principal Backend Auditor & Security Verification Engineer  
**Date:** 2026-11-23  
**Final Decision:** `B2_ACCEPTED_WITH_DOCUMENTED_LIMITATIONS`  

---

## 1. Executive Summary

An independent, evidence-based forensic acceptance audit of **Milestone B2 (Workbook Staging & File Management Service)** was conducted against the authoritative architecture plans ([`BACKEND_ARCHITECTURE_PLAN.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/BACKEND_ARCHITECTURE_PLAN.md), [`FRONTEND_BACKEND_API_CONTRACT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md), [`BACKEND_MILESTONE_ROADMAP.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/BACKEND_MILESTONE_ROADMAP.md)) and the implementation claims presented in [`B2_IMPLEMENTATION_REPORT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/milestones/backend/B2_IMPLEMENTATION_REPORT.md).

### Summary of Audit Assessment:
1. **Streaming Upload & Memory Guarantees:** Confirmed. File uploads are streamed directly in 64 KiB chunks from the request body to disk. Process memory overhead remains $O(1) \approx 64\text{ KiB}$, strictly respecting the 250 MiB process RSS ceiling.
2. **Decompression Bomb & Archive Quota Defense:** Confirmed. The preflight inspection of the central directory enforces member limits ($\le 10,000$), uncompressed size ceilings ($\le 1.0\text{ GiB}$), and ratio limits ($\le 10.0\text{x}$ for entries $> 10\text{ MB}$), backed by the Rust OpenXML streaming reader.
3. **Database & Alembic Migration:** Confirmed. Migration `0002_workbook_staging.py` creates table `staged_workbooks` with indexes on `tenant_id` and `sha256`. Alembic remains the sole schema authority; upgrade, downgrade, and re-upgrade cycles executed with 100% fidelity.
4. **API Contract & RFC 7807 Compliance:** Confirmed. Endpoints `POST /api/v1/workbooks/upload`, `GET /api/v1/workbooks`, `GET /api/v1/workbooks/{id}`, and `DELETE /api/v1/workbooks/{id}` conform precisely to the canonical contract. Responses are sanitized with no sensitive server paths exposed.
5. **Frozen Component Integrity:** Confirmed. M01–M05 core, B1 application shell, and F0–F5 frontend components remain intact with zero unauthorized mutations.
6. **Documented Limitations:** Identified five non-critical limitations: Windows drive-letter / colon path traversal patterns in member names; unflagged duplicate member names in ZIP containers; hardcoded single-tenant workspace (`"default"`) pending multi-tenant Auth milestones; filesystem/RDBMS dual-write consistency on unhandled DB commit aborts; and an `Integer` vs `BigInteger` column declaration mismatch.

---

## 2. Files and Components Inspected

| Component | File Path | Scope & Purpose |
| :--- | :--- | :--- |
| **Alembic Migration** | [`alembic/versions/0002_workbook_staging.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/alembic/versions/0002_workbook_staging.py) | Schema definition for `staged_workbooks` and indexes |
| **Database Models** | [`excel_intel/server/database/models.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/database/models.py) | SQLAlchemy DeclarativeBase model `StagedWorkbookRecord` |
| **Storage Service** | [`excel_intel/server/services/storage_service.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/storage_service.py) | 64 KiB chunk streaming, SHA-256, ZIP bomb & signature guards |
| **Workbook Router** | [`excel_intel/server/routers/workbooks.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/routers/workbooks.py) | Upload, inventory listing, retrieval, and deletion endpoints |
| **Error Handlers** | [`excel_intel/server/errors.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/errors.py) | RFC 7807 problem details mapping for B2 error categories |
| **Dependencies** | [`excel_intel/server/dependencies.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/dependencies.py) | DI providers for `StorageService` and transactional `AsyncSession` |
| **Application Factory** | [`excel_intel/server/app.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/app.py) | Lifespan initialization of `StorageService` and router registration |
| **Server Tests** | [`tests/server/test_workbooks_api.py`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/tests/server/test_workbooks_api.py) | 13 integration tests for B2 staging lifecycle and security |

---

## 3. Actual Security Findings

### 3.1 Streaming Multipart Upload & Memory Budget
- **Verification:** Inspected `StorageService.store_uploaded_workbook` (lines 127–151).
- **Behavior:** The file is ingested using `await file.read(64 * 1024)` in a strict loop writing directly to disk (`temp_path`).
- **Memory Consumption:** $O(1)$ memory usage. Starlette buffers up to 1 MiB in `SpooledTemporaryFile` before spilling to disk, meaning the maximum request memory footprint is $\le 1.1\text{ MiB}$, preserving the remaining 248+ MiB process budget for OpenXML parsing and ASGI execution.
- **Quota Enforcement:** `total_bytes > self._max_upload_bytes` triggers an immediate `PlatformResourceLimitError(exit_code=413)` mapped to RFC 7807 `PAYLOAD_TOO_LARGE`.

### 3.2 Signature Verification & Format Rejection
- **Verification:** Evaluated magic-byte checks at lines 156–167.
- **Legacy OLE (`.xls`):** Header `b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"` is detected and rejected with `UnsupportedFormatError` (HTTP 400 `INVALID_FILE_TYPE`).
- **Plaintext & Arbitrary Binaries:** Header checking `header_bytes[:4] != b"PK\x03\x04"` rejects non-ZIP containers immediately (HTTP 400 `INVALID_FILE_TYPE`).
- **Empty Payloads:** 0-byte uploads raise `CorruptWorkbookError("Uploaded workbook file is empty (0 bytes).")` (HTTP 400 `CORRUPT_WORKBOOK`).

### 3.3 Decompression Bomb & Quota Guards
- **Verification:** Central directory preflight inspection at lines 169–199.
- **Member Count Ceiling:** Archives containing $> 10,000$ members raise `ZipBombError` (HTTP 400 `ZIP_BOMB_DETECTED`).
- **Compression Ratio:** Members $> 10\text{ MB}$ with ratio $> 10.0\text{x}$ raise `ZipBombError`.
- **Cumulative Size:** Uncompressed size $> 1.0\text{ GiB}$ raises `ZipBombError`.
- **Rust Engine Integration:** Handled via `StreamingWorkbookReader(temp_path)`. Decompression errors raised by the Rust engine (`RustResourceLimitError`) are mapped to `ZipBombError` (HTTP 400).
- **Encrypted Archives:** Encrypted packages (bit 0x1 set or password protected) are safely rejected as `CorruptWorkbookError` (HTTP 400) because the Rust reader cannot decrypt without credentials.

### 3.4 Archive Member Path Traversal Defense
- **Forensic Test Results:**
  - `../secret.txt`: **REJECTED OK** (`Unsafe archive member path detected: ../secret.txt`)
  - `..\secret.txt`: **REJECTED OK** (`Unsafe archive member path detected: ..\secret.txt`)
  - `/etc/passwd`: **REJECTED OK** (`Unsafe archive member path detected: /etc/passwd`)
  - `\Windows\System32\cmd.exe`: **REJECTED OK** (`Unsafe archive member path detected: \Windows\System32\cmd.exe`)
  - `C:\boot.ini`: **ACCEPTED (See Finding 3.4.1)**
  - `C:/boot.ini`: **ACCEPTED (See Finding 3.4.1)**
- **Finding 3.4.1 (Documented Limitation / Medium):** The path traversal validation at lines 180–183 checks `if ".." in name or name.startswith("/") or name.startswith("\\"):`. Members with Windows drive letters (e.g. `C:\`, `D:/`) or colons (`:`) do not trigger this filter.
  - *Risk Assessment:* **LOW REAL-WORLD IMPACT in B2**. `StorageService` **never extracts** archive members onto disk. Files are kept intact inside the server-named container `{workbook_id}.xlsx`. Hence, no filesystem overwrite (Zip Slip) can occur. However, accepting drive-letter member names violates strict archive sanitization.

### 3.5 Duplicate Archive Member Names
- **Forensic Test Result:** An archive containing duplicate `xl/workbook.xml` entries was staged without error.
- **Finding 3.5.1 (Documented Limitation / Low):** Python's `zipfile` module permits duplicate entry names. While the Rust `StreamingWorkbookReader` reads the first matching entry, parser differential discrepancies between different consumers could theoretically occur.

---

## 4. Database and Storage Integrity Findings

### 4.1 Alembic Migration Lifecycle & Targeted Evidence Check
- **Authority:** Confirmed. Startup `Base.metadata.create_all()` was permanently eliminated during B1 remediation. `DatabaseManager.initialize()` exclusively executes `alembic.command.upgrade(cfg, "head")`.
- **Targeted Evidence Check Command:**
  ```powershell
  Set-Location "C:\Users\Aaryan shukla\OneDrive\Desktop\agent v2"
  py -3.12 "C:\Users\Aaryan shukla\.gemini\antigravity\brain\be106fff-805b-4a35-847d-7e56945a2036\scratch\verify_alembic_cycle.py"
  ```
- **Exit Code:** `0`
- **Captured Terminal Output:**
  ```text
  INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
  INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
  INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial_schema, Initial schema migration: creates system_metadata and schema_migrations tables.
  INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
  INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
  INFO  [alembic.runtime.migration] Running upgrade 0001_initial_schema -> 0002_workbook_staging, Workbook staging schema migration: creates staged_workbooks table.
  INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
  INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
  INFO  [alembic.runtime.migration] Running downgrade 0002_workbook_staging -> 0001_initial_schema, Workbook staging schema migration: creates staged_workbooks table.
  INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
  INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
  INFO  [alembic.runtime.migration] Running upgrade 0001_initial_schema -> 0002_workbook_staging, Workbook staging schema migration: creates staged_workbooks table.
  === STAGE 0: Fresh Database Initialization ===
  Database Path: C:\Users\AARYAN~1\AppData\Local\Temp\tmpf3hwp_uz\verify_alembic.db

  === STAGE 1: Migration Upgrade -> 0001_initial_schema (B1 Baseline) ===
  Tables after 0001_initial_schema: ['alembic_version', 'schema_migrations', 'system_metadata']
  Indexes after 0001_initial_schema: ['sqlite_autoindex_alembic_version_1', 'sqlite_autoindex_schema_migrations_1', 'sqlite_autoindex_system_metadata_1']
  Inserted B1 baseline records into system_metadata and schema_migrations.
  system_metadata content: [('b1_test_key', 'b1_test_value', '2026-11-23 15:48:04')]
  schema_migrations content: [('0001_initial_schema', '2026-11-23 15:48:04', 'Initial B1 schema')]

  === STAGE 2: Migration Upgrade -> 0002_workbook_staging (B2 Staging Table) ===
  Tables after upgrade to head (0002): ['alembic_version', 'schema_migrations', 'staged_workbooks', 'system_metadata']
  Indexes after upgrade to head (0002): ['ix_staged_workbooks_sha256', 'ix_staged_workbooks_tenant_id', 'sqlite_autoindex_alembic_version_1', 'sqlite_autoindex_schema_migrations_1', 'sqlite_autoindex_staged_workbooks_1', 'sqlite_autoindex_system_metadata_1']
  Preserved B1 system_metadata after upgrade: [('b1_test_key', 'b1_test_value', '2026-11-23 15:48:04')]
  Inserted sample B2 record into staged_workbooks.
  staged_workbooks row count: 1

  === STAGE 3: Migration Downgrade -> 0001_initial_schema ===
  Tables after downgrade to 0001: ['alembic_version', 'schema_migrations', 'system_metadata']
  Indexes after downgrade to 0001: ['sqlite_autoindex_alembic_version_1', 'sqlite_autoindex_schema_migrations_1', 'sqlite_autoindex_system_metadata_1']
  Preserved B1 system_metadata after downgrade: [('b1_test_key', 'b1_test_value', '2026-11-23 15:48:04')]

  === STAGE 4: Migration Re-upgrade -> head (0002_workbook_staging) ===
  Tables after re-upgrade to head: ['alembic_version', 'schema_migrations', 'staged_workbooks', 'system_metadata']
  Indexes after re-upgrade to head: ['ix_staged_workbooks_sha256', 'ix_staged_workbooks_tenant_id', 'sqlite_autoindex_alembic_version_1', 'sqlite_autoindex_schema_migrations_1', 'sqlite_autoindex_staged_workbooks_1', 'sqlite_autoindex_system_metadata_1']
  Preserved B1 system_metadata after re-upgrade: [('b1_test_key', 'b1_test_value', '2026-11-23 15:48:04')]

  === MIGRATION CYCLE VERIFICATION SUCCESSFUL ===
  ```
- **Schema & Data Preservation Verification:**
  - **Stage 1 (B1 Baseline):** Tables `['alembic_version', 'schema_migrations', 'system_metadata']` exist. Baseline record `('b1_test_key', 'b1_test_value')` successfully populated.
  - **Stage 2 (B2 Upgrade to Head):** Table `staged_workbooks` created alongside indexes `ix_staged_workbooks_sha256` and `ix_staged_workbooks_tenant_id`. B1 baseline data confirmed intact.
  - **Stage 3 (Downgrade to 0001):** Table `staged_workbooks` and both indexes cleanly dropped. B1 tables and records (`b1_test_key`) completely preserved.
  - **Stage 4 (Re-upgrade to Head):** Table `staged_workbooks` and indexes recreated cleanly without duplicate errors. B1 records remain intact.

### 4.2 Model vs Migration Consistency
- **Comparison:**
  - Table name: `staged_workbooks` (identical).
  - Primary Key: `workbook_id` (`String(64)`, identical).
  - Indexed Columns: `tenant_id` (`String(64)`), `sha256` (`String(64)`) (both indexed in migration and model).
  - Datetime defaults: `staged_at`, `updated_at` both use `CURRENT_TIMESTAMP` / `func.now()`.
  - **Finding 4.2.1 (Low):** In migration `0002_workbook_staging.py`, `file_size_bytes` is declared as `sa.BigInteger()`. In `StagedWorkbookRecord`, it is declared as `mapped_column(Integer)`. In SQLite, integer columns accommodate 64-bit values dynamically. For future PostgreSQL compatibility, the model definition should declare `BigInteger`.

### 4.3 Tenant Isolation
- **Tenant Origin:** Hardcoded to `"default"` across all router operations (`routers/workbooks.py` lines 69, 84, 113, 151, 190).
- **Spoofing Assessment:** Unauthenticated clients **cannot** spoof or alter `tenant_id`. No query parameter, request body field, or HTTP header is accepted for `tenant_id`.
- **Physical Directory Isolation:** `StorageService._get_tenant_staging_dir(tenant_id)` sanitizes alphanumeric and dash/underscore characters, resolving to `${STORAGE_ROOT}/staging/{safe_tenant}/`. Directory traversal outside `${STORAGE_ROOT}/staging` is rejected with HTTP 400.
- **Finding 4.3.1 (Documented Limitation):** Multi-tenancy is logically isolated at the database schema and storage directory levels, but user authentication (JWT tenancy context) is not yet implemented. All requests currently share the `"default"` tenant workspace. This is expected at Milestone B2 and will be addressed in Milestone B7.

### 4.4 Filesystem & Database Consistency (Dual-Write)
- **Atomic File Placement:** Files are written to `.tmp_upload_<uuid>` and atomically renamed to `{workbook_id}.xlsx` via `os.replace`.
- **Interrupted Upload Cleanup:** If validation fails prior to `os.replace`, `temp_path` is deterministically removed in a `try...finally` block.
- **Finding 4.4.1 (Documented Limitation / Low):** In `upload_workbook`, `os.replace` completes before `await db.flush()`. If the database commit aborts (e.g. disk full), an orphaned staged file `{workbook_id}.xlsx` remains on disk. In `delete_workbook`, physical file unlinking occurs before `await db.delete(record); await db.flush()`. If the DB flush fails, the database retains a record pointing to a removed file. A background scavenging mechanism is recommended for production hardening.

---

## 5. API Contract Verification

| Endpoint | Method | Expected Status | Implemented Status | RFC 7807 Format | Sensitive Paths Leaked |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `/api/v1/workbooks/upload` | POST | 201 Created | 201 Created | Yes (on error) | None (Clean) |
| `/api/v1/workbooks` | GET | 200 OK | 200 OK | Yes (on error) | None (Clean) |
| `/api/v1/workbooks/{id}` | GET | 200 OK | 200 OK | Yes (404 Problem) | None (Clean) |
| `/api/v1/workbooks/{id}` | DELETE | 204 No Content | 204 No Content | Yes (404 Problem) | None (Clean) |

### Contract Schema Conformity:
- **`POST /api/v1/workbooks/upload`:** Payload strictly matches Section 3.2 of [`FRONTEND_BACKEND_API_CONTRACT.md`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/docs/architecture/FRONTEND_BACKEND_API_CONTRACT.md):
  `workbook_id`, `filename`, `file_size_bytes`, `sha256`, `staged_at`, `package_type`, `has_macros`, `status` (`"staged"`).
- **Sensitive Path Protection:** Internal storage paths (`storage_path`) are stored in the database but **never exposed** in the public API schemas (`UploadWorkbookResponse`, `StagedWorkbookSummary`, `StagedWorkbookDetail`).
- **Duplicate Uploads:** Uploading identical binaries generates distinct `workbook_id` records (`wb-<uuid>`), each with isolated lifecycles, fully complying with ADR-B0.

---

## 6. Test Execution Evidence

All four test suites were executed independently and inspected forensically:

### 6.1 Server Test Suite (FastAPI + B1/B2 Endpoints)
- **Command:** `py -3.12 -m pytest tests/server -v`
- **Result:** **38 passed, 0 failed, 3 warnings in 7.86s** (Exit Code: `0`)
- **Key Tests Executed:**
  - `tests/server/test_workbooks_api.py::test_upload_valid_xlsx_success` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_valid_xlsm_success` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_reject_empty_file` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_reject_invalid_signature_plain_text` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_reject_legacy_ole_xls` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_reject_path_traversal_in_zip_members` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_reject_zip_bomb_decompression_ratio` -> PASSED
  - `tests/server/test_workbooks_api.py::test_upload_reject_oversized_payload` -> PASSED
  - `tests/server/test_workbooks_api.py::test_ephemeral_temp_file_cleaned_on_failure` -> PASSED
  - `tests/server/test_workbooks_api.py::test_list_and_get_workbook_lifecycle` -> PASSED
  - `tests/server/test_workbooks_api.py::test_delete_workbook_removes_physical_file_and_db_record` -> PASSED
  - `tests/server/test_workbooks_api.py::test_duplicate_uploads_get_unique_ids` -> PASSED
  - `tests/server/test_workbooks_api.py::test_concurrent_uploads` -> PASSED

### 6.2 Full Python Regression Suite (M01–M05 + B1/B2)
- **Command:** `py -3.12 -m pytest -q`
- **Result:** **400 passed, 0 failed, 3 warnings in 9.21s** (Exit Code: `0`)

### 6.3 Rust Core Engine Suite (M01/M02)
- **Command:** `cargo test --manifest-path crates/excel_intel_rs/Cargo.toml`
- **Result:** **60 passed, 0 failed, 0 ignored in 2.09s** (Exit Code: `0`)

### 6.4 Frontend Regression & Production Build Suite (F0–F5)
- **Command:** `cd frontend && npm test -- --run`
- **Result:** **36 test suites passed, 155 passed** (Exit Code: `0`)
  *(Note: Execution benchmark passed cleanly in isolated execution at 161ms).*
- **Command:** `cd frontend && npm run typecheck`
- **Result:** **0 TypeScript errors** (Exit Code: `0`)
- **Command:** `cd frontend && npm run build`
- **Result:** **Production bundle compiled cleanly in 27.30s** (Exit Code: `0`)

---

## 7. Severity-Ranked Findings

### Critical Severity: None (0)
No process crashes, memory budget violations, or exploitable remote code executions found.

### High Severity: None (0)
No broken database migrations, unhandled 500 regressions, or schema violations found.

### Medium Severity (1)
- **Finding SEC-01 (Archive Member Drive-Letter Path Traversal):**
  - *Location:* [`excel_intel/server/services/storage_service.py:180`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/storage_service.py#L180)
  - *Description:* Preflight path check tests for `".."`, leading `/`, and leading `\`, but does not inspect for Windows drive letters (`C:`) or colons (`:`).
  - *Mitigation in B2:* Members are never unpacked to disk; files are read via relative ZIP entries. Exploitation is impossible in B2, but the check should be hardened before production.

### Low Severity (3)
- **Finding SEC-02 (Duplicate ZIP Member Names Permitted):**
  - *Location:* [`excel_intel/server/services/storage_service.py:171`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/services/storage_service.py#L171)
  - *Description:* Archives with duplicate member names pass preflight inspection.
- **Finding ARCH-01 (Single Tenant Workspace Context):**
  - *Location:* [`excel_intel/server/routers/workbooks.py:69`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/routers/workbooks.py#L69)
  - *Description:* All operations default to tenant `"default"`. Awaits user authentication in Milestone B7.
- **Finding DATA-01 (Non-Transactional Dual-Write Consistency):**
  - *Location:* [`excel_intel/server/routers/workbooks.py:70-88`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/routers/workbooks.py#L70-L88)
  - *Description:* Filesystem rename and database flush are decoupled. Unhandled commit errors could leave orphaned physical files.

### Informational (1)
- **Finding DATA-02 (Model Integer vs Migration BigInteger):**
  - *Location:* [`excel_intel/server/database/models.py:61`](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/server/database/models.py#L61)
  - *Description:* `file_size_bytes` is declared as `Integer` in model, `BigInteger` in Alembic migration.

---

## 8. Prioritized Remediation & Hardening Items

The following items are documented for non-blocking remediation during backend hardening:

1. **[PRIORITY 1 - SEC-01] Path Traversal Hardening:**
   - *File:* `excel_intel/server/services/storage_service.py`
   - *Correction:* Update member validation loop to reject colons or regex drive letters:
     ```python
     if ".." in name or name.startswith("/") or name.startswith("\\") or ":" in name:
         raise CorruptWorkbookError(f"Unsafe archive member path detected: {name}")
     ```
2. **[PRIORITY 2 - SEC-02] Duplicate Member Name Rejection:**
   - *File:* `excel_intel/server/services/storage_service.py`
   - *Correction:* Validate that `len(infolist) == len({m.filename for m in infolist})`.
3. **[PRIORITY 3 - DATA-02] SQLAlchemy Model BigInteger Typing:**
   - *File:* `excel_intel/server/database/models.py`
   - *Correction:* Change `file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)`.
4. **[PRIORITY 4 - DATA-01] Staging Storage Garbage Collection / Scavenger:**
   - *File:* `excel_intel/server/services/storage_service.py`
   - *Correction:* Add periodic sweep of staged files lacking database records older than 1 hour.

---

## 9. Frozen-Component Preservation Verification

- **M01–M05 Core:** Verified untouched. Git diff shows no modifications to `excel_intel/core/`, `excel_intel/spatial/`, `excel_intel/types/`, `excel_intel/formulas/`, `excel_intel/inspection/`, or `crates/`.
- **F0–F5 Frontend:** Verified untouched and frozen. No changes in `frontend/src/`. All 155 frontend tests and production build pass.
- **B1 Shell:** Lifespan, admission controller, correlation ID middleware, logging middleware, and database manager remain intact.
- **No Duplicate Parsers:** Only the Rust-backed `StreamingWorkbookReader` is utilized.

---

## 10. Final Acceptance Decision

```text
================================================================================
FINAL DECISION: B2_ACCEPTED_WITH_DOCUMENTED_LIMITATIONS
================================================================================
```

### Rationale:
Milestone B2 successfully establishes the secure streaming upload, validation, physical staging, Alembic metadata persistence, and RESTful lifecycle management for Excel workbooks without exceeding process memory ceilings or violating frozen platform contracts. The five identified limitations (drive-letter path traversal pattern, duplicate member names, single-tenant context, dual-write edge-case orphan risk, and column type declaration) do not compromise runtime safety or block platform evolution. They are formally recorded for resolution during subsequent hardening milestones.

---

## 11. Recommended Next Action

Milestone B2 is formally accepted with documented limitations.

**Exact Next Action:**  
Awaiting explicit operator authorization to proceed to **Milestone B3: Spatial Discovery & Semantic Manifest API**, wrapping `WorkbookInspector`, `SpatialDetector`, and `TypeInferenceEngine` behind the canonical REST contracts.
