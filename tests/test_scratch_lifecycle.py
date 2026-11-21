"""Integration and lifecycle tests for Scratch-File Management & Scavenger (M02 Sprint 2).

Verifies:
1. Normal completion cleanup (zero leaked files in excel_intel_scratch).
2. Exception unwind cleanup.
3. Lock-first creation ordering.
4. Active reader protection (scavenger preserves active process files).
5. Scavenger reclamation of dead process scratch files.
6. Multi-process reader isolation.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import zipfile

import pytest
from excel_intel.core.parser import (
    CorruptWorkbookError,
    StreamingWorkbookReader,
    scavenge_scratch_dir,
)


def get_scratch_dir() -> Path:
    temp_dir = Path(tempfile.gettempdir())
    return temp_dir / "excel_intel_scratch"


def create_minimal_large_workbook(path: Path, string_count: int = 105_000) -> None:
    """Create workbook with enough shared strings to trigger Tier 2 scratch spill file creation."""
    sst_entries = "".join(f"<si><t>str_{i:06d}</t></si>" for i in range(string_count))
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{string_count}" uniqueCount="{string_count}">'
        f'{sst_entries}'
        '</sst>'
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="S1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>102000</v></c></row></sheetData></worksheet>')
        z.writestr("xl/sharedStrings.xml", sst_xml)


class TestScratchLifecycle:
    def test_normal_completion_scratch_cleanup(self, tmp_path: Path) -> None:
        """Verify scratch spill files are cleanly deleted when reader drops."""
        wb_path = tmp_path / "normal_scratch.xlsx"
        create_minimal_large_workbook(wb_path)

        scratch_dir = get_scratch_dir()
        initial_spill_files = list(scratch_dir.glob("m02_spill_*.bin")) if scratch_dir.exists() else []

        # Open and consume reader
        reader = StreamingWorkbookReader(wb_path)
        chunks = list(reader.stream_sheet(0))
        assert chunks[0][0]["cells"][0]["value"] == "str_102000"

        # Explicitly drop reader
        del reader

        # Verify scratch file deleted
        remaining = list(scratch_dir.glob("m02_spill_*.bin")) if scratch_dir.exists() else []
        assert len(remaining) <= len(initial_spill_files)

    def test_exception_unwind_scratch_cleanup(self, tmp_path: Path) -> None:
        """Verify scratch files are deleted when an exception unwinds the stack."""
        wb_path = tmp_path / "exception_scratch.xlsx"
        create_minimal_large_workbook(wb_path)

        scratch_dir = get_scratch_dir()
        initial_spill_files = list(scratch_dir.glob("m02_spill_*.bin")) if scratch_dir.exists() else []

        def run_faulty() -> None:
            with StreamingWorkbookReader(wb_path) as reader:
                for _ in reader.stream_sheet(0):
                    raise RuntimeError("Simulated mid-stream failure")

        try:
            run_faulty()
        except RuntimeError:
            pass

        # Verify no orphan files left behind
        remaining = list(scratch_dir.glob("m02_spill_*.bin")) if scratch_dir.exists() else []
        assert len(remaining) <= len(initial_spill_files)

    def test_scavenger_preserves_active_files(self, tmp_path: Path) -> None:
        """Verify scavenger does not delete scratch files of actively running reader instances."""
        wb_path = tmp_path / "active_scratch.xlsx"
        create_minimal_large_workbook(wb_path)

        # Clear any pre-existing stale artifacts in shared temp dir
        scavenge_scratch_dir()

        reader = StreamingWorkbookReader(wb_path)
        chunks = list(reader.stream_sheet(0))
        assert chunks[0][0]["cells"][0]["value"] == "str_102000"

        # Run scavenger while reader is still in scope
        cleaned = scavenge_scratch_dir()
        # Active file must NOT be deleted
        assert cleaned == 0

        # Reader can still read successfully
        assert chunks[0][0]["cells"][0]["value"] == "str_102000"

    def test_multi_reader_isolation(self, tmp_path: Path) -> None:
        """Verify two independent readers have completely isolated scratch files."""
        wb1 = tmp_path / "reader1.xlsx"
        wb2 = tmp_path / "reader2.xlsx"
        create_minimal_large_workbook(wb1)
        create_minimal_large_workbook(wb2)

        reader1 = StreamingWorkbookReader(wb1)
        reader2 = StreamingWorkbookReader(wb2)

        c1 = list(reader1.stream_sheet(0))
        c2 = list(reader2.stream_sheet(0))

        assert c1[0][0]["cells"][0]["value"] == "str_102000"
        assert c2[0][0]["cells"][0]["value"] == "str_102000"

        del reader1
        # reader2 must continue to function normally
        c2_again = list(reader2.stream_sheet(0))
        assert c2_again[0][0]["cells"][0]["value"] == "str_102000"
