"""Comprehensive integration tests for Spatial Discovery & Semantic Manifest API (Milestone B3).

Verifies:
- GET /api/v1/workbooks/{id}/manifest (canonical DiscoveryManifest synthesis)
- GET /api/v1/workbooks/{id}/inspection (M03 topology facts, dimensions, anomalies)
- GET /api/v1/workbooks/{id}/sheets/{sheet}/spatial (M04 2D spatial regions, zones, margins)
- GET /api/v1/workbooks/{id}/sheets/{sheet}/types (M05 semantic types, column profiles, sampling)
- Path sanitization (no internal server storage paths leaked in responses)
- RFC 7807 problem details error responses on missing workbooks, missing sheets, invalid regions
- Admission controller concurrency and memory throttling (HTTP 429)
"""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from excel_intel.server.admission import AdmissionController
from excel_intel.server.app import create_app
from excel_intel.server.config import ServerConfig


def create_discovery_test_xlsx(
    sheets_data: dict[str, list[list[str | int | float | None]]] | None = None,
    formulas: dict[str, str] | None = None,
) -> bytes:
    """Generates an in-memory OpenXML workbook with real cell data and optional formulas."""
    sheets = sheets_data or {
        "Transactions": [
            ["TxID", "Customer", "Amount", "Active"],
            [1001, "Acme Corp", 1500.50, "TRUE"],
            [1002, "Beta LLC", 2400.00, "FALSE"],
            [1003, "Gamma Inc", 320.75, "TRUE"],
        ],
        "Summary": [
            ["Metric", "Value"],
            ["Total", 4221.25],
        ],
    }

    buf = io.BytesIO()
    sheet_names = list(sheets.keys())

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    )
    for i in range(1, len(sheet_names) + 1):
        content_types += f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    content_types += '</Types>'

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    sheet_elems = "".join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(sheet_names, start=1))
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<workbookPr date1904="0"/>'
        f'<sheets>{sheet_elems}</sheets>'
        '</workbook>'
    )

    wb_rel_elems = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, len(sheet_names) + 1)
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{wb_rel_elems}'
        '</Relationships>'
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)

        for sheet_idx, (name, rows) in enumerate(sheets.items(), start=1):
            sheet_rows_xml = []
            for r_idx, row in enumerate(rows, start=1):
                cells_xml = []
                for c_idx, val in enumerate(row, start=1):
                    col_letter = chr(ord("A") + c_idx - 1)
                    coord = f"{col_letter}{r_idx}"
                    full_coord = f"{name}!{coord}"
                    formula_tag = ""
                    if formulas and full_coord in formulas:
                        formula_tag = f"<f>{formulas[full_coord]}</f>"

                    if val is None:
                        continue
                    elif isinstance(val, (int, float)):
                        cells_xml.append(f'<c r="{coord}">{formula_tag}<v>{val}</v></c>')
                    elif str(val).upper() in ("TRUE", "FALSE"):
                        bval = 1 if str(val).upper() == "TRUE" else 0
                        cells_xml.append(f'<c r="{coord}" t="b">{formula_tag}<v>{bval}</v></c>')
                    else:
                        cells_xml.append(f'<c r="{coord}" t="str">{formula_tag}<v>{val}</v></c>')

                sheet_rows_xml.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(sheet_rows_xml)}</sheetData>'
                '</worksheet>'
            )
            zf.writestr(f"xl/worksheets/sheet{sheet_idx}.xml", sheet_xml)

    return buf.getvalue()


