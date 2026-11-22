"""Rigorous Multi-Workbook Concurrency & State Isolation Validation for M03.

Directly addresses and closes the concurrency gap from Prompt 3:
1. Executes concurrent inspections across multiple distinct, independent workbooks.
2. Validates zero cross-contamination between workbook results.
3. Proves bit-for-bit deterministic output equality between concurrent and single-threaded baseline runs.
4. Validates state isolation under thread contention.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import zipfile

import pytest
from excel_intel.inspection import (
    LayoutClassification,
    WorkbookInspectionReport,
    WorkbookInspector,
)


def create_test_workbook(
    tmp_path: Path,
    filename: str,
    sheet_specs: list[tuple[str, str, int, int]],
) -> Path:
    """Create synthetic workbook with specified sheets: (sheet_name, type, rows, cols)."""
    wb_path = tmp_path / filename

    sheet_entries = []
    types_overrides = []
    rels_entries = []

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for idx, (name, layout_type, num_rows, num_cols) in enumerate(sheet_specs, start=1):
            sheet_filename = f"sheet{idx}.xml"
            sheet_part = f"/xl/worksheets/{sheet_filename}"

            rows_xml = []
            if layout_type == "table":
                # Header row
                cols_hdr = "".join(
                    f'<c r="{chr(65+c)}1" t="inlineStr"><is><t>Col_{c}</t></is></c>'
                    for c in range(num_cols)
                )
                rows_xml.append(f'<row r="1">{cols_hdr}</row>')
                # Data rows
                for r in range(2, num_rows + 1):
                    cols_data = "".join(
                        f'<c r="{chr(65+c)}{r}"><v>{r * 10 + c}</v></c>'
                        for c in range(num_cols)
                    )
                    rows_xml.append(f'<row r="{r}">{cols_data}</row>')
            elif layout_type == "empty":
                pass
            elif layout_type == "key_value":
                for r in range(1, num_rows + 1):
                    row_xml = (
                        f'<row r="{r}">'
                        f'<c r="A{r}" t="inlineStr"><is><t>Key_{r}_{filename}</t></is></c>'
                        f'<c r="B{r}"><v>{r * 100}</v></c>'
                        f"</row>"
                    )
                    rows_xml.append(row_xml)

            sheet_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<dimension ref="A1:{chr(64+max(1, num_cols))}{max(1, num_rows)}"/>'
                f"<sheetData>{''.join(rows_xml)}</sheetData>"
                "</worksheet>"
            )
            z.writestr(f"xl/worksheets/{sheet_filename}", sheet_xml)

            sheet_entries.append(f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>')
            types_overrides.append(
                f'<Override PartName="{sheet_part}" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            )
            rels_entries.append(
                f'<Relationship Id="rId{idx}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                f'Target="worksheets/{sheet_filename}"/>'
            )

        # Package parts
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            + "".join(types_overrides)
            + "</Types>",
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
            '<calcPr calcMode="auto"/>'
            f"<sheets>{''.join(sheet_entries)}</sheets>"
            f'<definedNames><definedName name="FileMarker_{filename[:4]}">"{filename}"</definedName></definedNames>'
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels_entries)
            + "</Relationships>",
        )

    return wb_path


def test_concurrent_multi_workbook_isolation(tmp_path: Path) -> None:
    """Verify concurrent inspection of distinct workbooks with zero cross-contamination."""
    # Create 3 distinct workbooks with completely different structures and sheet names
    wb_a = create_test_workbook(
        tmp_path,
        "WB_ALPHA.xlsx",
        [("AlphaSheet1", "table", 20, 5), ("AlphaSheet2", "empty", 1, 1)],
    )
    wb_b = create_test_workbook(
        tmp_path,
        "WB_BETA.xlsx",
        [("BetaConfig", "key_value", 8, 2), ("BetaData", "table", 15, 3), ("BetaArchive", "empty", 1, 1)],
    )
    wb_c = create_test_workbook(
        tmp_path,
        "WB_GAMMA.xlsx",
        [("GammaPrimary", "table", 30, 4)],
    )

    workbooks = [wb_a, wb_b, wb_c]

    # Baseline single-threaded reports
    baselines: dict[str, dict] = {}
    for wb in workbooks:
        rep = WorkbookInspector.inspect(wb)
        baselines[wb.name] = rep.model_dump(exclude={"inspection_timestamp"})

    # Execute concurrent inspections across a pool of 6 worker threads
    # Each workbook is inspected 4 times concurrently (12 total concurrent executions)
    tasks = []
    for wb in workbooks:
        for run_id in range(4):
            tasks.append((wb, run_id))

    def inspect_worker(wb_path: Path, task_id: int) -> tuple[str, int, dict]:
        report = WorkbookInspector.inspect(wb_path)
        dump = report.model_dump(exclude={"inspection_timestamp"})
        return wb_path.name, task_id, dump

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(inspect_worker, wb, tid) for wb, tid in tasks]
        results = [f.result() for f in as_completed(futures)]

    # Verification: Zero cross-contamination and 100% deterministic equality
    for wb_name, task_id, result_dump in results:
        expected_dump = baselines[wb_name]
        # 1. Output must be identical to single-threaded baseline
        assert result_dump == expected_dump, (
            f"Concurrent result for {wb_name} task {task_id} drifted from baseline!"
        )

        # 2. Strict isolation checks: ensure no cross-contamination of sheet names
        sheet_names = [s["sheet_name"] for s in result_dump["sheets"]]
        if wb_name == "WB_ALPHA.xlsx":
            assert sheet_names == ["AlphaSheet1", "AlphaSheet2"]
            assert "BetaConfig" not in sheet_names
            assert "GammaPrimary" not in sheet_names
            assert result_dump["defined_names"][0]["name"] == "FileMarker_WB_A"
        elif wb_name == "WB_BETA.xlsx":
            assert sheet_names == ["BetaConfig", "BetaData", "BetaArchive"]
            assert "AlphaSheet1" not in sheet_names
            assert "GammaPrimary" not in sheet_names
            assert result_dump["defined_names"][0]["name"] == "FileMarker_WB_B"
        elif wb_name == "WB_GAMMA.xlsx":
            assert sheet_names == ["GammaPrimary"]
            assert "AlphaSheet1" not in sheet_names
            assert "BetaConfig" not in sheet_names
            assert result_dump["defined_names"][0]["name"] == "FileMarker_WB_G"


def test_concurrent_same_workbook_thread_safety(tmp_path: Path) -> None:
    """Verify bit-for-bit report equality when 8 threads inspect the same workbook simultaneously."""
    wb_path = create_test_workbook(
        tmp_path,
        "WB_SHARED.xlsx",
        [("Data1", "table", 25, 4), ("Config", "key_value", 5, 2)],
    )

    baseline = WorkbookInspector.inspect(wb_path).model_dump(exclude={"inspection_timestamp"})

    def worker(worker_id: int) -> dict:
        rep = WorkbookInspector.inspect(wb_path)
        return rep.model_dump(exclude={"inspection_timestamp"})

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(16)]
        results = [f.result() for f in as_completed(futures)]

    for idx, dump in enumerate(results):
        assert dump == baseline, f"Worker {idx} produced inconsistent report under concurrency!"
