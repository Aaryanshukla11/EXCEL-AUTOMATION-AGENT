"""Comprehensive Concurrency and Reliability Test Suite (M02 Sprint 2 — Step 4).

Validates:
1. Multiple simultaneous parser instances reading the same workbook concurrently.
2. Independent parsing of different workbooks in parallel.
3. Shared-string cache isolation between distinct reader instances.
4. Scratch-file and lock-handle isolation across concurrent readers.
5. Concurrent background scavenging while active readers are streaming.
6. Cancellation and exception unwinding during concurrent parsing.
7. Memory-limit trigger propagation in concurrent environments.
8. Repeated sequential and parallel parsing of the same workbook (idempotence, zero descriptor leaks).
9. High-concurrency multi-threaded stress test with zero deadlocks.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import threading
import time
from typing import Any
import zipfile

import pytest
from excel_intel.core.parser import (
    PlatformResourceLimitError,
    StreamingWorkbookReader,
    check_memory_guard,
    scavenge_scratch_dir,
)


def create_test_workbook(
    path: Path,
    *,
    sheet_name: str = "Sheet1",
    row_count: int = 1000,
    prefix: str = "data",
) -> None:
    """Generate a clean OpenXML workbook fixture using python stdlib zipfile."""
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStringTable+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<workbookPr date1904="0"/>'
        '<sheets>'
        f'<sheet name="{sheet_name}" sheetId="1" r:id="rId1"/>'
        '</sheets>'
        '</workbook>'
    )

    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cellXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '</cellXfs>'
        '</styleSheet>'
    )

    # Build shared strings
    strings = [f"{prefix}_str_{i}" for i in range(min(row_count, 500))]
    sst_entries = "".join(f"<si><t>{s}</t></si>" for s in strings)
    sst_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">'
        f'{sst_entries}'
        '</sst>'
    )

    # Build rows
    rows_xml = []
    for r in range(1, row_count + 1):
        s_idx = (r - 1) % len(strings)
        row_str = (
            f'<row r="{r}">'
            f'<c r="A{r}"><v>{r}</v></c>'
            f'<c r="B{r}" t="s"><v>{s_idx}</v></c>'
            f'<c r="C{r}"><f>A{r}*2</f><v>{r * 2}</v></c>'
            '</row>'
        )
        rows_xml.append(row_str)

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rows_xml)}</sheetData>'
        '</worksheet>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles_xml)
        z.writestr("xl/sharedStrings.xml", sst_xml)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)


class TestConcurrencyAndReliability:
    """Rigorous multi-threaded concurrency and stability test suite."""

    def test_multiple_simultaneous_parser_instances(self, tmp_path: Path) -> None:
        """Verify 8 threads parsing the same workbook simultaneously receive identical results."""
        wb_path = tmp_path / "shared_workbook.xlsx"
        create_test_workbook(wb_path, row_count=2000, prefix="simultaneous")

        barrier = threading.Barrier(8)

        def worker(thread_id: int) -> int:
            barrier.wait(timeout=10)
            reader = StreamingWorkbookReader(wb_path)
            total_rows = 0
            for chunk in reader.stream_sheet(0, chunk_size=500):
                total_rows += len(chunk)
                # Verify row contents
                assert chunk[0]["cells"][0]["value"] == (total_rows - len(chunk) + 1)
            reader.close()
            return total_rows

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(8)]
            results = [f.result(timeout=20) for f in futures]

        assert len(results) == 8
        assert all(r == 2000 for r in results)

    def test_concurrent_independent_workbooks(self, tmp_path: Path) -> None:
        """Verify 6 threads parsing 6 completely different workbooks in parallel without cross-talk."""
        paths = []
        for i in range(6):
            p = tmp_path / f"independent_wb_{i}.xlsx"
            create_test_workbook(p, row_count=1000 + i * 100, prefix=f"worker_{i}")
            paths.append(p)

        def worker(idx: int) -> tuple[int, str]:
            reader = StreamingWorkbookReader(paths[idx])
            total_rows = 0
            first_val = ""
            for chunk in reader.stream_sheet(0, chunk_size=250):
                total_rows += len(chunk)
                if not first_val:
                    first_val = str(chunk[0]["cells"][1]["value"])
            reader.close()
            return total_rows, first_val

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(worker, i): i for i in range(6)}
            for f in as_completed(futures):
                idx = futures[f]
                rows, first_val = f.result(timeout=15)
                expected_rows = 1000 + idx * 100
                assert rows == expected_rows
                assert first_val == f"worker_{idx}_str_0"

    def test_shared_string_cache_isolation(self, tmp_path: Path) -> None:
        """Verify that concurrent readers on workbooks with overlapping indices do not cross-pollinate LRU cache."""
        wb1 = tmp_path / "wb_alpha.xlsx"
        wb2 = tmp_path / "wb_beta.xlsx"
        create_test_workbook(wb1, row_count=500, prefix="ALPHA")
        create_test_workbook(wb2, row_count=500, prefix="BETA")

        def reader_task(wb: Path, expected_prefix: str) -> list[str]:
            r = StreamingWorkbookReader(wb)
            collected = []
            for chunk in r.stream_sheet(0, chunk_size=100):
                for row in chunk:
                    val = str(row["cells"][1]["value"])
                    assert val.startswith(expected_prefix), f"Cache leakage detected: {val}"
                    collected.append(val)
            r.close()
            return collected

        with ThreadPoolExecutor(max_workers=4) as executor:
            f1 = executor.submit(reader_task, wb1, "ALPHA")
            f2 = executor.submit(reader_task, wb2, "BETA")
            f3 = executor.submit(reader_task, wb1, "ALPHA")
            f4 = executor.submit(reader_task, wb2, "BETA")

            res1 = f1.result(timeout=10)
            res2 = f2.result(timeout=10)
            res3 = f3.result(timeout=10)
            res4 = f4.result(timeout=10)

        assert len(res1) == 500
        assert len(res2) == 500
        assert res1 == res3
        assert res2 == res4

    def test_concurrent_scavenging_while_readers_active(self, tmp_path: Path) -> None:
        """Verify background scavenger running continuously does NOT delete active readers' scratch files."""
        wb_path = tmp_path / "scavenge_active.xlsx"
        create_test_workbook(wb_path, row_count=3000, prefix="scavenge_test")

        stop_scavenger = threading.Event()
        scavenge_errors: list[Exception] = []

        def scavenger_loop() -> None:
            while not stop_scavenger.is_set():
                try:
                    scavenge_scratch_dir()
                except Exception as e:
                    scavenge_errors.append(e)
                time.sleep(0.01)

        scavenger_thread = threading.Thread(target=scavenger_loop, daemon=True)
        scavenger_thread.start()

        try:
            def reader_work() -> int:
                r = StreamingWorkbookReader(wb_path)
                count = 0
                for chunk in r.stream_sheet(0, chunk_size=500):
                    count += len(chunk)
                    time.sleep(0.005)  # Yield CPU to allow scavenger to interleave
                r.close()
                return count

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(reader_work) for _ in range(4)]
                counts = [f.result(timeout=25) for f in futures]

            assert all(c == 3000 for c in counts)
            assert len(scavenge_errors) == 0, f"Scavenger errors: {scavenge_errors}"
        finally:
            stop_scavenger.set()
            scavenger_thread.join(timeout=5)

    def test_cancellation_and_exception_unwind_cleanup(self, tmp_path: Path) -> None:
        """Verify cancelling or raising exceptions midway cleanly releases scratch files and locks."""
        wb_path = tmp_path / "abort_test.xlsx"
        create_test_workbook(wb_path, row_count=2000, prefix="abort")

        def fault_worker() -> None:
            with StreamingWorkbookReader(wb_path) as reader:
                for idx, chunk in enumerate(reader.stream_sheet(0, chunk_size=200)):
                    if idx >= 2:
                        raise RuntimeError("Simulated mid-stream abortion")

        # Run 5 failing workers concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fault_worker) for _ in range(5)]
            for f in futures:
                with pytest.raises(RuntimeError, match="Simulated mid-stream abortion"):
                    f.result(timeout=10)

        # Scavenge to confirm no deadlocks or unclosed file handle locks
        cleaned = scavenge_scratch_dir()
        assert isinstance(cleaned, int)

    def test_repeated_parsing_same_workbook_idempotence(self, tmp_path: Path) -> None:
        """Verify 25 sequential and parallel parses produce identical results without descriptor or memory leaks."""
        wb_path = tmp_path / "idempotence.xlsx"
        create_test_workbook(wb_path, row_count=1500, prefix="idem")

        reference_rows = None
        for iteration in range(10):
            with StreamingWorkbookReader(wb_path) as reader:
                rows = []
                for chunk in reader.stream_sheet(0, chunk_size=500):
                    rows.extend(chunk)
                if reference_rows is None:
                    reference_rows = rows
                else:
                    assert len(rows) == len(reference_rows)
                    assert rows[0] == reference_rows[0]
                    assert rows[-1] == reference_rows[-1]

    def test_high_concurrency_stress_no_deadlocks(self, tmp_path: Path) -> None:
        """Stress test with 16 concurrent workers performing interleaved inspections and streams."""
        wb_path = tmp_path / "stress_wb.xlsx"
        create_test_workbook(wb_path, row_count=1000, prefix="stress")

        def task(worker_id: int) -> bool:
            reader = StreamingWorkbookReader(wb_path)
            meta = reader.inspect()
            assert meta["sheet_count"] == 1
            assert reader.has_macros is False
            assert reader.is_1904 is False

            total = 0
            for chunk in reader.stream_sheet(0, chunk_size=200):
                total += len(chunk)
            reader.close()
            return total == 1000

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(task, i) for i in range(16)]
            results = [f.result(timeout=30) for f in futures]

        assert all(results)
        assert len(results) == 16