@pytest.fixture
def b3_config(tmp_path: Path) -> ServerConfig:
    """Configured test environment for Milestone B3."""
    storage_dir = tmp_path / "b3_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "b3_vault.db"

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
async def b3_client(b3_config: ServerConfig):
    """AsyncClient fixture with lifespan initialized."""
    app = create_app(b3_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client, b3_config


# ==============================================================================
# Helper to upload workbook
# ==============================================================================

async def _upload_workbook(client: AsyncClient, content: bytes, filename: str = "test.xlsx") -> str:
    res = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code == 201
    return res.json()["workbook_id"]


# ==============================================================================
# 1. Manifest Endpoint Tests (GET /workbooks/{id}/manifest)
# ==============================================================================

@pytest.mark.asyncio
async def test_get_manifest_success(b3_client) -> None:
    """Verifies canonical DiscoveryManifest synthesis combining spatial tables, types, and formula graph."""
    client, cfg = b3_client
    content = create_discovery_test_xlsx(
        formulas={"Summary!B2": "SUM(Transactions!C2:C4)"}
    )
    wb_id = await _upload_workbook(client, content, "finance_model.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/manifest")
    assert res.status_code == 200
    data = res.json()

    assert "manifest_id" in data
    assert data["sha256"] is not None
    assert data["file_size_bytes"] == len(content)
    # Verify path sanitization
    assert str(cfg.storage_root) not in data["workbook_path"]
    assert data["workbook_path"] == "finance_model.xlsx"

    # Verify tables metadata
    assert len(data["tables"]) >= 1
    tx_table = next((t for t in data["tables"] if t["sheet_name"] == "Transactions"), None)
    assert tx_table is not None
    col_names = [c["header_name"] for c in tx_table["columns"]]
    assert "TxID" in col_names
    assert "Amount" in col_names

    # Verify formula graph metadata
    assert "formula_graph" in data
    assert data["formula_graph"]["node_count"] >= 1
    assert data["formula_graph"]["has_cycles"] is False


@pytest.mark.asyncio
async def test_get_manifest_missing_workbook_404(b3_client) -> None:
    """Verifies querying nonexistent workbook returns RFC 7807 404."""
    client, _ = b3_client
    res = await client.get("/api/v1/workbooks/wb-nonexistent-uuid/manifest")
    assert res.status_code == 404
    err = res.json()
    assert err["code"] == "RESOURCE_NOT_FOUND"
    assert "wb-nonexistent-uuid" in err["detail"]


# ==============================================================================
# 2. Inspection Endpoint Tests (GET /workbooks/{id}/inspection)
# ==============================================================================

@pytest.mark.asyncio
async def test_get_inspection_success(b3_client) -> None:
    """Verifies workbook inspection topology, package properties, facts, and path sanitization."""
    client, cfg = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content, "catalog.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/inspection")
    assert res.status_code == 200
    data = res.json()

    assert data["package_type"] == "xlsx"
    assert data["is_1904"] is False
    assert data["has_macros"] is False
    assert "inspection_timestamp" in data
    assert len(data["sheets"]) == 2

    sheet_names = [s["sheet_name"] for s in data["sheets"]]
    assert "Transactions" in sheet_names
    assert "Summary" in sheet_names

    # Sensitive path sanitization
    assert str(cfg.storage_root) not in data["workbook_path"]
    assert data["workbook_path"] == "catalog.xlsx"


@pytest.mark.asyncio
async def test_get_inspection_missing_workbook_404(b3_client) -> None:
    """Verifies inspection on missing workbook returns 404."""
    client, _ = b3_client
    res = await client.get("/api/v1/workbooks/wb-00000000/inspection")
    assert res.status_code == 404
    assert res.json()["code"] == "RESOURCE_NOT_FOUND"


# ==============================================================================
# 3. Spatial Regions Endpoint Tests (GET /workbooks/{id}/sheets/{sheet}/spatial)
# ==============================================================================

@pytest.mark.asyncio
async def test_get_sheet_spatial_regions_success(b3_client) -> None:
    """Verifies 2D grid segmentation, semantic zone decomposition, and margin clearance."""
    client, _ = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content, "spatial_test.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/Transactions/spatial")
    assert res.status_code == 200
    regions = res.json()

    assert isinstance(regions, list)
    assert len(regions) >= 1

    primary_reg = regions[0]
    assert primary_reg["sheet_name"] == "Transactions"
    assert "bounding_box" in primary_reg
    assert primary_reg["bounding_box"]["min_row"] >= 1
    assert primary_reg["region_type"] in ("inferred_table", "declared_table", "sparse_island")
    assert primary_reg["heuristic_confidence"] > 0.0
    assert "zones" in primary_reg
    assert "margin" in primary_reg


@pytest.mark.asyncio
async def test_get_sheet_spatial_missing_sheet_404(b3_client) -> None:
    """Verifies querying spatial regions on nonexistent sheet returns 404."""
    client, _ = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content)

    res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/NoSuchSheet/spatial")
    assert res.status_code == 404
    err = res.json()
    assert err["code"] == "RESOURCE_NOT_FOUND"
    assert "NoSuchSheet" in err["detail"]


# ==============================================================================
# 4. Semantic Types Endpoint Tests (GET /workbooks/{id}/sheets/{sheet}/types)
# ==============================================================================

@pytest.mark.asyncio
async def test_get_sheet_region_types_success(b3_client) -> None:
    """Verifies semantic type inference, column profiles, nullability, and sampling diagnostics."""
    client, _ = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content, "types_test.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/Transactions/types")
    assert res.status_code == 200
    data = res.json()

    assert data["sheet_name"] == "Transactions"
    assert "region_id" in data
    assert "columns" in data
    assert len(data["columns"]) >= 1

    # Check sampling diagnostics
    assert "sampling" in data
    assert data["sampling"]["sampled_rows"] >= 1

    # Columns keyed by integer string index
    cols = data["columns"]
    col_profiles = list(cols.values())
    inferred_types = [p["inferred_type"] for p in col_profiles]
    assert any(t in ("INTEGER", "DECIMAL", "STRING", "BOOLEAN") for t in inferred_types)


