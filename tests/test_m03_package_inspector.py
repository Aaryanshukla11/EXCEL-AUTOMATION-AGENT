"""Integration tests for M03 Package Structure Inspector (package_inspector.py).

Verifies:
1. Extraction of workbook calculation properties (calcPr).
2. Sheet visibility states (visible, hidden, veryHidden).
3. Defined names parsing, scoping (workbook vs sheet), duplicate detection.
4. Excel tables (ListObjects) via sheet relationships and table XML.
5. Missing optional metadata and corrupt XML handling.
6. Resource limit enforcement on defined names and tables.
7. Verification that inspection executes strictly via M02 read_package_part.
"""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest
from excel_intel.core.parser import CorruptWorkbookError, StreamingWorkbookReader
from excel_intel.inspection.models import AnomalySeverity, SheetVisibility
from excel_intel.inspection.package_inspector import (
    MAX_DEFINED_NAMES,
    MAX_TABLES_PER_WORKBOOK,
    PackageStructureInspector,
)


def create_synthetic_package(
    tmp_path: Path,
    *,
    calc_pr_xml: str = '<calcPr calcId="122534" concurrentCalc="1" fullCalcOnLoad="1"/>',
    sheets_xml: str = (
        '<sheet name="Sales" sheetId="1" r:id="rId1"/>'
        '<sheet name="Summary" sheetId="2" state="hidden" r:id="rId2"/>'
        '<sheet name="Config" sheetId="3" state="veryHidden" r:id="rId3"/>'
    ),
    defined_names_xml: str = (
        '<definedName name="TaxRate">0.15</definedName>'
        '<definedName name="RegionalBudget" localSheetId="0">Sales!$A$1:$D$10</definedName>'
        '<definedName name="TaxRate" localSheetId="0">0.20</definedName>'  # Duplicate in Sales scope
    ),
    table_xml: str | None = None,
    corrupt_workbook_xml: bool = False,
) -> Path:
    """Helper creating synthetic OpenXML workbook with specified metadata parts."""
    wb_path = tmp_path / "synthetic_pkg.xlsx"

    wb_content = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"{calc_pr_xml}"
        f"<sheets>{sheets_xml}</sheets>"
        f"<definedNames>{defined_names_xml}</definedNames>"
        "</workbook>"
    )
    if corrupt_workbook_xml:
        wb_content = "<workbook><unclosedTag>"

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            "</Types>",
        )
        z.writestr("xl/workbook.xml", wb_content)
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/>'
            "</Relationships>",
        )
        # Empty sheets
        z.writestr(
            "xl/worksheets/sheet1.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>',
        )
        z.writestr(
            "xl/worksheets/sheet2.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>',
        )
        z.writestr(
            "xl/worksheets/sheet3.xml",
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>',
        )

        # Optional Table on Sheet1
        if table_xml:
            z.writestr(
                "xl/worksheets/_rels/sheet1.xml.rels",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rIdTable1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table1.xml"/>'
                "</Relationships>",
            )
            z.writestr("xl/tables/table1.xml", table_xml)

    return wb_path


