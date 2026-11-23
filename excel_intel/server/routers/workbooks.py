"""Workbook management and staging router.

Conforms strictly to FRONTEND_BACKEND_API_CONTRACT.md Section 3.2.
"""

from __future__ import annotations

import json
from typing import List, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from excel_intel.server.database.models import StagedWorkbookRecord
from excel_intel.server.dependencies import get_db, get_storage_service
from excel_intel.server.services.storage_service import StorageService

router = APIRouter(prefix="/workbooks", tags=["Workbooks"])


class UploadWorkbookResponse(BaseModel):
    """Payload emitted upon successful workbook upload."""

    workbook_id: str
    filename: str
    file_size_bytes: int
    sha256: str
    staged_at: str
    package_type: str
    has_macros: bool
    status: Literal["staged"] = "staged"


class StagedWorkbookSummary(BaseModel):
    """Summary of a staged workbook in workspace inventory."""

    workbook_id: str
    filename: str
    file_size_bytes: int
    sha256: str
    staged_at: str
    package_type: str
    has_macros: bool
    sheet_count: int
    sheet_names: List[str]
    status: str


class StagedWorkbookDetail(StagedWorkbookSummary):
    """Detailed metadata for a staged workbook."""

    is_1904: bool


@router.post(
    "/upload",
    response_model=UploadWorkbookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_workbook(
    file: UploadFile = File(..., description="Multipart Excel spreadsheet (.xlsx / .xlsm)"),
    storage_service: StorageService = Depends(get_storage_service),
    db: AsyncSession = Depends(get_db),
) -> UploadWorkbookResponse:
    """Streams, validates, and stages an uploaded Excel workbook."""
    # 1. Ingest, validate structure/ratios, and write to storage
    metadata = await storage_service.store_uploaded_workbook(file, tenant_id="default")

    # 2. Persist metadata record in SQLite
    record = StagedWorkbookRecord(
        workbook_id=metadata.workbook_id,
        filename=metadata.filename,
        file_size_bytes=metadata.file_size_bytes,
        sha256=metadata.sha256,
        package_type=metadata.package_type,
        has_macros=metadata.has_macros,
        is_1904=metadata.is_1904,
        sheet_count=metadata.sheet_count,
        sheet_names=json.dumps(metadata.sheet_names),
        storage_path=metadata.storage_path,
        status="staged",
        tenant_id="default",
        staged_at=metadata.staged_at,
    )
    db.add(record)
    await db.flush()

    return UploadWorkbookResponse(
        workbook_id=metadata.workbook_id,
        filename=metadata.filename,
        file_size_bytes=metadata.file_size_bytes,
        sha256=metadata.sha256,
        staged_at=metadata.staged_at.isoformat(),
        package_type=metadata.package_type,
        has_macros=metadata.has_macros,
        status="staged",
    )


@router.get(
    "",
    response_model=List[StagedWorkbookSummary],
    status_code=status.HTTP_200_OK,
)
async def list_workbooks(
    db: AsyncSession = Depends(get_db),
) -> List[StagedWorkbookSummary]:
    """Returns list of all staged workbooks within the tenant workspace."""
    stmt = (
        select(StagedWorkbookRecord)
        .where(StagedWorkbookRecord.tenant_id == "default")
        .order_by(StagedWorkbookRecord.staged_at.desc())
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    items = []
    for r in records:
        sheet_names = json.loads(r.sheet_names) if r.sheet_names else []
        items.append(
            StagedWorkbookSummary(
                workbook_id=r.workbook_id,
                filename=r.filename,
                file_size_bytes=r.file_size_bytes,
                sha256=r.sha256,
                staged_at=r.staged_at.isoformat(),
                package_type=r.package_type,
                has_macros=r.has_macros,
                sheet_count=r.sheet_count,
                sheet_names=sheet_names,
                status=r.status,
            )
        )
    return items


@router.get(
    "/{workbook_id}",
    response_model=StagedWorkbookDetail,
    status_code=status.HTTP_200_OK,
)
async def get_workbook(
    workbook_id: str,
    db: AsyncSession = Depends(get_db),
) -> StagedWorkbookDetail:
    """Retrieves detailed metadata for a specific staged workbook."""
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

    sheet_names = json.loads(record.sheet_names) if record.sheet_names else []
    return StagedWorkbookDetail(
        workbook_id=record.workbook_id,
        filename=record.filename,
        file_size_bytes=record.file_size_bytes,
        sha256=record.sha256,
        staged_at=record.staged_at.isoformat(),
        package_type=record.package_type,
        has_macros=record.has_macros,
        is_1904=record.is_1904,
        sheet_count=record.sheet_count,
        sheet_names=sheet_names,
        status=record.status,
    )


@router.delete(
    "/{workbook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_workbook(
    workbook_id: str,
    storage_service: StorageService = Depends(get_storage_service),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Removes a staged workbook from physical disk and unregisters from SQLite."""
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

    # 1. Delete physical storage file
    storage_service.delete_staged_file(record.storage_path)

    # 2. Delete database record
    await db.delete(record)
    await db.flush()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
