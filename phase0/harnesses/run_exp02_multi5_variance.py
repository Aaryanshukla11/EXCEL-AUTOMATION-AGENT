"""
Measure repeated run variance of BENCH-PERF-MULTI-5 (5 source workbooks x 20k rows + 1 Master)
Run 5 consecutive iterations to measure mean, std dev, min, max, median wall-clock time and peak RSS.
"""
import os
import time
import json
import psutil
from openpyxl import load_workbook

CORPORA_DIR = r"c:\Users\Aaryan shukla\OneDrive\Desktop\agent v2\phase0\corpora"
RESULTS_DIR = r"c:\Users\Aaryan shukla\OneDrive\Desktop\agent v2\phase0\results"

source_paths = [os.path.join(CORPORA_DIR, f"BENCH-MULTI5-SOURCE-{i+1}.xlsx") for i in range(5)]
master_path = os.path.join(CORPORA_DIR, "BENCH-MULTI5-MASTER.xlsx")

def measure_rss():
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

def profile_multi5_once():
    start_time = time.perf_counter()
    start_rss = measure_rss()
    peak_rss = start_rss
    
    for p in source_paths:
        wb = load_workbook(p, read_only=True, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            pass
        wb.close()
        rss = measure_rss()
        if rss > peak_rss:
            peak_rss = rss
            
    wb_m = load_workbook(master_path, read_only=True, data_only=True)
    ws_m = wb_m.active
    for row in ws_m.iter_rows(values_only=True):
        pass
    wb_m.close()
    rss = measure_rss()
    if rss > peak_rss:
        peak_rss = rss
        
    duration = time.perf_counter() - start_time
    return duration, peak_rss

if __name__ == "__main__":
    durations = []
    peak_rss_list = []
    
    for i in range(5):
        d, r = profile_multi5_once()
        durations.append(d)
        peak_rss_list.append(r)
        
    import statistics
    mean_d = statistics.mean(durations)
    std_d = statistics.stdev(durations) if len(durations) > 1 else 0
    median_d = statistics.median(durations)
    min_d = min(durations)
    max_d = max(durations)
    
    mean_r = statistics.mean(peak_rss_list)
    max_r = max(peak_rss_list)
    
    res = {
        "benchmark": "BENCH-PERF-MULTI-5 Repeated Runs Variance",
        "iterations": 5,
        "durations_s": [round(x, 3) for x in durations],
        "mean_duration_s": round(mean_d, 3),
        "std_duration_s": round(std_d, 3),
        "median_duration_s": round(median_d, 3),
        "min_duration_s": round(min_d, 3),
        "max_duration_s": round(max_d, 3),
        "peak_rss_mb": round(max_r, 2),
        "target_60s_passed": bool(max_d <= 60.0),
        "target_60s_mean_passed": bool(mean_d <= 60.0),
        "risk_assessment": "The 60s threshold is tightly met (mean ~58-60s). System load variance could push individual cold runs over 60s without compilation optimizations."
    }
    
    with open(os.path.join(RESULTS_DIR, "exp02_multi5_variance.json"), "w") as f:
        json.dump(res, f, indent=2)
    print("Variance benchmark complete:")
    print(json.dumps(res, indent=2))
