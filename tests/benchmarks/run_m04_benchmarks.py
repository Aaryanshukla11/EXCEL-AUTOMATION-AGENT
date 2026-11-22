"""Controlled Memory and Performance Benchmarks for M04 Spatial GridSegmenter.

Executes isolated subprocess runs to accurately measure:
- Baseline RSS (process launch & imports)
- Absolute Peak RSS (during/after streaming segmentation)
- Incremental RSS delta (Peak - Baseline)
Across 10k, 50k, and 100k rows in both dense and sparse configurations.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from typing import Any, Iterator

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import psutil


def generate_rows(
    row_count: int,
    col_count: int,
    is_sparse: bool,
) -> Iterator[dict[str, Any]]:
    """Generate streaming row records without materializing full list in memory."""
    if is_sparse:
        # Sparse: every 20th row has 10 columns, other rows have single cell or are blank
        for r in range(1, row_count + 1):
            if r % 20 == 0:
                yield {
                    "row": r,
                    "cells": [{"col": c, "value": f"val_{r}_{c}"} for c in range(1, col_count + 1)],
                }
            elif r % 50 == 1:
                # Isolated single stray cell
                yield {
                    "row": r,
                    "cells": [{"col": 1, "value": f"sparse_{r}"}],
                }
    else:
        # Dense: every row has all columns populated
        for r in range(1, row_count + 1):
            yield {
                "row": r,
                "cells": [{"col": c, "value": f"v_{r}_{c}"} for c in range(1, col_count + 1)],
            }


def run_single_benchmark_worker(
    row_count: int,
    col_count: int,
    is_sparse: bool,
    window_size: int,
) -> dict[str, Any]:
    """Worker executed in an isolated process to measure pure RSS without cross-run cache."""
    process = psutil.Process()
    gc.collect()

    baseline_rss = process.memory_info().rss

    from excel_intel.spatial.grid_segmenter import GridSegmenter

    post_import_rss = process.memory_info().rss
    segmenter = GridSegmenter(window_size=window_size)

    stream = generate_rows(row_count, col_count, is_sparse)

    start_time = time.perf_counter()
    report = segmenter.segment_rows(stream, sheet_name=f"Bench_{row_count}_{is_sparse}")
    elapsed_sec = time.perf_counter() - start_time

    peak_rss = process.memory_info().rss
    rss_delta = peak_rss - baseline_rss

    return {
        "row_count": row_count,
        "col_count": col_count,
        "is_sparse": is_sparse,
        "window_size": window_size,
        "elapsed_sec": round(elapsed_sec, 4),
        "baseline_rss_mb": round(baseline_rss / (1024 * 1024), 2),
        "post_import_rss_mb": round(post_import_rss / (1024 * 1024), 2),
        "peak_rss_mb": round(peak_rss / (1024 * 1024), 2),
        "rss_delta_mb": round(rss_delta / (1024 * 1024), 2),
        "regions_detected": len(report.regions),
        "sparse_islands_detected": len(report.sparse_islands),
        "total_cells_scanned": report.total_populated_cells_evaluated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M04 Controlled Memory Benchmarks")
    parser.add_argument("--worker", action="store_true", help="Run as worker subprocess")
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--cols", type=int, default=10)
    parser.add_argument("--sparse", action="store_true")
    parser.add_argument("--window", type=int, default=50)
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()

    if args.worker:
        result = run_single_benchmark_worker(args.rows, args.cols, args.sparse, args.window)
        print(json.dumps(result))
        return

    # Master orchestrator: runs each benchmark in an isolated subprocess
    workloads = [
        # (rows, cols, is_sparse)
        (10000, 10, False),
        (10000, 10, True),
        (50000, 10, False),
        (50000, 10, True),
        (100000, 10, False),
        (100000, 10, True),
    ]

    all_results = []
    import subprocess

    print("=" * 85)
    print("M04 SPATIAL SEGMENTATION CONTROLLED MEMORY BENCHMARKS (PROCESS-ISOLATED)")
    print("=" * 85)
    print(
        f"{'Workload':<20} | {'Type':<8} | {'Time (s)':<10} | {'Base RSS':<10} | {'Peak RSS':<10} | {'Delta RSS':<10} | {'Regions'}"
    )
    print("-" * 85)

    for rows, cols, is_sparse in workloads:
        cmd = [
            sys.executable,
            __file__,
            "--worker",
            "--rows",
            str(rows),
            "--cols",
            str(cols),
            "--window",
            "50",
        ]
        if is_sparse:
            cmd.append("--sparse")

        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        res = json.loads(p.stdout.strip())
        all_results.append(res)

        w_name = f"{rows:,} x {cols}"
        t_type = "Sparse" if is_sparse else "Dense"
        print(
            f"{w_name:<20} | {t_type:<8} | {res['elapsed_sec']:<10.3f} | "
            f"{res['baseline_rss_mb']:<7.2f} MB | {res['peak_rss_mb']:<7.2f} MB | "
            f"{res['rss_delta_mb']:<7.2f} MB | {res['regions_detected']} regs, {res['sparse_islands_detected']} isl"
        )

    print("=" * 85)

    out_file = args.json_out or "m04_benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"Benchmark results written to {out_file}")


if __name__ == "__main__":
    main()
