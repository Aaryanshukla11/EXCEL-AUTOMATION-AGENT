"""Discovery, Inspection, and Manifest API Router (Milestone B3).

Exposes:
- GET /api/v1/workbooks/{workbook_id}/manifest
- GET /api/v1/workbooks/{workbook_id}/inspection
- GET /api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/spatial
- GET /api/v1/workbooks/{workbook_id}/sheets/{sheet_name}/types

Conforms strictly to FRONTEND_BACKEND_API_CONTRACT.md Section 3.3.
Enforces:
- Admission controller semaphore gating & memory protection (ADR-001).
- Strict information hiding (no physical server paths in responses).
- Multi-tenancy filtering (tenant_id="default").
- Non-blocking execution via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from excel_intel.core.types import DiscoveryManifest
from excel_intel.inspection.models import WorkbookInspectionReport
from excel_intel.server.admission import AdmissionController
from excel_intel.server.database.models import StagedWorkbookRecord
from excel_intel.server.dependencies import (
    get_admission_controller,
    get_db,
    get_discovery_service,
    get_storage_service,
)
from excel_intel.server.services.discovery_service import DiscoveryService
from excel_intel.server.services.storage_service import StorageService
from excel_intel.spatial.models import SpatialTableRegion
from excel_intel.types.models import RegionTypeReport

router = APIRouter(prefix="/workbooks/{workbook_id}", tags=["Discovery"])


async def _resolve_staged_workbook(
    workbook_id: str,
    db: AsyncSession,
    storage_service: StorageService,
) -> tuple[StagedWorkbookRecord, Path]:
    """Helper to locate staged workbook record and verify physical file existence."""
    stmt = select(StagedWorkbookRecord).where(
        StagedWorkbookRecord.workbook_id == workbook_id,
        StagedWorkbookRecord.tenant_id == "default",
    )
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staged workbook with ID '{workbook_id}' was not found.",
        )

    file_path = (storage_service.storage_root / record.storage_path).resolve()
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staged workbook file for ID '{workbook_id}' is missing from storage.",
        )

    return record, file_path


@router.get(
    "/manifest",
    response_model=DiscoveryManifest,
    status_code=status.HTTP_200_OK,
)
async def get_workbook_manifest(
    workbook_id: str,
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    admission_controller: AdmissionController = Depends(get_admission_controller),
) -> DiscoveryManifest:
    """Emits the root canonical DiscoveryManifest unifying spatial tables, types, and formula graph."""
    record, file_path = await _resolve_staged_workbook(workbook_id, db, storage_service)

    async with admission_controller.acquire(task_name=f"manifest:{workbook_id}"):
        manifest = await asyncio.to_thread(
            discovery_service.generate_manifest,
            file_path=file_path,
            sanitized_filename=record.filename,
            sha256=record.sha256,
            file_size_bytes=record.file_size_bytes,
        )

    return manifest


@router.get(
    "/inspection",
    response_model=WorkbookInspectionReport,
    status_code=status.HTTP_200_OK,
)
async def get_workbook_inspection(
    workbook_id: str,
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    admission_controller: AdmissionController = Depends(get_admission_controller),
) -> WorkbookInspectionReport:
    """Returns workbook topology facts, declared tables, merge cells, dimensions, and anomalies."""
    record, file_path = await _resolve_staged_workbook(workbook_id, db, storage_service)

    async with admission_controller.acquire(task_name=f"inspection:{workbook_id}"):
        report = await asyncio.to_thread(
            discovery_service.inspect_workbook,
            file_path=file_path,
            sanitized_filename=record.filename,
        )

    return report


@router.get(
    "/sheets/{sheet_name}/spatial",
    response_model=List[SpatialTableRegion],
    status_code=status.HTTP_200_OK,
)
async def get_sheet_spatial_regions(
    workbook_id: str,
    sheet_name: str,
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    admission_controller: AdmissionController = Depends(get_admission_controller),
) -> List[SpatialTableRegion]:
    """Returns detected 2D tabular regions, semantic zones, and margin clearances for a worksheet."""
    record, file_path = await _resolve_staged_workbook(workbook_id, db, storage_service)

    # Validate sheet exists in workbook metadata
    sheet_names = json.loads(record.sheet_names) if record.sheet_names else []
    if sheet_name not in sheet_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sheet '{sheet_name}' was not found in workbook '{workbook_id}'.",
        )

    async with admission_controller.acquire(task_name=f"spatial:{workbook_id}:{sheet_name}"):
        regions = await asyncio.to_thread(
            discovery_service.detect_sheet_spatial,
            file_path=file_path,
            sheet_name=sheet_name,
            sanitized_filename=record.filename,
        )

    return regions


@router.get(
    "/sheets/{sheet_name}/types",
    response_model=RegionTypeReport,
    status_code=status.HTTP_200_OK,
)
async def get_sheet_region_types(
    workbook_id: str,
    sheet_name: str,
    region_id: Optional[str] = Query(default=None, description="Optional target region identifier"),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    discovery_service: DiscoveryService = Depends(get_discovery_service),
    admission_controller: AdmissionController = Depends(get_admission_controller),
) -> RegionTypeReport:
    """Returns semantic type profiles, nullability, and heuristic support scores for worksheet regions."""
    record, file_path = await _resolve_staged_workbook(workbook_id, db, storage_service)

    # Validate sheet exists in workbook metadata
    sheet_names = json.loads(record.sheet_names) if record.sheet_names else []
    if sheet_name not in sheet_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sheet '{sheet_name}' was not found in workbook '{workbook_id}'.",
        )

    async with admission_controller.acquire(task_name=f"types:{workbook_id}:{sheet_name}"):
        report = await asyncio.to_thread(
            discovery_service.infer_sheet_types,
            file_path=file_path,
            sheet_name=sheet_name,
            region_id=region_id,
        )

    return report
