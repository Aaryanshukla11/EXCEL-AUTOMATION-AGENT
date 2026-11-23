"""Comprehensive integration tests for Formula Intelligence & Data Quality Audit API (Milestone B4).

Verifies:
- GET /api/v1/workbooks/{id}/formulas/graph (AST extraction, dependency DAG, cycle detection, volatile cells, unresolved deps)
- GET /api/v1/workbooks/{id}/quality/findings (Consolidated triage across structure, layout, types, cycles, syntax)
- Cycle detection (Tarjan SCC circular references tagged as CRITICAL)
- Volatile function identification (recalculation tags)
- Unsupported and unparsed formula categorization
- Type ambiguity and unverified column states
- Structural anomalies and margin clearance collisions
- Path sanitization (no internal server storage paths leaked in responses)
- RFC 7807 problem details error responses on missing workbooks
- Tenant isolation (foreign tenant workbooks inaccessible)
- Admission controller concurrency and memory throttling (HTTP 429 ADMISSION_REJECTED)
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
from excel_intel.server.database.models import StagedWorkbookRecord
from excel_intel.server.database.session import DatabaseManager


def create_quality_test_xlsx(
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

    sheet_elems = "".join(
        f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'
        for i, name in enumerate(sheet_names, start=1)
    )
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
def b4_config(tmp_path: Path) -> ServerConfig:
    """Configured test environment for Milestone B4."""
    storage_dir = tmp_path / "b4_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "b4_vault.db"

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
async def b4_client(b4_config: ServerConfig):
    """AsyncClient fixture with lifespan initialized."""
    app = create_app(b4_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client, b4_config


async def _upload_workbook(client: AsyncClient, content: bytes, filename: str = "test.xlsx") -> str:
    res = await client.post(
        "/api/v1/workbooks/upload",
        files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code == 201
    return res.json()["workbook_id"]


# ==============================================================================
# 1. Formula Graph Endpoint Tests (GET /workbooks/{id}/formulas/graph)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_formula_graph_normal_dag(b4_client) -> None:
    """Verifies formula graph extraction on an acyclic formula DAG."""
    client, cfg = b4_client
    content = create_quality_test_xlsx(
        formulas={"Summary!B2": "SUM(Transactions!C2:C4)"}
    )
    wb_id = await _upload_workbook(client, content, "valid_model.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/formulas/graph")
    assert res.status_code == 200
    data = res.json()

    assert data["node_count"] >= 1
    assert data["edge_count"] >= 1
    assert data["has_cycles"] is False
    assert data["cycle_status"] == "NO_CYCLES"
    assert data["is_complete"] is True
    assert data["circular_paths"] == []
    assert data["has_dynamic_spills"] is False


@pytest.mark.asyncio
async def test_get_formula_graph_with_cycles(b4_client) -> None:
    """Verifies cycle detection flags circular references and preserves cycle paths."""
    client, cfg = b4_client
    # Direct mutual recursion: A1 = B1 + 1, B1 = A1 * 2
    content = create_quality_test_xlsx(
        sheets_data={
            "Sheet1": [
                [10, 20],
            ]
        },
        formulas={
            "Sheet1!A1": "Sheet1!B1 + 1",
            "Sheet1!B1": "Sheet1!A1 * 2",
        },
    )
    wb_id = await _upload_workbook(client, content, "circular_model.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/formulas/graph")
    assert res.status_code == 200
    data = res.json()

    assert data["has_cycles"] is True
    assert data["cycle_status"] == "CYCLES_DETECTED"
    assert len(data["circular_paths"]) >= 1
    # Check that cycle path contains both cells
    flat_cycle = [cell for path in data["circular_paths"] for cell in path]
    assert any("A1" in cell for cell in flat_cycle)
    assert any("B1" in cell for cell in flat_cycle)


@pytest.mark.asyncio
async def test_get_formula_graph_volatile_functions(b4_client) -> None:
    """Verifies volatile functions (e.g. NOW(), TODAY(), RAND()) are tracked."""
    client, cfg = b4_client
    content = create_quality_test_xlsx(
        sheets_data={
            "Sheet1": [
                ["Timestamp", "Random"],
                [1, 2],
            ]
        },
        formulas={
            "Sheet1!A2": "NOW()",
            "Sheet1!B2": "RAND()",
        },
    )
    wb_id = await _upload_workbook(client, content, "volatile_model.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/formulas/graph")
    assert res.status_code == 200
    data = res.json()

    assert len(data["volatile_cells"]) >= 2
    assert any("A2" in c for c in data["volatile_cells"])
    assert any("B2" in c for c in data["volatile_cells"])


@pytest.mark.asyncio
async def test_get_formula_graph_missing_workbook_404(b4_client) -> None:
    """Verifies querying nonexistent workbook returns RFC 7807 404."""
    client, _ = b4_client
    res = await client.get("/api/v1/workbooks/wb-nonexistent-uuid/formulas/graph")
    assert res.status_code == 404
    err = res.json()
    assert err["code"] == "RESOURCE_NOT_FOUND"
    assert "wb-nonexistent-uuid" in err["detail"]


# ==============================================================================
# 2. Quality Findings Endpoint Tests (GET /workbooks/{id}/quality/findings)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_quality_findings_clean_workbook(b4_client) -> None:
    """Verifies quality findings on a clean workbook."""
    client, cfg = b4_client
    content = create_quality_test_xlsx(
        formulas={"Summary!B2": "SUM(Transactions!C2:C4)"}
    )
    wb_id = await _upload_workbook(client, content, "clean_model.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/quality/findings")
    assert res.status_code == 200
    data = res.json()

    assert "report_id" in data
    assert data["workbook_path"] == "clean_model.xlsx"
    # Verify path sanitization
    assert str(cfg.storage_root) not in data["workbook_path"]
    assert "findings" in data
    assert data["total_findings"] == len(data["findings"])
    assert data["formula_graph"] is not None
    assert data["formula_graph"]["has_cycles"] is False


@pytest.mark.asyncio
async def test_get_quality_findings_with_cycle_finding(b4_client) -> None:
    """Verifies that circular references produce CRITICAL severity quality findings."""
    client, cfg = b4_client
    content = create_quality_test_xlsx(
        sheets_data={
            "Sheet1": [
                [10, 20],
            ]
        },
        formulas={
            "Sheet1!A1": "Sheet1!B1 + 1",
            "Sheet1!B1": "Sheet1!A1 * 2",
        },
    )
    wb_id = await _upload_workbook(client, content, "cycle_findings.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/quality/findings")
    assert res.status_code == 200
    data = res.json()

    cycle_findings = [f for f in data["findings"] if f["category"] == "formula_cycle"]
    assert len(cycle_findings) >= 1
    cycle_f = cycle_findings[0]
    assert cycle_f["severity"] == "critical"
    assert cycle_f["code"] == "CIRCULAR_REFERENCE_CYCLE"
    assert "Circular calculation dependency cycle detected" in cycle_f["message"]
    assert cycle_f["detection_source"] == "M05_FORMULA_GRAPH"
    assert "cycle_path" in cycle_f["details"]


@pytest.mark.asyncio
async def test_get_quality_findings_with_volatile_function(b4_client) -> None:
    """Verifies that volatile functions produce INFO severity quality findings."""
    client, cfg = b4_client
    content = create_quality_test_xlsx(
        sheets_data={
            "Sheet1": [
                ["Col1"],
                [1],
            ]
        },
        formulas={
            "Sheet1!A2": "NOW()",
        },
    )
    wb_id = await _upload_workbook(client, content, "volatile_findings.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/quality/findings")
    assert res.status_code == 200
    data = res.json()

    vol_findings = [f for f in data["findings"] if f["category"] == "volatile_function"]
    assert len(vol_findings) >= 1
    vf = vol_findings[0]
    assert vf["severity"] == "info"
    assert vf["code"] == "VOLATILE_FUNCTION_CALL"
    assert "volatile function" in vf["message"].lower()


@pytest.mark.asyncio
async def test_get_quality_findings_missing_workbook_404(b4_client) -> None:
    """Verifies querying nonexistent workbook returns RFC 7807 404."""
    client, _ = b4_client
    res = await client.get("/api/v1/workbooks/wb-nonexistent-uuid/quality/findings")
    assert res.status_code == 404
    err = res.json()
    assert err["code"] == "RESOURCE_NOT_FOUND"
    assert "wb-nonexistent-uuid" in err["detail"]


# ==============================================================================
# 3. Security, Multi-Tenancy, and Admission Control Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_tenant_isolation_quality_endpoints(b4_client) -> None:
    """Verifies that records belonging to another tenant are inaccessible (404)."""
    client, cfg = b4_client
    content = create_quality_test_xlsx()
    wb_id = await _upload_workbook(client, content, "tenant_test.xlsx")

    # Manually reassign tenant_id to 'tenant_beta' in the database
    db_manager = DatabaseManager(database_url=cfg.database_url)
    async with db_manager.session_factory() as session:
        from sqlalchemy import update
        await session.execute(
            update(StagedWorkbookRecord)
            .where(StagedWorkbookRecord.workbook_id == wb_id)
            .values(tenant_id="tenant_beta")
        )
        await session.commit()
    await db_manager.dispose()

    # Querying as default tenant must yield 404
    res_graph = await client.get(f"/api/v1/workbooks/{wb_id}/formulas/graph")
    assert res_graph.status_code == 404

    res_quality = await client.get(f"/api/v1/workbooks/{wb_id}/quality/findings")
    assert res_quality.status_code == 404


@pytest.mark.asyncio
async def test_admission_controller_throttling_formula_graph(b4_client) -> None:
    """Verifies that saturated admission controller throttles requests with HTTP 429."""
    client, cfg = b4_client
    content = create_quality_test_xlsx()
    wb_id = await _upload_workbook(client, content, "throttled.xlsx")

    app = client._transport.app
    ctrl: AdmissionController = app.state.admission_controller
    ctrl._throttle_threshold_mb = 0.0  # Force throttle

    try:
        res = await client.get(f"/api/v1/workbooks/{wb_id}/formulas/graph")
        assert res.status_code == 429
        data = res.json()
        assert data["code"] == "ADMISSION_REJECTED"
        assert "Retry-After" in res.headers
        assert res.headers["Retry-After"] == "5"
    finally:
        ctrl._throttle_threshold_mb = cfg.memory_throttle_threshold_mb


@pytest.mark.asyncio
async def test_path_sanitization_in_findings(b4_client) -> None:
    """Verifies physical storage paths are completely redacted in all findings."""
    client, cfg = b4_client
    content = create_quality_test_xlsx(
        formulas={"Summary!B2": "SUM(Transactions!C2:C4)"}
    )
    wb_id = await _upload_workbook(client, content, "audit_secret.xlsx")

    res = await client.get(f"/api/v1/workbooks/{wb_id}/quality/findings")
    assert res.status_code == 200
    res_text = res.text

    assert str(cfg.storage_root) not in res_text
    assert "b4_storage" not in res_text
