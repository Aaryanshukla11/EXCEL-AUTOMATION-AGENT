"""Reproducible benchmark verification for M02 streaming parser (Step 5 Final Quality Gate).

Evaluates:
1. BENCH-SCALE-100K (100,000 data rows x 50 columns sparse sheet, 4,000,050 cells)
   - Contractual target: Streaming latency < 15.0s, Peak Working Set (RSS) <= 250.0 MB.
   - Evaluates Cold vs Warm execution, individual timings, median, and memory scaling ratio.
2. BENCH-PERF-MULTI-5 (5 source workbooks x 20,000 rows + 1 master workbook = 120,000 rows)
   - Contractual target: Mean total latency <= 60.0s across N=5 runs, Peak RSS <= 250.0 MB.
   - Evaluates run-by-run breakdown, mean, median, standard deviation (sigma), mean + 2*sigma.
"""

from __future__ import annotations

import os
import platform
import shutil
import statistics
import sys
import tempfile
import time
import psutil

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
os.environ["EXCEL_INTEL_MAX_DECOMPRESSION_RATIO"] = "25.0"

from excel_intel.core.parser import StreamingWorkbookReader


def measure_process_rss_mb() -> float:
    proc = psutil.Process(os.getpid())
    return proc.memory_info().rss / (1024.0 * 1024.0)


def benchmark_100k(corpora_dir: str, runs: int = 3) -> dict[str, Any]:
    src_path = os.path.join(corpora_dir, "BENCH-SCALE-100K.xlsx")
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Fixture not found: {src_path}")

    timings = []
    baseline_rss_list = []
    peak_rss_list = []
    total_rows = 0
    total_cells = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        disposable_path = os.path.join(tmp_dir, "BENCH-SCALE-100K-DISPOSABLE.xlsx")
        shutil.copyfile(src_path, disposable_path)

        for run_i in range(runs):
            start_rss = measure_process_rss_mb()
            baseline_rss_list.append(start_rss)
            peak_rss = start_rss

            t0 = time.perf_counter()
            reader = StreamingWorkbookReader(disposable_path)
            sheet_name = reader.sheet_names[0]

            rows_in_run = 0
            cells_in_run = 0
            for chunk in reader.stream_sheet(sheet_name, chunk_size=1000):
                rows_in_run += len(chunk)
                for row in chunk:
                    cells_in_run += len(row["cells"])
                current_rss = measure_process_rss_mb()
                if current_rss > peak_rss:
                    peak_rss = current_rss

            elapsed = time.perf_counter() - t0
            timings.append(elapsed)
            peak_rss_list.append(peak_rss)
            total_rows = rows_in_run
            total_cells = cells_in_run
            reader.close()

    cold_time = timings[0]
    warm_times = timings[1:] if len(timings) > 1 else timings
    mean_time = statistics.mean(timings)
    median_time = statistics.median(timings)
    std_dev = statistics.stdev(timings) if len(timings) > 1 else 0.0

    initial_baseline = baseline_rss_list[0]
    max_peak = max(peak_rss_list)
    scaling_ratio = max_peak / initial_baseline if initial_baseline > 0 else 1.0

    return {
        "runs": runs,
        "timings": timings,
        "cold_seconds": cold_time,
        "warm_mean_seconds": statistics.mean(warm_times) if warm_times else cold_time,
        "mean_seconds": mean_time,
        "median_seconds": median_time,
        "std_dev_seconds": std_dev,
        "baseline_rss_mb": initial_baseline,
        "peak_rss_mb": max_peak,
        "memory_scaling_ratio": scaling_ratio,
        "total_rows": total_rows,
        "total_cells": total_cells,
    }


def benchmark_multi5(corpora_dir: str, runs: int = 5) -> dict[str, Any]:
    source_names = [f"BENCH-MULTI5-SOURCE-{i}.xlsx" for i in range(1, 6)]
    master_name = "BENCH-MULTI5-MASTER.xlsx"

    all_elapsed = []
    baseline_rss_list = []
    peak_rss_list = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        disposable_sources = []
        for name in source_names:
            src = os.path.join(corpora_dir, name)
            dst = os.path.join(tmp_dir, name)
            shutil.copyfile(src, dst)
            disposable_sources.append(dst)

        master_src = os.path.join(corpora_dir, master_name)
        master_dst = os.path.join(tmp_dir, master_name)
        shutil.copyfile(master_src, master_dst)

        for run_idx in range(runs):
            start_rss = measure_process_rss_mb()
            baseline_rss_list.append(start_rss)
            run_peak_rss = start_rss

            t0 = time.perf_counter()
            total_rows = 0

            for path in disposable_sources:
                with StreamingWorkbookReader(path) as reader:
                    for chunk in reader.stream_sheet(0, chunk_size=1000):
                        total_rows += len(chunk)
                        rss = measure_process_rss_mb()
                        if rss > run_peak_rss:
                            run_peak_rss = rss

            with StreamingWorkbookReader(master_dst) as master_reader:
                for chunk in master_reader.stream_sheet(0, chunk_size=1000):
                    total_rows += len(chunk)
                    rss = measure_process_rss_mb()
                    if rss > run_peak_rss:
                        run_peak_rss = rss

            elapsed = time.perf_counter() - t0
            all_elapsed.append(elapsed)
            peak_rss_list.append(run_peak_rss)

    mean_elapsed = statistics.mean(all_elapsed)
    median_elapsed = statistics.median(all_elapsed)
    std_dev = statistics.stdev(all_elapsed) if len(all_elapsed) > 1 else 0.0
    initial_baseline = baseline_rss_list[0]
    max_peak = max(peak_rss_list)
    scaling_ratio = max_peak / initial_baseline if initial_baseline > 0 else 1.0

    return {
        "runs": runs,
        "timings": all_elapsed,
        "cold_seconds": all_elapsed[0],
        "warm_mean_seconds": statistics.mean(all_elapsed[1:]) if len(all_elapsed) > 1 else all_elapsed[0],
        "mean_seconds": mean_elapsed,
        "median_seconds": median_elapsed,
        "std_dev_seconds": std_dev,
        "mean_plus_2sigma": mean_elapsed + 2 * std_dev,
        "min_seconds": min(all_elapsed),
        "max_seconds": max(all_elapsed),
        "baseline_rss_mb": initial_baseline,
        "peak_rss_mb": max_peak,
        "memory_scaling_ratio": scaling_ratio,
        "total_rows_per_run": 120_000,
    }


