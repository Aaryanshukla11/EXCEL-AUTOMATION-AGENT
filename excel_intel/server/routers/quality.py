"""Formula Intelligence and Data Quality Audit API Router (Milestone B4).

Exposes:
- GET /api/v1/workbooks/{workbook_id}/formulas/graph
- GET /api/v1/workbooks/{workbook_id}/quality/findings

Conforms strictly to FRONTEND_BACKEND_API_CONTRACT.md Section 3.4.
Enforces:
- Admission controller semaphore gating & memory protection (ADR-001).
- Strict information hiding (no physical server paths in responses).
- Multi-tenancy filtering (tenant_id="default").
- Non-blocking execution via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from excel_intel.formulas.graph import FormulaGraphReport
from excel_intel.server.admission import AdmissionController
from excel_intel.server.dependencies import (
    get_admission_controller,
    get_db,
    get_discovery_service,
    get_quality_service,
    get_storage_service,
)
from excel_intel.server.routers.discovery import _resolve_staged_workbook
from excel_intel.server.services.discovery_service import DiscoveryService
from excel_intel.server.services.quality_service import QualityAuditReport, QualityService
from excel_intel.server.services.storage_service import StorageService

router = APIRouter(prefix="/workbooks/{workbook_id}", tags=["Formulas & Quality"])


@router.get(
    "/formulas/graph",
    response_model=FormulaGraphReport,
    status_code=status.HTTP_200_OK,
)
async def get_formula_graph(
    workbook_id: str,
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    admission_controller: AdmissionController = Depends(get_admission_controller),
) -> FormulaGraphReport:
    """Extracts formula ASTs, builds calculation dependency graph, and detects circular reference cycles."""
    record, file_path = await _resolve_staged_workbook(workbook_id, db, storage_service)

    async with admission_controller.acquire(task_name=f"formulas_graph:{workbook_id}"):
        graph_report = await asyncio.to_thread(
            discovery_service.analyze_formulas,
            file_path=file_path,
        )

    return graph_report


@router.get(
    "/quality/findings",
    response_model=QualityAuditReport,
    status_code=status.HTTP_200_OK,
)
async def get_quality_findings(
    workbook_id: str,
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    quality_service: QualityService = Depends(get_quality_service),
    admission_controller: AdmissionController = Depends(get_admission_controller),
) -> QualityAuditReport:
    """Consolidates workbook data quality audit findings across structure, layout, types, and formulas."""
    record, file_path = await _resolve_staged_workbook(workbook_id, db, storage_service)

    async with admission_controller.acquire(task_name=f"quality_audit:{workbook_id}"):
        audit_report = await asyncio.to_thread(
            quality_service.audit_workbook_quality,
            file_path=file_path,
            sanitized_filename=record.filename,
        )

    return audit_report
