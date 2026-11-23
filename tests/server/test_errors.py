"""Tests for RFC 7807 Problem Details error handling and Correlation ID middleware."""

from __future__ import annotations

from fastapi import APIRouter
from httpx import AsyncClient
import pytest

from excel_intel.exceptions import (
    FormulaCycleError,
    PlatformError,
    SchemaViolationError,
    UnsupportedFormatError,
)
from excel_intel.server.admission import AdmissionRejectedError

error_probe_router = APIRouter()


@error_probe_router.get("/test/raise-unsupported")
async def trigger_unsupported():
    raise UnsupportedFormatError("Spreadsheet format BIFF8 is not supported.")


@error_probe_router.get("/test/raise-schema-violation")
async def trigger_schema_violation():
    raise SchemaViolationError("Missing required Header zone in worksheet.")


@error_probe_router.get("/test/raise-formula-cycle")
async def trigger_formula_cycle():
    raise FormulaCycleError("Circular formula dependency: Sheet1!A1 -> Sheet1!B1 -> Sheet1!A1")


@error_probe_router.get("/test/raise-admission-rejected")
async def trigger_admission_rejected():
    raise AdmissionRejectedError("System RSS ceiling approached; request throttled.")


@error_probe_router.get("/test/raise-unexpected")
async def trigger_unexpected():
    raise RuntimeError("Unexpected zero division or null pointer simulation.")


@pytest.mark.asyncio
async def test_rfc7807_error_mapping_unsupported_format(client: AsyncClient, async_app) -> None:
    """Verifies UnsupportedFormatError produces RFC 7807 response with HTTP 400."""
    async_app.include_router(error_probe_router, prefix="/api/v1")
    response = await client.get("/api/v1/test/raise-unsupported")
    assert response.status_code == 400
    data = response.json()

    assert data["type"] == "https://excel-intel.internal/errors/INVALID_FILE_TYPE"
    assert data["status"] == 400
    assert data["code"] == "INVALID_FILE_TYPE"
    assert "Spreadsheet format BIFF8 is not supported" in data["detail"]
    assert "correlation_id" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_rfc7807_error_mapping_schema_violation(client: AsyncClient, async_app) -> None:
    """Verifies SchemaViolationError produces RFC 7807 response with HTTP 422."""
    async_app.include_router(error_probe_router, prefix="/api/v1")
    response = await client.get("/api/v1/test/raise-schema-violation")
    assert response.status_code == 422
    data = response.json()

    assert data["type"] == "https://excel-intel.internal/errors/SCHEMA_VALIDATION_ERROR"
    assert data["status"] == 422
    assert data["code"] == "SCHEMA_VALIDATION_ERROR"
    assert "Missing required Header zone" in data["detail"]


@pytest.mark.asyncio
async def test_rfc7807_error_mapping_formula_cycle(client: AsyncClient, async_app) -> None:
    """Verifies FormulaCycleError produces RFC 7807 response with HTTP 422."""
    async_app.include_router(error_probe_router, prefix="/api/v1")
    response = await client.get("/api/v1/test/raise-formula-cycle")
    assert response.status_code == 422
    data = response.json()

    assert data["type"] == "https://excel-intel.internal/errors/FORMULA_CYCLE_DETECTED"
    assert data["status"] == 422
    assert data["code"] == "FORMULA_CYCLE_DETECTED"
    assert "Circular formula dependency" in data["detail"]


@pytest.mark.asyncio
async def test_rfc7807_error_mapping_admission_rejected(client: AsyncClient, async_app) -> None:
    """Verifies AdmissionRejectedError produces RFC 7807 response with HTTP 429 and Retry-After header."""
    async_app.include_router(error_probe_router, prefix="/api/v1")
    response = await client.get("/api/v1/test/raise-admission-rejected")
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "5"
    data = response.json()

    assert data["type"] == "https://excel-intel.internal/errors/ADMISSION_REJECTED"
    assert data["status"] == 429
    assert data["code"] == "ADMISSION_REJECTED"


@pytest.mark.asyncio
async def test_rfc7807_error_mapping_unexpected_exception(client: AsyncClient, async_app) -> None:
    """Verifies unhandled exception returns HTTP 500 without leaking stack traces."""
    async_app.include_router(error_probe_router, prefix="/api/v1")
    response = await client.get("/api/v1/test/raise-unexpected")
    assert response.status_code == 500
    data = response.json()

    assert data["type"] == "https://excel-intel.internal/errors/INTERNAL_ERROR"
    assert data["status"] == 500
    assert data["code"] == "INTERNAL_ERROR"
    assert "An unexpected internal error occurred" in data["detail"]


@pytest.mark.asyncio
async def test_correlation_id_propagation(client: AsyncClient) -> None:
    """Verifies incoming X-Correlation-ID is preserved and attached to the response."""
    custom_cid = "req-custom-audit-test-999"
    response = await client.get("/api/v1/health", headers={"X-Correlation-ID": custom_cid})
    assert response.status_code == 200
    assert response.headers.get("x-correlation-id") == custom_cid
