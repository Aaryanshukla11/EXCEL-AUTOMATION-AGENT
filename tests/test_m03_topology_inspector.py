"""Integration tests for M03 Sheet Topology Inspector (topology_inspector.py).

Verifies:
1. Worksheet declared dimension parsing and validation.
2. Missing or malformed dimension element handling.
3. Merged cell range parsing, coordinates, and overlap detection.
4. Hidden row and column interval discovery and contiguous consolidation.
5. Invariant: Source workbook file remains 100% unchanged after inspection.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

import pytest
from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.inspection.models import AnomalySeverity, BoundingBox, HiddenInterval
from excel_intel.inspection.topology_inspector import SheetTopologyInspector


def create_sheet_with_topology(
    tmp_path: Path,
    *,
    dimension_xml: str = '<dimension ref="A1:F50"/>',
    cols_xml: str = '<cols><col min="2" max="3" hidden="1"/><col min="5" max="5" hidden="1"/></cols>',
    sheet_data_xml: str = (
        '<row r="1"><c r="A1"><v>100</v></c></row>'
        '<row r="4" hidden="1"><c r="A4"><v>200</v></c></row>'
        '<row r="5" hidden="1"><c r="A5"><v>300</v></c></row>'
        '<row r="10" hidden="1"><c r="A10"><v>400</v></c></row>'
    ),
    merge_cells_xml: str = (
        '<mergeCells count="2">'
        '<mergeCell ref="A1:B2"/>'
        '<mergeCell ref="D5:E6"/>'
        "</mergeCells>"
    ),
) -> Path:
    """Create synthetic OpenXML workbook with specified sheet topology."""
    wb_path = tmp_path / "topology_test.xlsx"

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"{dimension_xml}"
        f"{cols_xml}"
        f"<sheetData>{sheet_data_xml}</sheetData>"
        f"{merge_cells_xml}"
        "</worksheet>"
    )

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            "</Types>",
        )
        z.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="DataSheet" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    return wb_path


class TestSheetTopologyInspector:
    def test_inspect_declared_dimension(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(
            tmp_path, dimension_xml='<dimension ref="B2:G30"/>'
        )
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, anomalies = inspector.inspect_topology("DataSheet")

            assert facts.declared_dimension is not None
            assert facts.declared_dimension == BoundingBox(
                min_row=2, max_row=30, min_col=2, max_col=7
            )
            assert facts.declared_dimension.to_a1_ref() == "B2:G30"
            assert len(anomalies) == 0

    def test_missing_dimension_element(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(tmp_path, dimension_xml="")
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, anomalies = inspector.inspect_topology("DataSheet")

            assert facts.declared_dimension is None
            assert len(anomalies) == 0

    def test_invalid_dimension_ref_emits_anomaly(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(
            tmp_path, dimension_xml='<dimension ref="INVALID_REF"/>'
        )
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, anomalies = inspector.inspect_topology("DataSheet")

            assert facts.declared_dimension is None
            assert len(anomalies) == 1
            assert anomalies[0].code == "ANOM_INVALID_DIMENSION_REF"
            assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_merged_cells_extraction(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(
            tmp_path,
            merge_cells_xml=(
                '<mergeCells count="2">'
                '<mergeCell ref="A1:C2"/>'
                '<mergeCell ref="E10:F12"/>'
                "</mergeCells>"
            ),
        )
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, anomalies = inspector.inspect_topology("DataSheet")

            assert len(facts.merge_cells) == 2
            m1 = facts.merge_cells[0]
            assert m1.ref == "A1:C2"
            assert m1.top_left_cell == "A1"
            assert m1.box == BoundingBox(min_row=1, max_row=2, min_col=1, max_col=3)

            m2 = facts.merge_cells[1]
            assert m2.ref == "E10:F12"
            assert m2.top_left_cell == "E10"
            assert m2.box == BoundingBox(min_row=10, max_row=12, min_col=5, max_col=6)
            assert len(anomalies) == 0

    def test_overlapping_merge_cells_emit_anomaly(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(
            tmp_path,
            merge_cells_xml=(
                '<mergeCells count="2">'
                '<mergeCell ref="A1:C3"/>'
                '<mergeCell ref="B2:D4"/>'  # Overlaps with A1:C3
                "</mergeCells>"
            ),
        )
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, anomalies = inspector.inspect_topology("DataSheet")

            assert len(facts.merge_cells) == 2
            assert len(anomalies) == 1
            assert anomalies[0].code == "ANOM_OVERLAPPING_MERGE_CELLS"
            assert anomalies[0].severity == AnomalySeverity.WARNING

    def test_hidden_rows_and_columns_consolidated(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(
            tmp_path,
            cols_xml='<cols><col min="2" max="4" hidden="1"/><col min="7" max="7" hidden="1"/></cols>',
            sheet_data_xml=(
                '<row r="3" hidden="1"/>'
                '<row r="4" hidden="1"/>'
                '<row r="8" hidden="1"/>'
            ),
        )
        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, _ = inspector.inspect_topology("DataSheet")

            # Column 2..4, and 7
            assert len(facts.hidden_columns) == 2
            assert facts.hidden_columns[0] == HiddenInterval(
                dimension="col", start=2, end=4
            )
            assert facts.hidden_columns[1] == HiddenInterval(
                dimension="col", start=7, end=7
            )

            # Rows 3..4, and 8
            assert len(facts.hidden_rows) == 2
            assert facts.hidden_rows[0] == HiddenInterval(
                dimension="row", start=3, end=4
            )
            assert facts.hidden_rows[1] == HiddenInterval(
                dimension="row", start=8, end=8
            )

    def test_source_workbook_remains_unchanged(self, tmp_path: Path) -> None:
        wb_path = create_sheet_with_topology(tmp_path)
        initial_bytes = wb_path.read_bytes()
        initial_hash = hashlib.sha256(initial_bytes).hexdigest()

        with StreamingWorkbookReader(wb_path) as reader:
            inspector = SheetTopologyInspector(reader)
            facts, anomalies = inspector.inspect_topology(0)
            assert facts.properties.name == "DataSheet"

        # Verify source file byte-for-byte unchanged
        post_bytes = wb_path.read_bytes()
        post_hash = hashlib.sha256(post_bytes).hexdigest()

        assert initial_bytes == post_bytes
        assert initial_hash == post_hash