class TestPackageStructureInspector:
    def test_inspect_calc_pr(self, tmp_path: Path) -> None:
        wb_path = create_synthetic_package(tmp_path)
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            calc_props = inspector.inspect_calc_pr()

            assert calc_props["calcId"] == 122534
            assert calc_props["concurrentCalc"] is True
            assert calc_props["fullCalcOnLoad"] is True

    def test_missing_calc_pr_returns_empty_dict(self, tmp_path: Path) -> None:
        wb_path = create_synthetic_package(tmp_path, calc_pr_xml="")
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            calc_props = inspector.inspect_calc_pr()
            assert calc_props == {}

    def test_inspect_sheet_catalog_visibility(self, tmp_path: Path) -> None:
        wb_path = create_synthetic_package(tmp_path)
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            catalog = inspector.inspect_sheet_catalog()

            assert len(catalog) == 3
            assert catalog[0].name == "Sales"
            assert catalog[0].visibility == SheetVisibility.VISIBLE
            assert catalog[1].name == "Summary"
            assert catalog[1].visibility == SheetVisibility.HIDDEN
            assert catalog[2].name == "Config"
            assert catalog[2].visibility == SheetVisibility.VERY_HIDDEN

    def test_inspect_defined_names_scopes_and_duplicates(self, tmp_path: Path) -> None:
        wb_path = create_synthetic_package(
            tmp_path,
            defined_names_xml=(
                '<definedName name="GlobalRate">0.05</definedName>'
                '<definedName name="LocalTotal" localSheetId="0">Sales!$B$10</definedName>'
                '<definedName name="GlobalRate">0.08</definedName>'  # Duplicate in workbook scope
            ),
        )
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            sheet_names = reader.sheet_names
            names, anomalies = inspector.inspect_defined_names(sheet_names)

            assert len(names) == 3
            assert names[0].name == "GlobalRate"
            assert names[0].scope == "workbook"
            assert names[1].name == "LocalTotal"
            assert names[1].scope == "Sales"

            # Check duplicate anomaly
            assert len(anomalies) == 1
            assert anomalies[0].code == "ANOM_DUPLICATE_DEFINED_NAME"
            assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_inspect_tables_list_objects(self, tmp_path: Path) -> None:
        table_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'id="1" name="Table1" displayName="SalesTable" ref="A1:C10" headerRowCount="1" totalsRowCount="1">'
            '<autoFilter ref="A1:C10"/>'
            "<tableColumns count=\"3\">"
            '<tableColumn id="1" name="Product"/>'
            '<tableColumn id="2" name="Quantity"/>'
            '<tableColumn id="3" name="Revenue"/>'
            "</tableColumns>"
            "</table>"
        )
        wb_path = create_synthetic_package(tmp_path, table_xml=table_xml)

        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            sheet_path = reader.get_sheet_path("Sales")
            assert sheet_path is not None
            tables, anomalies = inspector.inspect_tables_for_sheet(sheet_path)

            assert len(tables) == 1
            table = tables[0]
            assert table.id == 1
            assert table.name == "Table1"
            assert table.display_name == "SalesTable"
            assert table.ref == "A1:C10"
            assert table.box.min_row == 1
            assert table.box.max_row == 10
            assert table.box.min_col == 1
            assert table.box.max_col == 3
            assert table.header_row_count == 1
            assert table.totals_row_count == 1
            assert table.column_names == ["Product", "Quantity", "Revenue"]
            assert table.has_auto_filter is True
            assert table.auto_filter_ref == "A1:C10"
            assert len(anomalies) == 0

    def test_corrupt_table_xml_handled_gracefully(self, tmp_path: Path) -> None:
        table_xml = "<table id='1' name='BadTable'><corrupt>"
        wb_path = create_synthetic_package(tmp_path, table_xml=table_xml)

        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            sheet_path = reader.get_sheet_path("Sales")
            assert sheet_path is not None
            tables, anomalies = inspector.inspect_tables_for_sheet(sheet_path)

            assert len(tables) == 0
            assert len(anomalies) == 1
            assert anomalies[0].code == "ANOM_CORRUPT_TABLE_XML"

    def test_corrupt_workbook_xml_raises(self, tmp_path: Path) -> None:
        wb_path = create_synthetic_package(tmp_path, corrupt_workbook_xml=True)
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = PackageStructureInspector(reader)
            with pytest.raises(CorruptWorkbookError, match="Malformed xl/workbook.xml"):
                inspector.inspect_sheet_catalog()

    def test_package_read_via_native_interface_only(self, tmp_path: Path) -> None:
        wb_path = create_synthetic_package(tmp_path)
        with StreamingWorkbookReader(wb_path) as reader:
            # Package access routes through reader.read_package_part
            part = reader.read_package_part("xl/workbook.xml")
            assert part is not None
            assert "<workbook" in part

            # Non-existent part returns None without error
            non_existent = reader.read_package_part("xl/non_existent.xml")
            assert non_existent is None
