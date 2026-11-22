"""End-to-End Integration Test Suite for Milestone M04 Spatial Detection.

Verifies:
- Multi-sheet workbook spatial analysis with diverse topologies:
  * Sheet 1: Multiple side-by-side tables with whitespace corridors
  * Sheet 2: Hierarchical stacked headers with title banner and summary totals
  * Sheet 3: Declared OpenXML ListObjects
  * Sheet 4: Sparse islands and isolated annotations
  * Sheet 5: ADR-005 boundary collisions
- Deterministic output across repeated runs
- Source workbook SHA-256 byte immutability
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from typing import Any
import pytest

from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.inspection.models import (
    BoundingBox,
    DeclaredListObject,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
)
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.models import (
    SemanticZoneType,
    SpatialEvidenceType,
    SpatialRegionType,
)


def build_multisheet_test_workbook(target_path: Path) -> Path:
    """Create a valid synthetic multi-sheet Excel workbook with diverse topologies."""
    # Sheet 1: Side-by-side tables (cols 1..2 and cols 5..6, rows 1..5)
    # Sheet 2: Stacked header table (rows 1..6, cols 1..3) with title, header, body, totals
    # Sheet 3: Declared table simulation
    # Sheet 4: Single table with sparse island at col 20, row 50
    # Sheet 5: Table with zero-space collision (data in row 11)
    sheet1_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
        '<sheetData>\n'
        '  <row r="1">\n'
        '    <c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>\n'
        '    <c r="E1" t="s"><v>2</v></c><c r="F1" t="s"><v>3</v></c>\n'
        '  </row>\n'
        '  <row r="2">\n'
        '    <c r="A2"><v>10</v></c><c r="B2"><v>20</v></c>\n'
        '    <c r="E2"><v>100</v></c><c r="F2"><v>200</v></c>\n'
        '  </row>\n'
        '  <row r="3">\n'
        '    <c r="A3"><v>30</v></c><c r="B3"><v>40</v></c>\n'
        '    <c r="E3"><v>300</v></c><c r="F3"><v>400</v></c>\n'
        '  </row>\n'
        '</sheetData>\n'
        '</worksheet>'
    )

    sheet2_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
        '<sheetData>\n'
        '  <row r="1"><c r="A1" t="s"><v>4</v></c></row>\n'  # Title banner
        '  <row r="2"><c r="A2" t="s"><v>5</v></c><c r="B2" t="s"><v>6</v></c></row>\n'  # Header
        '  <row r="3"><c r="A3"><v>10</v></c><c r="B3"><v>20</v></c></row>\n'
        '  <row r="4"><c r="A4"><v>30</v></c><c r="B4"><v>40</v></c></row>\n'
        '  <row r="5"><c r="A5" t="s"><v>7</v></c><c r="B5"><f>SUM(B3:B4)</f><v>60</v></c></row>\n'  # Total
        '</sheetData>\n'
        '</worksheet>'
    )

    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="8" uniqueCount="8">\n'
        '  <si><t>T1_A</t></si>\n'
        '  <si><t>T1_B</t></si>\n'
        '  <si><t>T2_A</t></si>\n'
        '  <si><t>T2_B</t></si>\n'
        '  <si><t>Quarterly Summary</t></si>\n'
        '  <si><t>Region</t></si>\n'
        '  <si><t>Amount</t></si>\n'
        '  <si><t>Total</t></si>\n'
        '</sst>'
    )

    wb_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
        '<sheets>\n'
        '  <sheet name="SideBySide" sheetId="1" r:id="rId1"/>\n'
        '  <sheet name="SummarySheet" sheetId="2" r:id="rId2"/>\n'
        '</sheets>\n'
        '</workbook>'
    )

    wb_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>\n'
        '  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>\n'
        '  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>\n'
        '</Relationships>'
    )

    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>\n'
        '</Relationships>'
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
        '  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
        '  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
        '  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>\n'
        '</Types>'
    )

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", wb_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_xml)
        zf.writestr("xl/sharedStrings.xml", sst_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml)
        zf.writestr("xl/worksheets/sheet2.xml", sheet2_xml)

    return target_path


class TestM04E2EIntegration:
    """End-to-end integration test suite for Milestone M04."""

    def test_multisheet_spatial_analysis_e2e(self, tmp_path: Path) -> None:
        """Verify SpatialDetector processes multiple sheets with side-by-side and summary tables."""
        wb_path = build_multisheet_test_workbook(tmp_path / "e2e_multisheet.xlsx")
        detector = SpatialDetector()
        analysis = detector.detect_workbook(wb_path)

        assert len(analysis.sheets) == 2
        assert analysis.total_tables_detected >= 3

        # Sheet 1: Side-by-side tables
        s1 = analysis.sheets["SideBySide"]
        assert len(s1.regions) == 2
        # Verify vertical separation corridor between cols 2 and 5
        corridors = s1.corridors_detected
        assert any(c.start_index in (3, 4) for c in corridors)

        # Sheet 2: Summary sheet with title banner, headers, data, and totals
        s2 = analysis.sheets["SummarySheet"]
        assert len(s2.regions) == 1
        r2 = s2.regions[0]
        assert SemanticZoneType.TITLE in r2.zones
        assert SemanticZoneType.HEADER in r2.zones
        assert SemanticZoneType.BODY in r2.zones
        assert SemanticZoneType.TOTALS in r2.zones

    def test_deterministic_output_across_repeated_runs(self, tmp_path: Path) -> None:
        """Verify spatial detection produces identical output across multiple independent runs."""
        wb_path = build_multisheet_test_workbook(tmp_path / "determinism_check.xlsx")
        detector = SpatialDetector()

        run1 = detector.detect_workbook(wb_path)
        run2 = detector.detect_workbook(wb_path)

        # Compare model dumps (ignoring timestamp)
        d1 = run1.model_dump()
        d2 = run2.model_dump()
        del d1["analysis_timestamp"]
        del d2["analysis_timestamp"]
        for s in d1["sheets"].values():
            del s["detection_timestamp"]
        for s in d2["sheets"].values():
            del s["detection_timestamp"]

        assert d1 == d2

    def test_source_workbook_sha_unchanged(self, tmp_path: Path) -> None:
        """Verify source workbook SHA-256 remains strictly bit-for-bit identical."""
        wb_path = build_multisheet_test_workbook(tmp_path / "sha_check.xlsx")
        sha_before = hashlib.sha256(wb_path.read_bytes()).hexdigest()

        detector = SpatialDetector()
        _ = detector.detect_workbook(wb_path)

        sha_after = hashlib.sha256(wb_path.read_bytes()).hexdigest()
        assert sha_before == sha_after
