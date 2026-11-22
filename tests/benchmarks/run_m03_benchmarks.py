"""Controlled Empirical Benchmark Suite for Milestone M03 (Prompt 4 Addendum).

Evaluates:
1. Repeated Measurements (N=3 repetitions per workload) for:
   - Dense 100K x 4
   - Wide 10K x 50
   - Sparse 100K-Row
   - Multi-Sheet (5 Sheets)
2. Controlled O(C) Row-Scaling Experiments (Fixed C=4, Increasing R):
   - 10,000 x 4
   - 50,000 x 4
   - 100,000 x 4
3. Controlled Column-Scaling Experiments (Fixed R=10,000, Increasing C):
   - 10,000 x 4
   - 10,000 x 20
   - 10,000 x 50
4. Continuous Background Sampling Methodology:
   - Polling thread samples process WorkingSetSize every 5 ms during execution.
   - Captures transient spikes and compares against OS PeakWorkingSetSize.
   - Full process scope (Python runtime + PyO3 native Rust extension).
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
import zipfile
import psutil

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from excel_intel.inspection import WorkbookInspector, col_index_to_letter


class MemorySampler:
    """High-frequency background memory sampler polling process RSS every 5ms."""

    def __init__(self, interval_sec: float = 0.005) -> None:
        self.interval = interval_sec
        self.proc = psutil.Process(os.getpid())
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.samples: list[float] = []

    def _sample_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                rss = self.proc.memory_info().rss / (1024.0 * 1024.0)
                self.samples.append(rss)
            except Exception:
                pass
            time.sleep(self.interval)

    def start(self) -> None:
        self.samples.clear()
        self._stop_event.clear()
        # Record initial reading
        self.samples.append(self.proc.memory_info().rss / (1024.0 * 1024.0))
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self) -> float:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        # Record final reading
        try:
            self.samples.append(self.proc.memory_info().rss / (1024.0 * 1024.0))
        except Exception:
            pass
        return max(self.samples) if self.samples else 0.0


def create_sheet_xml(num_rows: int, num_cols: int, *, is_sparse: bool = False, step: int = 500) -> str:
    """Generate raw sheet XML for a given dimension and layout."""
    rows_xml = []

    if is_sparse:
        for r in range(1, num_rows + 1, step):
            col_idx = ((r // step) % num_cols) + 1
            col_letter = col_index_to_letter(col_idx)
            rows_xml.append(f'<row r="{r}"><c r="{col_letter}{r}"><v>{r}</v></c></row>')
    else:
        # Header row
        hdr_cells = "".join(
            f'<c r="{col_index_to_letter(c)}1" t="inlineStr"><is><t>Col_{c}</t></is></c>'
            for c in range(1, num_cols + 1)
        )
        rows_xml.append(f'<row r="1">{hdr_cells}</row>')

        # Data rows
        for r in range(2, num_rows + 1):
            cells = []
            for c in range(1, num_cols + 1):
                col_letter = col_index_to_letter(c)
                if c == 1:
                    cells.append(f'<c r="{col_letter}{r}"><v>{r}</v></c>')
                elif c == 2:
                    cells.append(f'<c r="{col_letter}{r}"><v>{r * 1.5:.2f}</v></c>')
                elif c == 3:
                    cells.append(f'<c r="{col_letter}{r}" t="inlineStr"><is><t>Text_{r}</t></is></c>')
                elif c % 5 == 0:
                    cells.append(f'<c r="{col_letter}{r}"><f>A{r}*2</f><v>{r * 2}</v></c>')
                else:
                    cells.append(f'<c r="{col_letter}{r}"><v>{r * 10 + c}</v></c>')
            rows_xml.append(f'<row r="{r}">{"".join(cells)}</row>')

    max_col_letter = col_index_to_letter(num_cols)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="A1:{max_col_letter}{num_rows}"/>'
        f"<sheetData>{''.join(rows_xml)}</sheetData>"
        "</worksheet>"
    )


def build_single_sheet_package(tmp_path: Path, filename: str, sheet_xml: str) -> Path:
    wb_path = tmp_path / filename

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
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
            '<calcPr calcMode="auto"/>'
            "<sheets><sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\"/></sheets>"
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


def build_multi_sheet_package(tmp_path: Path, filename: str) -> Path:
    wb_path = tmp_path / filename

    sheets_config = [
        ("Transactions", 10000, 10, False, 1),
        ("ReferenceData", 5000, 4, False, 1),
        ("SparseLookup", 20000, 26, True, 200),
        ("SummaryMetrics", 1000, 5, False, 1),
        ("EmptyArchive", 1, 1, True, 10),
    ]

    sheet_entries = []
    types_overrides = []
    rels_entries = []
    sheets_xml_map = {}

    for idx, (name, rows, cols, is_sparse, step) in enumerate(sheets_config, start=1):
        s_xml = create_sheet_xml(rows, cols, is_sparse=is_sparse, step=step)
        sheet_part = f"/xl/worksheets/sheet{idx}.xml"
        sheets_xml_map[f"xl/worksheets/sheet{idx}.xml"] = s_xml
        sheet_entries.append(f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>')
        types_overrides.append(f'<Override PartName="{sheet_part}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        rels_entries.append(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>')

    with zipfile.ZipFile(wb_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
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
            "</workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels_entries)
            + "</Relationships>",
        )
        for path, s_xml in sheets_xml_map.items():
            z.writestr(path, s_xml)

    return wb_path


def run_single_benchmark(
    wb_path: Path,
    label: str,
    reps: int = 3,
) -> dict[str, Any]:
    """Execute N independent repetitions with 5ms background memory sampling."""
    proc = psutil.Process(os.getpid())
    sampler = MemorySampler(interval_sec=0.005)

    with open(wb_path, "rb") as f:
        sha_initial = hashlib.sha256(f.read()).hexdigest()

    runs_data = []

    for rep_i in range(1, reps + 1):
        gc.collect()
        base_rss = proc.memory_info().rss / (1024.0 * 1024.0)

        sampler.start()
        t0 = time.perf_counter()
        report = WorkbookInspector.inspect(wb_path)
        t1 = time.perf_counter()
        peak_sampled_rss = sampler.stop()

        lat = t1 - t0
        delta_rss = max(0.0, peak_sampled_rss - base_rss)
        cells = sum(s.actual_cell_count or 0 for s in report.sheets)
        tp = cells / max(1e-6, lat)

        runs_data.append({
            "repetition": rep_i,
            "latency_s": lat,
            "throughput_cells_sec": tp,
            "base_rss_mb": base_rss,
            "peak_rss_mb": peak_sampled_rss,
            "delta_rss_mb": delta_rss,
            "cells": cells,
        })

    with open(wb_path, "rb") as f:
        sha_final = hashlib.sha256(f.read()).hexdigest()

    assert sha_initial == sha_final, f"File mutation detected on {wb_path.name}!"

    latencies = [r["latency_s"] for r in runs_data]
    peaks = [r["peak_rss_mb"] for r in runs_data]
    deltas = [r["delta_rss_mb"] for r in runs_data]
    throughputs = [r["throughput_cells_sec"] for r in runs_data]

    summary = {
        "label": label,
        "runs": runs_data,
        "cells": runs_data[0]["cells"],
        "latency_stats": {
            "min": min(latencies),
            "median": statistics.median(latencies),
            "max": max(latencies),
            "mean": statistics.mean(latencies),
        },
        "peak_rss_stats": {
            "min": min(peaks),
            "median": statistics.median(peaks),
            "max": max(peaks),
        },
        "delta_rss_stats": {
            "min": min(deltas),
            "median": statistics.median(deltas),
            "max": max(deltas),
        },
        "throughput_stats": {
            "median": statistics.median(throughputs),
        },
        "sha_verified": True,
    }

    return summary


def run_full_suite() -> dict[str, Any]:
    suite_results = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        print("\n" + "=" * 90)
        print("M03 PROMPT 4: CONTROLLED BENCHMARKS WITH 5ms PEAK RSS SAMPLING & N=3 REPETITIONS")
        print("=" * 90)

        # ---------------------------------------------------------------------
        # 1. Four Core Contractual Workloads (N=3)
        # ---------------------------------------------------------------------
        print("\n--- SECTION 1: CORE WORKLOAD REPEATED MEASUREMENTS (N=3) ---")
        print(f"{'Workload Target':<26} {'Rep':<5} {'Latency':<10} {'Throughput':<12} {'Base RSS':<10} {'Peak RSS':<10} {'Delta RSS':<10}")
        print("-" * 85)

        # 1.1 Dense 100K x 4
        s1 = create_sheet_xml(100000, 4, is_sparse=False)
        wb1 = build_single_sheet_package(tmp_path, "dense_100k_4.xlsx", s1)
        res_dense_100k = run_single_benchmark(wb1, "Dense 100K x 4", reps=3)
        for r in res_dense_100k["runs"]:
            print(f"{'Dense 100K x 4':<26} #{r['repetition']:<4} {r['latency_s']:6.3f}s    {r['throughput_cells_sec']:8.0f} c/s {r['base_rss_mb']:6.1f} MB  {r['peak_rss_mb']:6.1f} MB  {r['delta_rss_mb']:6.1f} MB")

        # 1.2 Wide 10K x 50
        s2 = create_sheet_xml(10000, 50, is_sparse=False)
        wb2 = build_single_sheet_package(tmp_path, "wide_10k_50.xlsx", s2)
        res_wide_10k = run_single_benchmark(wb2, "Wide 10K x 50", reps=3)
        for r in res_wide_10k["runs"]:
            print(f"{'Wide 10K x 50':<26} #{r['repetition']:<4} {r['latency_s']:6.3f}s    {r['throughput_cells_sec']:8.0f} c/s {r['base_rss_mb']:6.1f} MB  {r['peak_rss_mb']:6.1f} MB  {r['delta_rss_mb']:6.1f} MB")

        # 1.3 Sparse 100K-Row
        s3 = create_sheet_xml(100000, 26, is_sparse=True, step=1000)
        wb3 = build_single_sheet_package(tmp_path, "sparse_100k.xlsx", s3)
        res_sparse_100k = run_single_benchmark(wb3, "Sparse 100K-Row", reps=3)
        for r in res_sparse_100k["runs"]:
            print(f"{'Sparse 100K-Row':<26} #{r['repetition']:<4} {r['latency_s']:6.3f}s    {r['throughput_cells_sec']:8.0f} c/s {r['base_rss_mb']:6.1f} MB  {r['peak_rss_mb']:6.1f} MB  {r['delta_rss_mb']:6.1f} MB")

        # 1.4 Multi-Sheet (5 Sheets)
        wb4 = build_multi_sheet_package(tmp_path, "multi_sheet_5.xlsx")
        res_multi_5 = run_single_benchmark(wb4, "Multi-Sheet (5 Sheets)", reps=3)
        for r in res_multi_5["runs"]:
            print(f"{'Multi-Sheet (5 Sheets)':<26} #{r['repetition']:<4} {r['latency_s']:6.3f}s    {r['throughput_cells_sec']:8.0f} c/s {r['base_rss_mb']:6.1f} MB  {r['peak_rss_mb']:6.1f} MB  {r['delta_rss_mb']:6.1f} MB")

        suite_results["core_workloads"] = {
            "dense_100k_4": res_dense_100k,
            "wide_10k_50": res_wide_10k,
            "sparse_100k": res_sparse_100k,
            "multi_sheet_5": res_multi_5,
        }

        # ---------------------------------------------------------------------
        # 2. Controlled Row-Scaling Experiments (Fixed C=4, Increasing Rows)
        # ---------------------------------------------------------------------
        print("\n--- SECTION 2: CONTROLLED ROW-SCALING (FIXED C=4, INCREASING ROWS) ---")
        print(f"{'Dimensions (R x C)':<26} {'Cells':<10} {'Median Lat':<12} {'Median Peak':<12} {'Median Delta':<12}")
        print("-" * 75)

        row_scales = [10000, 50000, 100000]
        row_results = []
        for r_count in row_scales:
            s_xml = create_sheet_xml(r_count, 4, is_sparse=False)
            wb_r = build_single_sheet_package(tmp_path, f"ctrl_r_{r_count}_c_4.xlsx", s_xml)
            res_r = run_single_benchmark(wb_r, f"{r_count:,} x 4", reps=3)
            row_results.append(res_r)
            med_lat = res_r["latency_stats"]["median"]
            med_peak = res_r["peak_rss_stats"]["median"]
            med_delta = res_r["delta_rss_stats"]["median"]
            print(f"{f'{r_count:,} x 4':<26} {res_r['cells']:<10} {med_lat:6.3f}s       {med_peak:6.1f} MB     {med_delta:6.1f} MB")

        suite_results["controlled_row_scaling"] = row_results

        # ---------------------------------------------------------------------
        # 3. Controlled Column-Scaling Experiments (Fixed R=10,000, Increasing Cols)
        # ---------------------------------------------------------------------
        print("\n--- SECTION 3: CONTROLLED COLUMN-SCALING (FIXED R=10,000, INCREASING COLS) ---")
        print(f"{'Dimensions (R x C)':<26} {'Cells':<10} {'Median Lat':<12} {'Median Peak':<12} {'Median Delta':<12}")
        print("-" * 75)

        col_scales = [4, 20, 50]
        col_results = []
        for c_count in col_scales:
            s_xml = create_sheet_xml(10000, c_count, is_sparse=False)
            wb_c = build_single_sheet_package(tmp_path, f"ctrl_r_10000_c_{c_count}.xlsx", s_xml)
            res_c = run_single_benchmark(wb_c, f"10,000 x {c_count}", reps=3)
            col_results.append(res_c)
            med_lat = res_c["latency_stats"]["median"]
            med_peak = res_c["peak_rss_stats"]["median"]
            med_delta = res_c["delta_rss_stats"]["median"]
            print(f"{f'10,000 x {c_count}':<26} {res_c['cells']:<10} {med_lat:6.3f}s       {med_peak:6.1f} MB     {med_delta:6.1f} MB")

        suite_results["controlled_column_scaling"] = col_results
        print("=" * 90 + "\n")

    return suite_results


if __name__ == "__main__":
    benchmark_output = run_full_suite()
    with open("m03_controlled_benchmark_results.json", "w") as f:
        json.dump(benchmark_output, f, indent=2)
    print("Benchmark complete. Data saved to m03_controlled_benchmark_results.json\n")
