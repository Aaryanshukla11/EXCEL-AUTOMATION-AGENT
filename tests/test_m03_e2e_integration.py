"""End-to-End Integration Verification Suite for M03 Inspection Subsystem.

Validates the full M03 pipeline on a complex multi-sheet workbook covering:
1. Multiple worksheets (visible, hidden, veryHidden).
2. Declared ListObjects vs inferred candidate regions.
3. Merged cell ranges and hidden rows/columns.
4. Diverse layouts: tabular, key-value, empty, sparse matrix, multi-table composite.
5. Understated declared dimensions vs actual discovered coordinates.
6. Extreme coordinates (col 16384, row 50000).
7. Formula columns with constant inconsistencies.
8. Strict separation of declared OpenXML facts from heuristic inferences.
9. Determinism, JSON serialization, and source file immutability.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import pytest
from excel_intel.inspection import (
    AnomalySeverity,
    BoundingBox,
    EvidenceCode,
    LayoutClassification,
    RegionRole,
    RegionType,
    SheetVisibility,
    WorkbookInspectionReport,
    WorkbookInspector,
)


def create_comprehensive_e2e_workbook(tmp_path: Path) -> Path:
    """Build a rich 5-sheet workbook exercising all structural scenarios."""
    wb_path = tmp_path / "e2e_integration.xlsx"

    # Sheet 1: Tabular data with declared ListObject, merges, hidden rows/cols
    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:E20"/>'
        '<cols>'
        '<col min="2" max="2" hidden="1"/>'  # Col B hidden
        "</cols>"
        "<sheetData>"
        # Header row
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>RecordID</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>SecretKey</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Amount</t></is></c>'
        '<c r="D1" t="inlineStr"><is><t>Tax</t></is></c>'
        '<c r="E1" t="inlineStr"><is><t>Total</t></is></c>'
        "</row>"
        # Data rows 2 to 20
        + "".join(
            f'<row r="{r}"{" hidden=\"1\"" if r == 5 else ""}>'
            f'<c r="A{r}"><v>{r-1}</v></c>'
            f'<c r="B{r}" t="inlineStr"><is><t>SEC_{r}</t></is></c>'
            f'<c r="C{r}"><v>{(r-1) * 100.0}</v></c>'
            f'<c r="D{r}"><f>C{r}*0.18</f><v>{(r-1) * 18.0}</v></c>'
            f'<c r="E{r}"><f>C{r}+D{r}</f><v>{(r-1) * 118.0}</v></c>'
            f"</row>"
            for r in range(2, 21)
        )
        + "</sheetData>"
        '<mergeCells count="1">'
        '<mergeCell ref="A21:E21"/>'  # Summary footer merge outside table
        "</mergeCells>"
        '<tableParts count="1">'
        '<tablePart r:id="rIdTable1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
        "</tableParts>"
        "</worksheet>"
    )

    # Table 1 XML
    table1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'id="1" name="TransactionsTable" displayName="TransactionsTable" ref="A1:E20" headerRowCount="1">'
        '<autoFilter ref="A1:E20"/>'
        '<tableColumns count="5">'
        '<tableColumn id="1" name="RecordID"/>'
        '<tableColumn id="2" name="SecretKey"/>'
        '<tableColumn id="3" name="Amount"/>'
        '<tableColumn id="4" name="Tax"/>'
        '<tableColumn id="5" name="Total"/>'
        "</tableColumns>"
        "</table>"
    )

    # Sheet 1 relationships
    sheet1_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rIdTable1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" '
        'Target="../tables/table1.xml"/>'
        "</Relationships>"
    )

    # Sheet 2: Hidden sheet with Key-Value grid & Understated Dimension
    # Declared as A1:B2, but data extends down to B10
    sheet2_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:B2"/>'
        "<sheetData>"
        + "".join(
            f'<row r="{r}">'
            f'<c r="A{r}" t="inlineStr"><is><t>Setting_{r}</t></is></c>'
            f'<c r="B{r}"><v>{r * 50}</v></c>'
            f"</row>"
            for r in range(1, 11)
        )
        + "</sheetData>"
        "</worksheet>"
    )

    # Sheet 3: VeryHidden sheet, completely empty
    sheet3_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:A1"/>'
        "<sheetData/>"
        "</worksheet>"
    )

    # Sheet 4: Sparse Matrix with extreme coordinates (XFD = 16384, row 50000)
    sheet4_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:XFD50000"/>'
        "<sheetData>"
        '<row r="1"><c r="A1"><v>100</v></c></row>'
        '<row r="25000"><c r="M25000"><v>200</v></c></row>'
        '<row r="50000"><c r="XFD50000"><v>300</v></c></row>'
        "</sheetData>"
        "</worksheet>"
    )

    # Sheet 5: Multi-table layout with formula inconsistency and jagged rows
    # Block 1 (rows 1..4, cols A..C): 3 cols, with row 3 having only 1 cell (jagged)
    # Block 2 (rows 10..15, cols A..B): Formula col with 1 hardcoded constant
    sheet5_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<dimension ref="A1:C15"/>'
        "<sheetData>"
        # Block 1 (rows 1..4, cols A..E with row 3 having only 1 cell)
        '<row r="1"><c r="A1"><v>1</v></c><c r="B1"><v>2</v></c><c r="C1"><v>3</v></c><c r="D1"><v>4</v></c><c r="E1"><v>5</v></c></row>'
        '<row r="2"><c r="A2"><v>6</v></c><c r="B2"><v>7</v></c><c r="C2"><v>8</v></c><c r="D2"><v>9</v></c><c r="E2"><v>10</v></c></row>'
        '<row r="3"><c r="A3"><v>11</v></c></row>'  # Highly jagged row
        '<row r="4"><c r="A4"><v>12</v></c><c r="B4"><v>13</v></c><c r="C4"><v>14</v></c><c r="D4"><v>15</v></c><c r="E4"><v>16</v></c></row>'
        # Gap: rows 5..9 empty
        # Block 2: rows 10..15 (Col B has 5 formulas and 1 constant)
        '<row r="10"><c r="A10"><v>10</v></c><c r="B10"><f>A10*2</f><v>20</v></c></row>'
        '<row r="11"><c r="A11"><v>11</v></c><c r="B11"><f>A11*2</f><v>22</v></c></row>'
        '<row r="12"><c r="A12"><v>12</v></c><c r="B12"><f>A12*2</f><v>24</v></c></row>'
        '<row r="13"><c r="A13"><v>13</v></c><c r="B13"><f>A13*2</f><v>26</v></c></row>'
        '<row r="14"><c r="A14"><v>14</v></c><c r="B14"><f>A14*2</f><v>28</v></c></row>'
        '<row r="15"><c r="A15"><v>15</v></c><c r="B15"><v>999</v></c></row>'  # Constant in formula column
        "</sheetData>"
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
            '<Override PartName="/xl/worksheets/sheet4.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/worksheets/sheet5.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/tables/table1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>'
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
            '<calcPr calcMode="auto" fullCalcOnLoad="1"/>'
            "<sheets>"
            '<sheet name="Transactions" sheetId="1" r:id="rId1"/>'
            '<sheet name="AppSettings" sheetId="2" state="hidden" r:id="rId2"/>'
            '<sheet name="AuditArchive" sheetId="3" state="veryHidden" r:id="rId3"/>'
            '<sheet name="ScatterPlot" sheetId="4" r:id="rId4"/>'
            '<sheet name="CompositeData" sheetId="5" r:id="rId5"/>'
            "</sheets>"
            "<definedNames>"
            '<definedName name="GlobalVAT">0.20</definedName>'
            '<definedName name="LocalConfig" localSheetId="1">AppSettings!$A$1:$B$10</definedName>'
            '<definedName name="_xlnm._FilterDatabase" hidden="1" localSheetId="0">Transactions!$A$1:$E$20</definedName>'
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
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet4.xml"/>'
            '<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet5.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        z.writestr("xl/worksheets/_rels/sheet1.xml.rels", sheet1_rels)
        z.writestr("xl/tables/table1.xml", table1_xml)
        z.writestr("xl/worksheets/sheet2.xml", sheet2_xml)
        z.writestr("xl/worksheets/sheet3.xml", sheet3_xml)
        z.writestr("xl/worksheets/sheet4.xml", sheet4_xml)
        z.writestr("xl/worksheets/sheet5.xml", sheet5_xml)

    return wb_path


def test_full_pipeline_e2e_integration(tmp_path: Path) -> None:
    """Verify complete end-to-end inspection of a multi-sheet complex workbook."""
    wb_path = create_comprehensive_e2e_workbook(tmp_path)

    with open(wb_path, "rb") as f:
        sha_before = hashlib.sha256(f.read()).hexdigest()

    report = WorkbookInspector.inspect(wb_path)

    # 1. Package Metadata Verification
    assert isinstance(report, WorkbookInspectionReport)
    assert report.package_type == "xlsx"
    assert not report.is_1904
    assert not report.has_macros
    assert report.calc_pr.get("calcMode") == "auto"
    assert report.calc_pr.get("fullCalcOnLoad") is True

    # Defined Names
    assert len(report.defined_names) == 3
    names_by_name = {dn.name: dn for dn in report.defined_names}
    assert "GlobalVAT" in names_by_name
    assert names_by_name["GlobalVAT"].scope == "workbook"
    assert "LocalConfig" in names_by_name
    assert names_by_name["LocalConfig"].scope == "AppSettings"
    assert "_xlnm._FilterDatabase" in names_by_name
    assert names_by_name["_xlnm._FilterDatabase"].is_hidden

    # 2. Sheet Catalog & Visibility
    assert len(report.sheets) == 5

    # Sheet 1: Transactions (Visible, Declared Table, Merged Cells, Hidden Row/Col)
    s1 = report.sheets[0]
    assert s1.sheet_name == "Transactions"
    assert s1.facts.properties.visibility == SheetVisibility.VISIBLE
    assert s1.actual_cell_count == 100  # 20 rows * 5 cols
    assert s1.profile.layout_classification == LayoutClassification.SINGLE_TABLE
    # Declared OpenXML Table
    assert len(s1.facts.list_objects) == 1
    tbl = s1.facts.list_objects[0]
    assert tbl.name == "TransactionsTable"
    assert tbl.column_names == ["RecordID", "SecretKey", "Amount", "Tax", "Total"]
    assert tbl.has_auto_filter
    # Declared ListObject hypothesis
    hypo_tbl = next(h for h in s1.region_hypotheses if h.role == RegionRole.DECLARED_LIST_OBJECT)
    assert hypo_tbl.confidence_score == 1.0
    assert EvidenceCode.LIST_OBJECT_DECLARED in hypo_tbl.evidence_codes
    # Merged Cells
    assert len(s1.facts.merge_cells) == 1
    assert s1.facts.merge_cells[0].ref == "A21:E21"
    # Hidden Rows & Columns
    assert len(s1.facts.hidden_rows) == 1
    assert s1.facts.hidden_rows[0].start == 5
    assert s1.facts.hidden_rows[0].end == 5
    assert len(s1.facts.hidden_columns) == 1
    assert s1.facts.hidden_columns[0].start == 2
    assert s1.facts.hidden_columns[0].end == 2

    # Sheet 2: AppSettings (Hidden, Key-Value Grid, Understated Dimension)
    s2 = report.sheets[1]
    assert s2.sheet_name == "AppSettings"
    assert s2.facts.properties.visibility == SheetVisibility.HIDDEN
    assert s2.profile.layout_classification == LayoutClassification.KEY_VALUE_GRID
    assert s2.actual_cell_count == 20  # 10 rows * 2 cols
    # Understated dimension anomaly check
    understated_anoms = [a for a in s2.anomalies if a.code == "ANOM_UNDERSTATED_DIMENSION"]
    assert len(understated_anoms) == 1
    assert understated_anoms[0].severity == AnomalySeverity.WARNING
    assert "declared A1:B2, actual A1:B10" in understated_anoms[0].message

    # Sheet 3: AuditArchive (VeryHidden, Empty)
    s3 = report.sheets[2]
    assert s3.sheet_name == "AuditArchive"
    assert s3.facts.properties.visibility == SheetVisibility.VERY_HIDDEN
    assert s3.actual_cell_count == 0
    assert s3.profile.layout_classification == LayoutClassification.EMPTY
    assert len(s3.region_hypotheses) == 0

    # Sheet 4: ScatterPlot (Sparse Matrix, Extreme Coordinates XFD = 16384, row 50000)
    s4 = report.sheets[3]
    assert s4.sheet_name == "ScatterPlot"
    assert s4.profile.layout_classification == LayoutClassification.SPARSE_MATRIX
    assert s4.actual_cell_count == 3
    assert s4.profile.actual_bounding_box.min_row == 1
    assert s4.profile.actual_bounding_box.max_row == 50000
    assert s4.profile.actual_bounding_box.min_col == 1
    assert s4.profile.actual_bounding_box.max_col == 16384  # XFD

    # Sheet 5: CompositeData (Multi-table, Jagged rows, Formula inconsistencies)
    s5 = report.sheets[4]
    assert s5.sheet_name == "CompositeData"
    assert s5.profile.layout_classification == LayoutClassification.MULTI_TABLE
    # Content anomalies: Jagged row + Formula inconsistency
    codes = {a.code for a in s5.anomalies}
    assert "ANOM_JAGGED_ROW_STRUCTURE" in codes
    assert "ANOM_FORMULA_INCONSISTENCY" in codes

    # 3. Determinism & Serialization Roundtrip
    json_str = report.model_dump_json()
    roundtrip_report = WorkbookInspectionReport.model_validate_json(json_str)
    assert report.model_dump() == roundtrip_report.model_dump()

    # 4. Source Immutability
    with open(wb_path, "rb") as f:
        sha_after = hashlib.sha256(f.read()).hexdigest()
    assert sha_before == sha_after, "Source workbook was mutated by inspection pipeline!"
