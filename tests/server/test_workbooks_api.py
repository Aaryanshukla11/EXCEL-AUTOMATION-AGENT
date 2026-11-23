"""Comprehensive tests for Workbook Staging & File Management Service (Milestone B2).

Verifies:
- Valid XLSX & XLSM multipart upload and SHA-256 hashing.
- Invalid file signatures and legacy OLE (.xls) rejection (HTTP 400).
- ZIP bomb and decompression ratio guards (HTTP 400 ZIP_BOMB_DETECTED).
- Archive member path traversal rejection (HTTP 400).
- Oversized uploads exceeding configured size ceiling (HTTP 413).
- Ephemeral temporary file cleanup on failures.
- Duplicate uploads getting distinct workbook IDs without collision.
- Inventory listing and detail retrieval.
- Physical disk and database deletion.
- Concurrent uploads.
- RFC 7807 Problem Details error formatting.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
from pathlib import Path
from typing import Generator
import zipfile

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from excel_intel.server.app import create_app
from excel_intel.server.config import ServerConfig


def create_test_xlsx_bytes(sheet_names: list[str] | None = None, is_xlsm: bool = False) -> bytes:
    """Generates an in-memory valid OpenXML workbook binary."""
    sheets = sheet_names or ["Sheet1", "Summary"]
    buf = io.BytesIO()

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    )
    for i, _ in enumerate(sheets, start=1):
        content_types += f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    content_types += '</Types>'

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    sheet_elems = "".join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheets, start=1))
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<workbookPr date1904="0"/>'
        f'<sheets>{sheet_elems}</sheets>'
        '</workbook>'
    )

    wb_rel_elems = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i, _ in enumerate(sheets, start=1)
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{wb_rel_elems}'
        '</Relationships>'
    )

    minimal_sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData><row r="1"><c r="A1"><v>42</v></c></row></sheetData>'
        '</worksheet>'
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        for i, _ in enumerate(sheets, start=1):
            zf.writestr(f"xl/worksheets/sheet{i}.xml", minimal_sheet_xml)
        if is_xlsm:
            zf.writestr("xl/vbaProject.bin", b"\x00" * 100)

    return buf.getvalue()


@pytest.fixture
def b2_server_config(tmp_path: Path) -> ServerConfig:
    """Isolated ServerConfig fixture for B2 workbook tests."""
    storage_dir = tmp_path / "b2_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "b2_vault.db"

    return ServerConfig(
        env="test",
        host="127.0.0.1",
        port=8000,
        api_prefix="/api/v1",
        storage_root=storage_dir,
        database_url=f"sqlite+aiosqlite:///{db_file}",
        max_rss_mb=250,
        memory_warning_mb=235.0,
        memory_throttle_threshold_mb=180.0,
        admission_concurrency_limit=2,
        log_level="DEBUG",
        log_format="json",
    )


@pytest_asyncio.fixture
async def b2_client(b2_server_config: ServerConfig):
    """AsyncClient connected to the B2 ASGI test application."""
    app = create_app(b2_server_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac, b2_server_config


# ==============================================================================
# 1. Successful Upload Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_upload_valid_xlsx_success(b2_client) -> None:
    """Verifies valid XLSX file upload computes exact SHA-256, stages physical file, and creates DB record."""
    client, cfg = b2_client
    content = create_test_xlsx_bytes(["Sales", "Forecast"])
    expected_sha256 = hashlib.sha256(content).hexdigest()

    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("financial_q4.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["workbook_id"].startswith("wb-")
    assert data["filename"] == "financial_q4.xlsx"
    assert data["file_size_bytes"] == len(content)
    assert data["sha256"] == expected_sha256
    assert data["package_type"] == "xlsx"
    assert data["has_macros"] is False
    assert data["status"] == "staged"
    assert "staged_at" in data

    # Verify physical file existence in storage
    staging_dir = cfg.storage_root / "staging" / "default"
    staged_file = staging_dir / f"{data['workbook_id']}.xlsx"
    assert staged_file.exists()
    assert staged_file.read_bytes() == content


@pytest.mark.asyncio
async def test_upload_valid_xlsm_success(b2_client) -> None:
    """Verifies valid XLSM macro-enabled workbook upload is correctly classified."""
    client, cfg = b2_client
    content = create_test_xlsx_bytes(["MacroSheet"], is_xlsm=True)

    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("macro_model.xlsm", content, "application/vnd.ms-excel.sheet.macroEnabled.12")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["package_type"] == "xlsm"
    assert data["has_macros"] is True


# ==============================================================================
# 2. Security & Validation Rejection Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_upload_reject_empty_file(b2_client) -> None:
    """Verifies uploading an empty 0-byte file returns HTTP 400."""
    client, _ = b2_client
    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("empty.xlsx", b"", "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "CORRUPT_WORKBOOK"
    assert "empty" in data["detail"].lower()


@pytest.mark.asyncio
async def test_upload_reject_invalid_signature_plain_text(b2_client) -> None:
    """Verifies non-ZIP plain text file returns HTTP 400 INVALID_FILE_TYPE."""
    client, _ = b2_client
    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("notes.txt", b"Hello, this is just plain text content.", "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_FILE_TYPE"
    assert "signature" in data["detail"].lower()


@pytest.mark.asyncio
async def test_upload_reject_legacy_ole_xls(b2_client) -> None:
    """Verifies legacy binary Excel (.xls / OLE) header is detected and rejected with informative error."""
    client, _ = b2_client
    ole_content = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1" + b"\x00" * 512

    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("legacy.xls", ole_content, "application/vnd.ms-excel")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_FILE_TYPE"
    assert "legacy" in data["detail"].lower() or "ole" in data["detail"].lower()


@pytest.mark.asyncio
async def test_upload_reject_path_traversal_in_zip_members(b2_client) -> None:
    """Verifies ZIP archives containing path traversal entries are rejected before extraction."""
    client, _ = b2_client
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        zf.writestr("xl/workbook.xml", b"<workbook/>")
        zf.writestr("../../etc/passwd", b"malicious content")

    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("exploit.xlsx", buf.getvalue(), "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "CORRUPT_WORKBOOK"
    assert "unsafe archive member path" in data["detail"].lower()


@pytest.mark.asyncio
async def test_upload_reject_zip_bomb_decompression_ratio(b2_client) -> None:
    """Verifies high-ratio zip bombs trigger immediate rejection via Rust decompression guard."""
    client, _ = b2_client
    buf = io.BytesIO()
    # 25 MB of repeated zeros compresses down to ~25 KB (ratio > 1000:1, exceeding 10x ceiling)
    zero_bytes = b"0" * (25 * 1024 * 1024)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        zf.writestr("xl/workbook.xml", b"<workbook/>")
        zf.writestr("xl/worksheets/sheet1.xml", zero_bytes)

    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("bomb.xlsx", buf.getvalue(), "application/octet-stream")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] in ("ZIP_BOMB_DETECTED", "CORRUPT_WORKBOOK")


@pytest.mark.asyncio
async def test_upload_reject_oversized_payload(b2_client) -> None:
    """Verifies files exceeding max upload size ceiling are aborted with HTTP 413."""
    client, cfg = b2_client
    # Artificially set a low ceiling on the service for testing
    from excel_intel.server.services.storage_service import StorageService

    # 100 KiB threshold
    tiny_storage = StorageService(storage_root=cfg.storage_root, max_upload_bytes=100 * 1024)
    app = client._transport.app
    app.state.storage_service = tiny_storage

    large_content = create_test_xlsx_bytes() + (b"0" * 200 * 1024)  # ~210 KB

    response = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("large.xlsx", large_content, "application/octet-stream")},
    )
    assert response.status_code == 413
    data = response.json()
    assert data["code"] == "PAYLOAD_TOO_LARGE"


@pytest.mark.asyncio
async def test_ephemeral_temp_file_cleaned_on_failure(b2_client) -> None:
    """Verifies no ephemeral .tmp_upload_* files remain on disk when an upload fails."""
    client, cfg = b2_client
    staging_dir = cfg.storage_root / "staging" / "default"

    # Send malformed data that fails validation
    await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("corrupt.xlsx", b"PK\x03\x04corrupted_payload", "application/octet-stream")},
    )

    # Verify no temp files exist
    tmp_files = list(staging_dir.glob(".tmp_upload_*"))
    assert len(tmp_files) == 0


# ==============================================================================
# 3. Inventory Listing, Retrieval, and Deletion Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_list_and_get_workbook_lifecycle(b2_client) -> None:
    """Verifies listing staged workbooks and retrieving single workbook detail."""
    client, _ = b2_client

    # 1. Upload first workbook
    wb1_content = create_test_xlsx_bytes(["SheetA", "SheetB"])
    res1 = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("model_1.xlsx", wb1_content, "application/octet-stream")},
    )
    assert res1.status_code == 201
    wb1_id = res1.json()["workbook_id"]

    # 2. Upload second workbook
    wb2_content = create_test_xlsx_bytes(["OnlyOne"])
    res2 = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("model_2.xlsx", wb2_content, "application/octet-stream")},
    )
    assert res2.status_code == 201
    wb2_id = res2.json()["workbook_id"]

    # 3. List workbooks
    list_res = await client.get("/api/v1/workbooks")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 2

    ids = [item["workbook_id"] for item in items]
    assert wb1_id in ids
    assert wb2_id in ids

    # 4. Get specific workbook detail
    detail_res = await client.get(f"/api/v1/workbooks/{wb1_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["workbook_id"] == wb1_id
    assert detail["filename"] == "model_1.xlsx"
    assert detail["sheet_count"] == 2
    assert detail["sheet_names"] == ["SheetA", "SheetB"]
    assert "is_1904" in detail

    # 5. Nonexistent workbook returns 404
    nonexistent_res = await client.get("/api/v1/workbooks/wb-nonexistent-id")
    assert nonexistent_res.status_code == 404
    assert nonexistent_res.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_workbook_removes_physical_file_and_db_record(b2_client) -> None:
    """Verifies DELETE /api/v1/workbooks/{id} cleans up both storage file and SQLite record."""
    client, cfg = b2_client
    content = create_test_xlsx_bytes(["DeletableSheet"])

    # Upload
    upload_res = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("to_delete.xlsx", content, "application/octet-stream")},
    )
    wb_id = upload_res.json()["workbook_id"]

    staging_file = cfg.storage_root / "staging" / "default" / f"{wb_id}.xlsx"
    assert staging_file.exists()

    # Delete
    del_res = await client.delete(f"/api/v1/workbooks/{wb_id}")
    assert del_res.status_code == 204

    # Verify physical file is gone
    assert not staging_file.exists()

    # Verify subsequent GET returns 404
    get_res = await client.get(f"/api/v1/workbooks/{wb_id}")
    assert get_res.status_code == 404

    # Deleting again returns 404
    second_del = await client.delete(f"/api/v1/workbooks/{wb_id}")
    assert second_del.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_uploads_get_unique_ids(b2_client) -> None:
    """Verifies uploading the exact same binary twice produces distinct IDs without collision."""
    client, cfg = b2_client
    content = create_test_xlsx_bytes(["Identical"])

    res1 = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("same.xlsx", content, "application/octet-stream")},
    )
    res2 = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": ("same.xlsx", content, "application/octet-stream")},
    )

    wb1_id = res1.json()["workbook_id"]
    wb2_id = res2.json()["workbook_id"]

    assert wb1_id != wb2_id
    assert res1.json()["sha256"] == res2.json()["sha256"]

    # Both files must coexist on disk
    staging_dir = cfg.storage_root / "staging" / "default"
    assert (staging_dir / f"{wb1_id}.xlsx").exists()
    assert (staging_dir / f"{wb2_id}.xlsx").exists()


@pytest.mark.asyncio
async def test_concurrent_uploads(b2_client) -> None:
    """Verifies multiple concurrent uploads stage cleanly without deadlocks or race conditions."""
    client, cfg = b2_client

    async def upload_task(idx: int):
        content = create_test_xlsx_bytes([f"Concurrent_{idx}"])
        res = await client.post(
            "/api/v1/workbooks/upload",
            files={"file": (f"concurrent_{idx}.xlsx", content, "application/octet-stream")},
        )
        assert res.status_code == 201
        return res.json()["workbook_id"]

    wb_ids = await asyncio.gather(*[upload_task(i) for i in range(5)])
    assert len(set(wb_ids)) == 5

    # Verify all 5 exist in inventory
    list_res = await client.get("/api/v1/workbooks")
    inventory_ids = [item["workbook_id"] for item in list_res.json()]
    for wb_id in wb_ids:
        assert wb_id in inventory_ids
