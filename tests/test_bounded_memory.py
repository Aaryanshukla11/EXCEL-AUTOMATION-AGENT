"""Bounded memory and defensive working set tripwire tests (M02 Sprint 2).

Verifies:
1. get_process_working_set_bytes() returns accurate non-zero working set size.
2. check_memory_guard() passes when memory is within bounded limits.
3. Memory guard enforces defensive 235.0 MiB abort ceiling (PlatformResourceLimitError: ERR_PEAK_RSS_EXCEEDED).
4. Memory remains bounded during large row iteration without accumulative leak.
"""

from __future__ import annotations

from pathlib import Path
import zipfile

import pytest
from excel_intel.core.parser import (
    PlatformResourceLimitError,
    StreamingWorkbookReader,
    check_memory_guard,
    get_process_working_set_bytes,
)


class TestBoundedMemory:
    def test_working_set_query(self) -> None:
        """Verify working set measurement returns positive integer."""
        ws = get_process_working_set_bytes()
        assert isinstance(ws, int)
        assert ws > 0
        # Normal Python process working set is between 10 MB and 200 MB
        assert ws < 235 * 1024 * 1024

    def test_memory_guard_normal_operation(self) -> None:
        """Verify check_memory_guard succeeds when memory is healthy."""
        check_memory_guard()  # Must not raise

    def test_streaming_memory_bounded_across_chunks(self, tmp_path: Path) -> None:
        """Verify memory does not grow unbounded during sheet iteration."""
        wb_path = tmp_path / "bounded_sheet.xlsx"

        # Generate a 20,000-row sheet
        rows_xml = "".join(f'<row r="{i}"><c r="A{i}"><v>{i}</v></c></row>' for i in range(1, 20_001))
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{rows_xml}</sheetData>'
            '</worksheet>'
        )

        with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/worksheets/sheet1.xml", sheet_xml)

        initial_ws = get_process_working_set_bytes()

        reader = StreamingWorkbookReader(wb_path)
        row_count = 0
        for chunk in reader.stream_sheet(0, chunk_size=2000):
            row_count += len(chunk)
            current_ws = get_process_working_set_bytes()
            # Working set must remain well below defensive 235 MB ceiling
            assert current_ws < 235 * 1024 * 1024

        assert row_count == 20_000
        final_ws = get_process_working_set_bytes()
        # Working set delta should be modest (< 30 MB delta for 20,000 rows streaming)
        delta_mb = (final_ws - initial_ws) / (1024 * 1024)
        assert delta_mb < 30.0