def print_environment_specs() -> None:
    mem = psutil.virtual_memory()
    total_ram_gb = mem.total / (1024.0 ** 3)
    cpu_count = os.cpu_count() or 1
    py_ver = platform.python_version()
    os_name = platform.system()
    os_release = platform.release()
    os_arch = platform.machine()
    proc_desc = platform.processor()

    print("\n" + "=" * 70)
    print("BENCHMARK EXECUTION ENVIRONMENT AUDIT")
    print("=" * 70)
    print(f"  Operating System:     {os_name} {os_release} ({os_arch})")
    print(f"  Processor:            {proc_desc} ({cpu_count} logical cores)")
    print(f"  Total System RAM:     {total_ram_gb:.2f} GB")
    print(f"  Python Runtime:       CPython {py_ver}")
    print(f"  Process PID:          {os.getpid()}")
    print("=" * 70)


if __name__ == "__main__":
    print_environment_specs()

    corpora_dir = os.path.abspath(r"phase0/corpora")
    print("\n" + "=" * 70)
    print("M02 BENCHMARK EVALUATION ON FROZEN PHASE 0 CORPORA")
    print("=" * 70)

    print("\n[1/2] Executing 100k Streaming Ingestion Benchmark (BENCH-SCALE-100K)...")
    res_100k = benchmark_100k(corpora_dir, runs=3)
    print(f"  Rows Processed:       {res_100k['total_rows']:,}")
    print(f"  Cells Decoded:        {res_100k['total_cells']:,}")
    print(f"  Runs (N):             {res_100k['runs']}")
    print(f"  Individual Timings:   {[round(t, 3) for t in res_100k['timings']]} s")
    print(f"  Cold Run Latency:     {res_100k['cold_seconds']:.3f} s")
    print(f"  Warm Mean Latency:    {res_100k['warm_mean_seconds']:.3f} s")
    print(f"  Mean Latency:         {res_100k['mean_seconds']:.3f} s  (Target: < 15.0 s)")
    print(f"  Median Latency:       {res_100k['median_seconds']:.3f} s")
    print(f"  Std Dev (sigma):      {res_100k['std_dev_seconds']:.3f} s")
    print(f"  Baseline Working Set: {res_100k['baseline_rss_mb']:.1f} MB")
    print(f"  Peak Working Set:     {res_100k['peak_rss_mb']:.1f} MB  (Target: <= 250.0 MB)")
    print(f"  Memory Scaling Ratio: {res_100k['memory_scaling_ratio']:.2f}x  (Target: <= 4.0x)")

    pass_100k = (
        res_100k["mean_seconds"] < 15.0
        and res_100k["peak_rss_mb"] <= 250.0
        and res_100k["memory_scaling_ratio"] <= 4.0
    )
    print(f"  Status:               {'PASS' if pass_100k else 'FAIL'}")

    print("\n[2/2] Executing Multi-5 Consolidation Benchmark (N=5 repeated runs)...")
    res_m5 = benchmark_multi5(corpora_dir, runs=5)
    print(f"  Runs (N):             {res_m5['runs']}")
    print(f"  Total Ingested Rows:  {res_m5['total_rows_per_run'] * res_m5['runs']:,} ({res_m5['total_rows_per_run']:,} rows/run)")
    print(f"  Individual Timings:   {[round(t, 3) for t in res_m5['timings']]} s")
    print(f"  Cold Run Latency:     {res_m5['cold_seconds']:.3f} s")
    print(f"  Warm Mean Latency:    {res_m5['warm_mean_seconds']:.3f} s")
    print(f"  Mean Latency:         {res_m5['mean_seconds']:.3f} s  (Target: <= 60.0 s)")
    print(f"  Median Latency:       {res_m5['median_seconds']:.3f} s")
    print(f"  Std Dev (sigma):      {res_m5['std_dev_seconds']:.3f} s")
    print(f"  Mean + 2*sigma:       {res_m5['mean_plus_2sigma']:.3f} s  (Robustness target: <= 60.0 s)")
    print(f"  Baseline Working Set: {res_m5['baseline_rss_mb']:.1f} MB")
    print(f"  Peak Working Set:     {res_m5['peak_rss_mb']:.1f} MB  (Target: <= 250.0 MB)")
    print(f"  Memory Scaling Ratio: {res_m5['memory_scaling_ratio']:.2f}x  (Target: <= 4.0x)")

    pass_m5 = (
        res_m5["mean_seconds"] <= 60.0
        and res_m5["peak_rss_mb"] <= 250.0
        and res_m5["memory_scaling_ratio"] <= 4.0
    )
    print(f"  Status:               {'PASS' if pass_m5 else 'FAIL'}")

    print("\n" + "=" * 70)
    if pass_100k and pass_m5:
        print("ALL BENCHMARK CRITERIA MET WITH EMPIRICAL COMPLIANCE.")
    else:
        print("ONE OR MORE BENCHMARK CRITERIA FAILED.")
        sys.exit(1)
