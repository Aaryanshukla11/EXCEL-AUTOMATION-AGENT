"""
EXP-02: Streaming Ingestion & Process Memory Scaling Benchmark
Evaluates Resident Set Size (RSS) and wall-clock time on:
1. BENCH-SCALE-100K (100,000 rows x 50 columns sparse sheet)
2. BENCH-PERF-MULTI-5 (5 source workbooks up to 20,000 rows each + 1 Master, V1.2 NFR-03 benchmark)
"""
import os
import sys
import time
import json
import psutil
from openpyxl import Workbook, load_workbook

RESULTS_DIR = r"c:\Users\Aaryan shukla\OneDrive\Desktop\agent v2\phase0\results"
CORPORA_DIR = r"c:\Users\Aaryan shukla\OneDrive\Desktop\agent v2\phase0\corpora"
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(CORPORA_DIR, exist_ok=True)

def generate_100k_sheet():
    path = os.path.join(CORPORA_DIR, "BENCH-SCALE-100K.xlsx")
    if os.path.exists(path):
        return path
    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    headers = [f"Col_{i}" for i in range(50)]
    ws.append(headers)
    # Generate 100k rows
    for r in range(100000):
        # 20% sparsity
        row = [f"Val_{r}_{c}" if (r + c) % 5 != 0 else None for c in range(50)]
        ws.append(row)
    wb.save(path)
    return path

def generate_multi_5_workbooks():
    paths = []
    for f_idx in range(5):
        path = os.path.join(CORPORA_DIR, f"BENCH-MULTI5-SOURCE-{f_idx+1}.xlsx")
        paths.append(path)
        if not os.path.exists(path):
            wb = Workbook(write_only=True)
            ws = wb.create_sheet()
            ws.append([f"Header_{c}" for c in range(20)])
            for r in range(20000):
                ws.append([f"Data_{r}_{c}" for c in range(20)])
            wb.save(path)
    master_path = os.path.join(CORPORA_DIR, "BENCH-MULTI5-MASTER.xlsx")
    if not os.path.exists(master_path):
        wb = Workbook(write_only=True)
        ws = wb.create_sheet()
        ws.append([f"MasterCol_{c}" for c in range(25)])
        for r in range(5000):
            ws.append([f"MasterVal_{r}_{c}" for c in range(25)])
        wb.save(master_path)
    return paths, master_path

def measure_rss():
    proc = psutil.Process(os.getpid())
    return proc.memory_info().rss / (1024 * 1024) # MB

def test_streaming_read(path, max_rows=None):
    start_rss = measure_rss()
    start_time = time.perf_counter()
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    row_count = 0
    cell_count = 0
    peak_rss = start_rss
    for row in ws.iter_rows(values_only=True):
        row_count += 1
        cell_count += len([c for c in row if c is not None])
        if row_count % 10000 == 0:
            current_rss = measure_rss()
            if current_rss > peak_rss:
                peak_rss = current_rss
        if max_rows and row_count >= max_rows:
            break
    wb.close()
    duration = time.perf_counter() - start_time
    final_rss = measure_rss()
    return {
        "duration_s": round(duration, 3),
        "peak_rss_mb": round(peak_rss, 2),
        "start_rss_mb": round(start_rss, 2),
        "final_rss_mb": round(final_rss, 2),
        "net_rss_growth_mb": round(final_rss - start_rss, 2),
        "rows_read": row_count,
        "cells_read": cell_count
    }

if __name__ == "__main__":
    print("Generating/Checking benchmark files...")
    path_100k = generate_100k_sheet()
    source_paths, master_path = generate_multi_5_workbooks()
    
    print("Executing EXP-02 Part 1: Streaming read on 100k rows (BENCH-SCALE-100K)...")
    res_100k = test_streaming_read(path_100k)
    
    print("Executing EXP-02 Part 2: Profiling 5 sources (20k rows each) + Master (V1.2 NFR-03)...")
    multi_start = time.perf_counter()
    start_rss_multi = measure_rss()
    peak_rss_multi = start_rss_multi
    multi_results = []
    
    for s_path in source_paths:
        r = test_streaming_read(s_path)
        multi_results.append(r)
        if r["peak_rss_mb"] > peak_rss_multi:
            peak_rss_multi = r["peak_rss_mb"]
            
    master_res = test_streaming_read(master_path)
    if master_res["peak_rss_mb"] > peak_rss_multi:
        peak_rss_multi = master_res["peak_rss_mb"]
        
    total_multi_duration = time.perf_counter() - multi_start
    
    # Calculate uncompressed sheet size ratio for V1.2 NFR-03
    uncompressed_size_mb = sum([os.path.getsize(p) for p in source_paths + [master_path]]) / (1024 * 1024) * 3.5 # OpenXML zip expansion factor ~3.5x
    mem_ratio = peak_rss_multi / uncompressed_size_mb if uncompressed_size_mb > 0 else 0
    
    summary = {
        "experiment": "EXP-02: Streaming Ingestion & Memory Scaling",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bench_scale_100k": {
            "file": path_100k,
            "metrics": res_100k,
            "meets_target_rss_under_250mb": res_100k["peak_rss_mb"] < 250.0,
            "meets_target_latency_under_15s": res_100k["duration_s"] < 15.0
        },
        "bench_perf_multi_5": {
            "total_duration_s": round(total_multi_duration, 3),
            "meets_target_latency_under_60s": total_multi_duration <= 60.0,
            "peak_rss_mb": round(peak_rss_multi, 2),
            "estimated_uncompressed_mb": round(uncompressed_size_mb, 2),
            "memory_ratio": round(mem_ratio, 2),
            "meets_target_memory_under_4x": mem_ratio <= 4.0,
            "sources": multi_results,
            "master": master_res
        }
    }
    
    with open(os.path.join(RESULTS_DIR, "exp02_results.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("EXP-02 completed successfully.")
    print(json.dumps(summary, indent=2))
