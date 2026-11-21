"""Tests for M03 Workbook Inspector Facade (inspector.py).

Verifies:
1. End-to-end inspection of multi-sheet workbooks.
2. Individual sheet inspection by name and index.
3. Clean context management (with-statement) and self-closing classmethod.
4. Correct aggregation of package facts, topology facts, content profiles, and anomalies.
5. Deterministic output across repeated runs.
6. Thread safety and concurrent inspection isolation.
7. Source workbook SHA-256 byte-level immutability.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import zipfile

import pytest
from excel_intel.inspection import (
    LayoutClassification,
    RegionRole,
    SheetVisibility,
    WorkbookInspectionReport,
    WorkbookInspector,
)


def create_comprehensive_workbook(
    tmp_path: Path,
    filename: str = "facade_test.xlsx",
) -> Path:
    """Build a multi-sheet OpenXML workbook with tables, defined names, hidden sheets."""
    wb_path = tmp_path / filename

    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:C10"/>'
        "<sheetData>"
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>ID</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Amount</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Status</t></is></c>'
        "</row>"
        '<row r="2"><c r="A2"><v>1</v></c><c r="B2"><v>100.5</v></c><c r="C2" t="inlineStr"><is><t>OK</t></is></c></row>'
        '<row r="3"><c r="A3"><v>2</v></c><c r="B3"><v>200.0</v></c><c r="C3" t="inlineStr"><is><t>OK</t></is></c></row>'
        "</sheetData>"
        "</worksheet>"
    )

    sheet2_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:B5"/>'
        "<sheetData>"
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Config_Key</t></is></c><c r="B1"><v>123</v></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>Timeout</t></is></c><c r="B2"><v>30</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>MaxRetries</t></is></c><c r="B3"><v>3</v></c></row>'
        "</sheetData>"
        "</worksheet>"
    )

    sheet3_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:A1"/>'
        "<sheetData/>"
        "</worksheet>"
    )

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<workbookPr date1904="0"/>'
            '<calcPr calcMode="auto"/>'
            "<sheets>"
            '<sheet name="DataSheet" sheetId="1" r:id="rId1"/>'
            '<sheet name="ConfigSheet" sheetId="2" state="hidden" r:id="rId2"/>'
            '<sheet name="EmptySheet" sheetId="3" state="veryHidden" r:id="rId3"/>'
            "</sheets>"
            "<definedNames>"
            '<definedName name="TaxRate">0.18</definedName>'
            '<definedName name="LocalParam" localSheetId="0">Sheet1!$A$1</definedName>'
            "</definedNames>"
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        z.writestr("xl/worksheets/sheet2.xml", sheet2_xml)
        z.writestr("xl/worksheets/sheet3.xml", sheet3_xml)

    return wb_path


def test_workbook_inspector_full_run(tmp_path: Path) -> None:
    """Verify end-to-end inspect_workbook() on a multi-sheet workbook."""
    wb_path = create_comprehensive_workbook(tmp_path)

    with WorkbookInspector(wb_path) as inspector:
        report = inspector.inspect_workbook()

        assert isinstance(report, WorkbookInspectionReport)
        assert report.workbook_path == str(wb_path.resolve())
        assert report.package_type == "xlsx"
        assert not report.is_1904
        assert not report.has_macros
        assert report.calc_pr.get("calcMode") == "auto"

        # Check defined names
        assert len(report.defined_names) == 2
        name_map = {dn.name: dn for dn in report.defined_names}
        assert "TaxRate" in name_map
        assert name_map["TaxRate"].scope == "workbook"
        assert "LocalParam" in name_map
        assert name_map["LocalParam"].scope == "DataSheet"

        # Check sheets
        assert len(report.sheets) == 3

        # Sheet 1: DataSheet
        s1 = report.sheets[0]
        assert s1.sheet_name == "DataSheet"
        assert s1.facts.properties.visibility == SheetVisibility.VISIBLE
        assert s1.actual_cell_count == 9  # 3 rows * 3 cols
        assert s1.profile.layout_classification == LayoutClassification.SINGLE_TABLE
        assert len(s1.region_hypotheses) >= 1
        assert s1.region_hypotheses[0].role == RegionRole.INFERRED_TABULAR_CANDIDATE

        # Sheet 2: ConfigSheet (Hidden)
        s2 = report.sheets[1]
        assert s2.sheet_name == "ConfigSheet"
        assert s2.facts.properties.visibility == SheetVisibility.HIDDEN
        assert s2.profile.layout_classification == LayoutClassification.KEY_VALUE_GRID

        # Sheet 3: EmptySheet (VeryHidden)
        s3 = report.sheets[2]
        assert s3.sheet_name == "EmptySheet"
        assert s3.facts.properties.visibility == SheetVisibility.VERY_HIDDEN
        assert s3.actual_cell_count == 0
        assert s3.profile.layout_classification == LayoutClassification.EMPTY


def test_inspect_sheet_individually(tmp_path: Path) -> None:
    """Verify inspect_sheet by name and by 0-indexed position."""
    wb_path = create_comprehensive_workbook(tmp_path)

    with WorkbookInspector(wb_path) as inspector:
        sheet_by_name = inspector.inspect_sheet("DataSheet")
        sheet_by_idx = inspector.inspect_sheet(0)

        assert sheet_by_name.sheet_name == "DataSheet"
        assert sheet_by_idx.sheet_name == "DataSheet"
        assert sheet_by_name.actual_cell_count == sheet_by_idx.actual_cell_count

        with pytest.raises(ValueError, match="not found in workbook"):
            inspector.inspect_sheet("NonExistentSheet")

        with pytest.raises(ValueError, match="out of range"):
            inspector.inspect_sheet(99)


def test_classmethod_inspect_helper(tmp_path: Path) -> None:
    """Verify WorkbookInspector.inspect() one-line self-closing interface."""
    wb_path = create_comprehensive_workbook(tmp_path)

    report = WorkbookInspector.inspect(wb_path)
    assert isinstance(report, WorkbookInspectionReport)
    assert len(report.sheets) == 3


def test_inspection_determinism(tmp_path: Path) -> None:
    """Verify consecutive inspections yield structurally identical results."""
    wb_path = create_comprehensive_workbook(tmp_path)

    report1 = WorkbookInspector.inspect(wb_path)
    report2 = WorkbookInspector.inspect(wb_path)

    d1 = report1.model_dump(exclude={"inspection_timestamp"})
    d2 = report2.model_dump(exclude={"inspection_timestamp"})

    assert d1 == d2, "Inspection results differed between consecutive runs!"


def test_source_workbook_immutability(tmp_path: Path) -> None:
    """Verify source workbook file SHA-256 hash is identical before and after inspection."""
    wb_path = create_comprehensive_workbook(tmp_path)

    with open(wb_path, "rb") as f:
        sha_initial = hashlib.sha256(f.read()).hexdigest()

    _ = WorkbookInspector.inspect(wb_path)

    with open(wb_path, "rb") as f:
        sha_after = hashlib.sha256(f.read()).hexdigest()

    assert sha_initial == sha_after, "Inspection altered the source file on disk!"


def test_concurrent_inspections(tmp_path: Path) -> None:
    """Verify thread safety when multiple workers inspect the same workbook concurrently."""
    wb_path = create_comprehensive_workbook(tmp_path)

    def worker(idx: int) -> tuple[int, int]:
        report = WorkbookInspector.inspect(wb_path)
        return idx, len(report.sheets)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker, i) for i in range(8)]
        results = [f.result() for f in futures]

    for idx, sheet_count in results:
        assert sheet_count == 3