@pytest.mark.asyncio
async def test_get_sheet_region_types_with_region_id_filter(b3_client) -> None:
    """Verifies querying specific region by region_id query parameter."""
    client, _ = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content)

    # 1. Fetch spatial regions to obtain valid region_id
    spatial_res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/Transactions/spatial")
    assert spatial_res.status_code == 200
    target_region_id = spatial_res.json()[0]["region_id"]

    # 2. Query types with query param
    types_res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/Transactions/types?region_id={target_region_id}")
    assert types_res.status_code == 200
    assert types_res.json()["region_id"] == target_region_id

    # 3. Query with nonexistent region_id returns 404
    bad_res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/Transactions/types?region_id=reg-invalid-id")
    assert bad_res.status_code == 404
    assert bad_res.json()["code"] == "RESOURCE_NOT_FOUND"


# ==============================================================================
# 5. Admission Controller Throttling Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_discovery_admission_control_throttling(b3_client) -> None:
    """Verifies memory pressure triggers HTTP 429 ADMISSION_REJECTED with Retry-After header."""
    client, cfg = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content)

    # Artificially set throttle threshold to 0.0 MB so admission check fails
    app = client._transport.app
    ctrl: AdmissionController = app.state.admission_controller
    ctrl._throttle_threshold_mb = 0.0  # Force throttle

    try:
        res = await client.get(f"/api/v1/workbooks/{wb_id}/manifest")
        assert res.status_code == 429
        data = res.json()
        assert data["code"] == "ADMISSION_REJECTED"
        assert res.headers.get("Retry-After") == "5"
    finally:
        # Restore threshold
        ctrl._throttle_threshold_mb = cfg.memory_throttle_threshold_mb


# ==============================================================================
# 6. Edge Cases, Tenant Isolation & Information Hiding Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_manifest_empty_sheet(b3_client) -> None:
    """Verifies workbook with empty sheet produces valid manifest with 0 tables."""
    client, _ = b3_client
    content = create_discovery_test_xlsx(sheets_data={"EmptySheet": [[]]})
    wb_id = await _upload_workbook(client, content, "empty.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/manifest")
    assert res.status_code == 200
    data = res.json()
    assert data["tables"] == []
    assert data["formula_graph"]["node_count"] == 0


@pytest.mark.asyncio
async def test_get_sheet_types_empty_sheet(b3_client) -> None:
    """Verifies empty sheet returns default RegionTypeReport without throwing 500."""
    client, _ = b3_client
    content = create_discovery_test_xlsx(sheets_data={"EmptySheet": [[]]})
    wb_id = await _upload_workbook(client, content, "empty_types.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/sheets/EmptySheet/types")
    assert res.status_code == 200
    data = res.json()
    assert data["columns"] == {}
    assert data["sampling"]["sampled_rows"] == 0


@pytest.mark.asyncio
async def test_tenant_isolation_cannot_access_foreign_tenant_workbook(b3_client) -> None:
    """Verifies workbooks belonging to a foreign tenant are not accessible (returns 404)."""
    client, cfg = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content, "tenant_test.xlsx")

    # Manually reassign record in database to another tenant
    app = client._transport.app
    db_mgr = app.state.db_manager
    from sqlalchemy import update
    from excel_intel.server.database.models import StagedWorkbookRecord

    async with db_mgr.session_factory() as session:
        await session.execute(
            update(StagedWorkbookRecord)
            .where(StagedWorkbookRecord.workbook_id == wb_id)
            .values(tenant_id="foreign_tenant_xyz")
        )
        await session.commit()

    # Querying as default tenant must yield 404
    for endpoint in ("/manifest", "/inspection", "/sheets/Transactions/spatial", "/sheets/Transactions/types"):
        res = await client.get(f"/api/v1/workbooks/{wb_id}{endpoint}")
        assert res.status_code == 404
        assert res.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_no_internal_paths_leaked_in_any_response(b3_client) -> None:
    """Verifies that none of the B3 endpoints leak internal filesystem paths or drive letters."""
    client, cfg = b3_client
    content = create_discovery_test_xlsx()
    wb_id = await _upload_workbook(client, content, "sensitive_check.xlsx")

    root_str = str(cfg.storage_root)
    # Check all 4 endpoints
    for url in (
        f"/api/v1/workbooks/{wb_id}/manifest",
        f"/api/v1/workbooks/{wb_id}/inspection",
        f"/api/v1/workbooks/{wb_id}/sheets/Transactions/spatial",
        f"/api/v1/workbooks/{wb_id}/sheets/Transactions/types",
    ):
        res = await client.get(url)
        assert res.status_code == 200
        body_text = res.text
        assert root_str not in body_text
        assert "b3_storage" not in body_text
        assert "Users" not in body_text

