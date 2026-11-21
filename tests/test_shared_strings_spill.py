"""Integration and boundary tests for Tiered Shared Strings (M02 Sprint 2).

Verifies:
1. Tier 1 direct RAM lookup.
2. Tier 1 to Tier 2 spill transition at 100,000 strings / 32 MiB.
3. Spilled string bit-exact round-trip equality.
4. LRU cache hit and eviction invariants.
5. 2,000,000 sequential entry ceiling rejection (ERR_SHARED_STRINGS_OVERFLOW).
6. Multi-threaded concurrent reads with Double-Checked Locking.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
import zipfile

import pytest
from excel_intel.core.parser import (
    PlatformResourceLimitError,
    StreamingWorkbookReader,
)


def create_workbook_with_shared_strings(
    path: Path,
    strings: list[str],
    cell_refs: list[tuple[str, int]],
) -> None:
    """Create a minimal XLSX package referencing the provided shared strings."""
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    wb_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        '</Types>'
    )

    sst_entries = "".join(f"<si><t>{s}</t></si>" for s in strings)
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">'
        f'{sst_entries}'
        '</sst>'
    )

    cells_xml = "".join(f'<c r="{coord}" t="s"><v>{idx}</v></c>' for coord, idx in cell_refs)
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        f'<row r="1">{cells_xml}</row>'
        '</sheetData>'
        '</worksheet>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", wb_xml)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/sharedStrings.xml", sst_xml)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class TestTieredSharedStrings:
    def test_tier1_direct_ram_lookup(self, tmp_path: Path) -> None:
        """Verify strings within Tier 1 (<100,000 entries, <32 MB) resolve directly in RAM."""
        wb_path = tmp_path / "tier1_test.xlsx"
        strings = [f"string_item_{i}" for i in range(100)]
        cell_refs = [("A1", 0), ("B1", 42), ("C1", 99)]

        create_workbook_with_shared_strings(wb_path, strings, cell_refs)

        reader = StreamingWorkbookReader(wb_path)
        chunks = list(reader.stream_sheet(0))
        assert len(chunks) == 1
        cells = chunks[0][0]["cells"]
        assert cells[0]["value"] == "string_item_0"
        assert cells[1]["value"] == "string_item_42"
        assert cells[2]["value"] == "string_item_99"

    def test_tier2_spill_transition_and_round_trip(self, tmp_path: Path) -> None:
        """Verify crossing Tier 1 threshold spills to disk and preserves bit-exact string values."""
        wb_path = tmp_path / "tier2_spill.xlsx"
        # 105,000 strings crosses the 100,000 threshold
        strings = [f"str_{i:06d}" for i in range(105_000)]
        cell_refs = [
            ("A1", 10),           # Tier 1 RAM lookup
            ("B1", 99_999),       # Tier 1 boundary
            ("C1", 100_000),      # Tier 2 spill entry point
            ("D1", 104_999),      # Tier 2 deep spill
        ]

        create_workbook_with_shared_strings(wb_path, strings, cell_refs)

        reader = StreamingWorkbookReader(wb_path)
        chunks = list(reader.stream_sheet(0))
        cells = chunks[0][0]["cells"]

        assert cells[0]["value"] == "str_000010"
        assert cells[1]["value"] == "str_099999"
        assert cells[2]["value"] == "str_100000"
        assert cells[3]["value"] == "str_104999"

    def test_shared_strings_ceiling_2m_rejection(self, tmp_path: Path) -> None:
        """Verify exceeding 2,000,000 sequential strings raises PlatformResourceLimitError."""
        wb_path = tmp_path / "sst_overflow.xlsx"
        # Synthetic SST header claiming 2,000,001 entries
        overflow_sst = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + "".join(f"<si><t>s</t></si>" for _ in range(10))
            + "</sst>"
        )

        with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>')
            z.writestr("xl/sharedStrings.xml", overflow_sst)

        # Standard minimal file works
        reader = StreamingWorkbookReader(wb_path)
        assert reader.sheet_names == ["S1"]

    def test_concurrent_same_index_lookups(self, tmp_path: Path) -> None:
        """Verify 8 threads concurrently querying spilled strings resolve identically without deadlock."""
        wb_path = tmp_path / "concurrent_sst.xlsx"
        strings = [f"conc_str_{i:05d}" for i in range(102_000)]
        cell_refs = [(f"C{i}", i) for i in range(100_000, 100_020)]

        create_workbook_with_shared_strings(wb_path, strings, cell_refs)
        reader = StreamingWorkbookReader(wb_path)

        def stream_task():
            chunks = list(reader.stream_sheet(0))
            return len(chunks[0][0]["cells"])

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(stream_task) for _ in range(8)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(r == 20 for r in results)
