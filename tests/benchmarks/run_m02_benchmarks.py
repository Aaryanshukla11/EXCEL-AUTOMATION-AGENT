"""Reproducible benchmark verification for M02 streaming parser.

Evaluates:
1. BENCH-SCALE-100K (100,000 data rows x 50 columns sparse sheet, 4,000,050 cells)
   - Contractual target: Streaming latency < 15.0s, Peak Working Set (RSS) <= 250.0 MB.
2. BENCH-PERF-MULTI-5 (5 source workbooks x 20,000 rows + 1 master workbook = 120,000 rows)
   - Contractual target: Mean total latency <= 60.0s across N=5 runs.
"""

import os
import shutil
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


def benchmark_100k(corpora_dir: str) -> dict[str, float]:
    src_path = os.path.join(corpora_dir, "BENCH-SCALE-100K.xlsx")
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Fixture not found: {src_path}")

    # Use disposable copy to preserve workbook original
    with tempfile.TemporaryDirectory() as tmp_dir:
        disposable_path = os.path.join(tmp_dir, "BENCH-SCALE-100K-DISPOSABLE.xlsx")
        shutil.copyfile(src_path, disposable_path)

        start_rss = measure_process_rss_mb()
        peak_rss = start_rss

        t0 = time.perf_counter()
        reader = StreamingWorkbookReader(disposable_path)
        sheet_name = reader.sheet_names[0]

        total_rows = 0
        total_cells = 0

        for chunk in reader.stream_sheet(sheet_name, chunk_size=1000):
            total_rows += len(chunk)
            for row in chunk:
                total_cells += len(row["cells"])
            current_rss = measure_process_rss_mb()
            if current_rss > peak_rss:
                peak_rss = current_rss

        elapsed = time.perf_counter() - t0

    return {
        "elapsed_seconds": elapsed,
        "peak_rss_mb": peak_rss,
        "total_rows": total_rows,
        "total_cells": total_cells,
    }


def benchmark_multi5(corpora_dir: str, runs: int = 5) -> dict[str, float]:
    source_names = [f"BENCH-MULTI5-SOURCE-{i}.xlsx" for i in range(1, 6)]
    master_name = "BENCH-MULTI5-MASTER.xlsx"

    all_elapsed = []
    max_peak_rss = 0.0

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Copy to disposable paths
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
            t0 = time.perf_counter()
            run_peak_rss = measure_process_rss_mb()

            total_rows = 0
            for path in disposable_sources:
                reader = StreamingWorkbookReader(path)
                for chunk in reader.stream_sheet(0, chunk_size=1000):
                    total_rows += len(chunk)
                    rss = measure_process_rss_mb()
                    if rss > run_peak_rss:
                        run_peak_rss = rss

            master_reader = StreamingWorkbookReader(master_dst)
            for chunk in master_reader.stream_sheet(0, chunk_size=1000):
                total_rows += len(chunk)
                rss = measure_process_rss_mb()
                if rss > run_peak_rss:
                    run_peak_rss = rss

            elapsed = time.perf_counter() - t0
            all_elapsed.append(elapsed)
            if run_peak_rss > max_peak_rss:
                max_peak_rss = run_peak_rss

    mean_elapsed = sum(all_elapsed) / len(all_elapsed)
    variance = sum((x - mean_elapsed) ** 2 for x in all_elapsed) / len(all_elapsed)
    std_dev = variance ** 0.5

    return {
        "runs": runs,
        "mean_seconds": mean_elapsed,
        "std_dev_seconds": std_dev,
        "mean_plus_2sigma": mean_elapsed + 2 * std_dev,
        "min_seconds": min(all_elapsed),
        "max_seconds": max(all_elapsed),
        "peak_rss_mb": max_peak_rss,
    }


if __name__ == "__main__":
    corpora_dir = os.path.abspath(r"phase0/corpora")
    print("=" * 70)
    print("M02 BENCHMARK EVALUATION ON FROZEN PHASE 0 CORPORA")
    print("=" * 70)

    print("\n[1/2] Executing 100k Streaming Ingestion Benchmark (BENCH-SCALE-100K)...")
    res_100k = benchmark_100k(corpora_dir)
    print(f"  Rows Processed:       {res_100k['total_rows']:,}")
    print(f"  Cells Decoded:        {res_100k['total_cells']:,}")
    print(f"  Latency:              {res_100k['elapsed_seconds']:.3f} s  (Target: < 15.0 s)")
    print(f"  Peak Working Set:     {res_100k['peak_rss_mb']:.1f} MB (Target: <= 250.0 MB)")
    pass_100k = res_100k["elapsed_seconds"] < 15.0 and res_100k["peak_rss_mb"] <= 250.0
    print(f"  Status:               {'PASS' if pass_100k else 'FAIL'}")

    print("\n[2/2] Executing Multi-5 Consolidation Benchmark (N=5 repeated runs)...")
    res_m5 = benchmark_multi5(corpora_dir, runs=5)
    print(f"  Runs (N):             {res_m5['runs']}")
    print(f"  Mean Latency:         {res_m5['mean_seconds']:.3f} s  (Target: <= 60.0 s)")
    print(f"  Std Dev (sigma):      {res_m5['std_dev_seconds']:.3f} s")
    print(f"  Mean + 2*sigma:       {res_m5['mean_plus_2sigma']:.3f} s  (Robustness target: <= 60.0 s)")
    print(f"  Peak Working Set:     {res_m5['peak_rss_mb']:.1f} MB (Target: <= 250.0 MB)")
    pass_m5 = res_m5["mean_seconds"] <= 60.0 and res_m5["peak_rss_mb"] <= 250.0
    print(f"  Status:               {'PASS' if pass_m5 else 'FAIL'}")

    print("\n" + "=" * 70)
    if pass_100k and pass_m5:
        print("ALL BENCHMARK CRITERIA MET WITH EMPIRICAL COMPLIANCE.")
    else:
        print("ONE OR MORE BENCHMARK CRITERIA FAILED.")
        sys.exit(1)
