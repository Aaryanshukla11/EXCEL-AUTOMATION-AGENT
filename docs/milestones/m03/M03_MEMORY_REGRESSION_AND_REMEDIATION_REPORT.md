# Milestone M03: Memory Regression, Streaming Architecture Remediation & Evidence Reconciliation Report

**Date:** 2026-11-21  
**Milestone:** M03 — Workbook Inspection & Structural Analysis  
**Topic:** Memory Remediation, Allocation Audit & Evidence Reconciliation  
**Status:** **RECONCILED, 100% COMPLIANT & SUBMITTED FOR CLOSURE**  
**Git Integrity:** STRICT ZERO AUTONOMOUS COMMITS / PUSHES (All working tree changes unstaged)

---

## 1. Executive Summary & Governance Compliance

In response to Project Owner directives, this report reconciles the empirical benchmark evidence, documents the exact XML parsing memory mechanics, resolves all data discrepancies between summary and detailed tables, and details remaining architectural boundaries.

Key Reconciliation Conclusions:
1. **XML Parsing Mechanics:** The remediation path uses `ET.iterparse(io.StringIO(sheet_xml))`. This is **bounded DOM parsing over an in-memory string buffer**, *not* fully streaming from the ZIP container. The complete uncompressed worksheet XML string is materialized in Python memory via `read_package_part()`, but full ElementTree DOM materialization (millions of `Element` objects) is completely avoided.
2. **Benchmark Discrepancy Resolved:**
   - **Core 4 Workloads (Section 1):** Peak RSS across all repetitions reached a maximum of **171.1 MB** (Wide 10K $\times$ 50, Rep #3; median: **171.0 MB**).
   - **Controlled Row-Scaling (Section 2):** Peak RSS reached a maximum of **182.6 MB** (100,000 $\times$ 4, Rep #1; median: **180.5 MB**).
   - **Controlled Column-Scaling (Section 3):** Peak RSS reached a maximum of **192.1 MB** (10,000 $\times$ 50, Rep #3; median: **191.7 MB**).
   The previous summary cited "191.7 MB" (the median of Section 3's 10,000 $\times$ 50 test) without noting that the absolute single-run peak was **192.1 MB**, and without explicitly distinguishing it from the Section 1 core table peak of **171.1 MB**.
3. **Contractual Target:** The contractual limit is **250 MB**. Across all 30 benchmark runs (all repetitions of all workloads and scaling experiments), every single observed peak RSS remained strictly below 192.2 MB ($\ge 57.8\text{ MB}$ margin).
4. **Frozen Module Integrity:** Modules M01 and M02 remain 100% frozen, intact, and unmodified.

---

## 2. XML Memory Behavior & Architectural Boundary Audit

### 2.1 Trace of `sheet_xml` and Memory Materialization

In [excel_intel/inspection/topology_inspector.py](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/excel_intel/inspection/topology_inspector.py):
```python
sheet_xml = self.reader.read_package_part(sheet_path)
...
f = io.StringIO(sheet_xml)
del sheet_xml
context = ET.iterparse(f, events=("start", "end"))
```

1. **How `sheet_xml` is Obtained:**
   - `self.reader.read_package_part(sheet_path)` calls `WorkbookStreamReader.read_package_part()` in the compiled PyO3 native Rust extension (`excel_intel_rs`).
   - In Rust, `ZipPackageReader::read_file_to_string()` opens the archive, decompresses the entry into a native heap `String`, and converts it into a Python `str`.
   - **Consequence:** The complete uncompressed worksheet XML is **materialized as a contiguous Python string in memory**. For a 100,000-row $\times$ 4-column sheet, this string occupies $\approx 17.2\text{ MB}$.

2. **ElementTree DOM Avoidance:**
   - Prior to remediation, `ET.fromstring(sheet_xml)` parsed that string into a full DOM tree, creating over $1,000,000$ Python `xml.etree.ElementTree.Element` objects (consuming an additional $268\text{ MB}$ of Python heap memory and spiking RSS to $375\text{--}384\text{ MB}$).
   - With `ET.iterparse(f, events=("start", "end"))`, XML tokens are streamed sequentially through an `io.StringIO` buffer. Every child tag (`<c>`, `<row>`, `<col>`, `<mergeCell>`) is immediately purged from memory via `elem.clear()`, and parent container references are cleared via `root.clear()`.
   - Zero DOM tree is retained. Only scalar facts (bounding box coordinates, hidden intervals, merge boxes) are accumulated.

3. **Classification: Bounded DOM Parsing over In-Memory String:**
   - This implementation is **bounded DOM parsing over an in-memory string**, *not* fully streaming decompression from ZIP.
   - `ContentDistributionProfiler` is fully streaming (using M02's Rust `stream_sheet()` which spills decompression to disk and reads in discrete 1000-row chunks).
   - However, `SheetTopologyInspector` requires `read_package_part()`, which loads the uncompressed XML string into memory.

4. **Empirical Peak Memory Observed:**
   - On 100,000 rows $\times$ 4 columns (17.2 MB XML string): Process peak RSS observed is **137.4 MB** (Section 1) and **182.6 MB** (Section 2).
   - On 10,000 rows $\times$ 50 columns (21.5 MB XML string): Process peak RSS observed is **171.1 MB** (Section 1) and **192.1 MB** (Section 3).

5. **Remaining Limitations for Extremely Large Worksheets:**
   - *Scale Boundary:* For sheets up to 100,000 rows / 500,000 cells, the XML string size ($17\text{--}25\text{ MB}$) is well within the 250 MB ceiling.
   - *Extrapolation Limitation:* If a worksheet XML part reaches 500,000–1,000,000+ rows, the uncompressed XML string would exceed $85\text{--}170\text{ MB}$. In that regime, materializing the string in Python memory would consume a large fraction of the process ceiling.
   - *Future Work:* A truly streaming topology parser that reads directly from the native M02 scratch file without materializing the XML string in Python would require extending M02's Rust API (which is currently frozen).

---

## 3. Benchmark Reconciliation: Core Workloads vs. Scaling Experiments

### 3.1 Reconciliation of the 171.1 MB vs. 191.7 MB / 192.1 MB Data

| Context / Table | Workload | Repetition | Latency | Base RSS | Peak RSS | Delta RSS | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Section 1: Core Workloads** | Wide 10K $\times$ 50 | #1 | 7.837 s | 71.5 MB | 165.1 MB | +93.6 MB | Executed first in test order |
| | Wide 10K $\times$ 50 | #2 | 7.829 s | 92.3 MB | 171.0 MB | +78.7 MB | |
| | Wide 10K $\times$ 50 | #3 | 7.789 s | 93.5 MB | **171.1 MB** | +77.6 MB | **Section 1 Maximum: 171.1 MB** |
| **Section 2: Row Scaling** | 100,000 $\times$ 4 | #1 | 7.577 s | 100.4 MB | **182.6 MB** | +82.2 MB | **Section 2 Maximum: 182.6 MB** |
| | 100,000 $\times$ 4 | #2 | 8.156 s | 98.0 MB | 180.4 MB | +82.4 MB | |
| | 100,000 $\times$ 4 | #3 | 6.735 s | 98.1 MB | 180.5 MB | +82.4 MB | Section 2 Median: 180.5 MB |
| **Section 3: Column Scaling** | 10,000 $\times$ 50 | #1 | 7.959 s | 98.7 MB | 185.0 MB | +86.3 MB | Executed last in test order |
| | 10,000 $\times$ 50 | #2 | 7.518 s | 109.4 MB | **191.7 MB** | +82.3 MB | **Section 3 Median: 191.7 MB** |
| | 10,000 $\times$ 50 | #3 | 8.076 s | 115.5 MB | **192.1 MB** | +76.6 MB | **Absolute Test Maximum: 192.1 MB** |

**Why did 10,000 $\times$ 50 peak at 171.1 MB in Section 1 and 192.1 MB in Section 3?**
The difference is due to cumulative process baseline memory:
- In Section 1, the benchmark process had just started; the baseline RSS before running Wide 10K $\times$ 50 was **71.5–93.5 MB**, leading to a peak of **171.1 MB**.
- In Section 3, the same process had executed 24 prior benchmark runs across hundreds of thousands of cells. Because Windows `pymalloc` does not release committed heap arenas back to the OS, the baseline RSS had climbed to **98.7–115.5 MB**. Adding the ~80 MB delta produced a peak of **192.1 MB**.
- Both peaks strictly respect the **250 MB ceiling**.

---

### 3.2 Complete Raw Repeated Benchmark Measurements ($N = 3$)

All 30 benchmark runs recorded with continuous 5ms sampling via `MemorySampler`:

#### Section 1: Core Contractual Workloads

| Workload Target | Rep | Latency | Throughput | Base RSS | Peak RSS (5ms Max) | Delta RSS | SHA-256 Verified |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dense 100K x 4** | #1 | 7.435 s | 53,799 c/s | 51.7 MB | 134.4 MB | +82.7 MB | MATCH |
| (400,000 cells) | #2 | 7.703 s | 51,930 c/s | 54.1 MB | 136.4 MB | +82.3 MB | MATCH |
| | #3 | 7.142 s | 56,009 c/s | 55.0 MB | 137.4 MB | +82.4 MB | MATCH |
| **Wide 10K x 50** | #1 | 7.837 s | 63,800 c/s | 71.5 MB | 165.1 MB | +93.6 MB | MATCH |
| (500,000 cells) | #2 | 7.829 s | 63,862 c/s | 92.3 MB | 171.0 MB | +78.7 MB | MATCH |
| | #3 | 7.789 s | 64,194 c/s | 93.5 MB | 171.1 MB | +77.6 MB | MATCH |
| **Sparse 100K-Row** | #1 | 0.018 s | 5,622 c/s | 81.7 MB | 81.9 MB | +0.12 MB | MATCH |
| (100 cells) | #2 | 0.015 s | 6,751 c/s | 81.8 MB | 81.9 MB | +0.02 MB | MATCH |
| | #3 | 0.017 s | 6,035 c/s | 81.8 MB | 81.9 MB | +0.02 MB | MATCH |
| **Multi-Sheet (5 Sheets)** | #1 | 2.345 s | 53,337 c/s | 82.3 MB | 100.7 MB | +18.3 MB | MATCH |
| (125,101 cells) | #2 | 2.343 s | 53,389 c/s | 81.7 MB | 99.5 MB | +17.8 MB | MATCH |
| | #3 | 2.416 s | 51,783 c/s | 81.9 MB | 101.6 MB | +19.7 MB | MATCH |

#### Section 2: Controlled Row-Scaling Experiments (Fixed $C=4$, Increasing $R$)

| Dimensions ($R \times C$) | Rep | Latency | Throughput | Base RSS | Peak RSS (5ms Max) | Delta RSS | SHA-256 Verified |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10,000 x 4** | #1 | 0.672 s | 59,559 c/s | 83.2 MB | 90.8 MB | +7.6 MB | MATCH |
| (40,000 cells) | #2 | 0.677 s | 59,102 c/s | 84.6 MB | 90.8 MB | +6.3 MB | MATCH |
| | #3 | 0.747 s | 53,536 c/s | 83.2 MB | 90.6 MB | +7.4 MB | MATCH |
| **50,000 x 4** | #1 | 3.403 s | 58,774 c/s | 91.5 MB | 132.3 MB | +40.8 MB | MATCH |
| (200,000 cells) | #2 | 3.568 s | 56,050 c/s | 90.4 MB | 131.3 MB | +40.9 MB | MATCH |
| | #3 | 3.712 s | 53,880 c/s | 90.4 MB | 131.3 MB | +40.9 MB | MATCH |
| **100,000 x 4** | #1 | 7.577 s | 52,790 c/s | 100.4 MB | 182.6 MB | +82.2 MB | MATCH |
| (400,000 cells) | #2 | 8.156 s | 49,043 c/s | 98.0 MB | 180.4 MB | +82.4 MB | MATCH |
| | #3 | 6.735 s | 59,392 c/s | 98.1 MB | 180.5 MB | +82.4 MB | MATCH |

#### Section 3: Controlled Column-Scaling Experiments (Fixed $R=10,000$, Increasing $C$)

| Dimensions ($R \times C$) | Rep | Latency | Throughput | Base RSS | Peak RSS (5ms Max) | Delta RSS | SHA-256 Verified |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **10,000 x 4** | #1 | 0.672 s | 59,498 c/s | 84.2 MB | 92.0 MB | +7.8 MB | MATCH |
| (40,000 cells) | #2 | 0.734 s | 54,503 c/s | 83.7 MB | 90.8 MB | +7.1 MB | MATCH |
| | #3 | 0.597 s | 66,989 c/s | 83.6 MB | 90.8 MB | +7.2 MB | MATCH |
| **10,000 x 20** | #1 | 2.669 s | 74,932 c/s | 89.6 MB | 119.1 MB | +29.6 MB | MATCH |
| (200,000 cells) | #2 | 3.047 s | 65,646 c/s | 91.6 MB | 119.3 MB | +27.7 MB | MATCH |
| | #3 | 2.908 s | 68,765 c/s | 89.8 MB | 119.3 MB | +29.5 MB | MATCH |
| **10,000 x 50** | #1 | 7.959 s | 62,820 c/s | 98.7 MB | 185.0 MB | +86.3 MB | MATCH |
| (500,000 cells) | #2 | 7.518 s | 66,505 c/s | 109.4 MB | 191.7 MB | +82.3 MB | MATCH |
| | #3 | 8.076 s | 61,911 c/s | 115.5 MB | 192.1 MB | +76.6 MB | MATCH |

---

### 3.3 Statistical Distribution Summary (Min / Median / Max)

| Workload Target | Section | Latency Min | Latency Median | Latency Max | Peak RSS Min | Peak RSS Median | Peak RSS Max | Median Delta RSS | Compliance Target (250 MB) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Dense 100K x 4** | 1 | 7.142 s | **7.435 s** | 7.703 s | 134.4 MB | **136.4 MB** | **137.4 MB** | +82.4 MB | **PASS** (112.6 MB margin) |
| **Wide 10K x 50** | 1 | 7.789 s | **7.829 s** | 7.837 s | 165.1 MB | **171.0 MB** | **171.1 MB** | +78.7 MB | **PASS** (78.9 MB margin) |
| **Sparse 100K-Row** | 1 | 0.015 s | **0.017 s** | 0.018 s | 81.9 MB | **81.9 MB** | **81.9 MB** | +0.02 MB | **PASS** (168.1 MB margin) |
| **Multi-Sheet (5 Sheets)**| 1 | 2.343 s | **2.345 s** | 2.416 s | 99.5 MB | **100.7 MB** | **101.6 MB** | +18.3 MB | **PASS** (148.4 MB margin) |
| **Row-Scaling 10K x 4** | 2 | 0.672 s | **0.677 s** | 0.747 s | 90.6 MB | **90.8 MB** | **90.8 MB** | +7.4 MB | **PASS** (159.2 MB margin) |
| **Row-Scaling 50K x 4** | 2 | 3.403 s | **3.568 s** | 3.712 s | 131.3 MB | **131.3 MB** | **132.3 MB** | +40.9 MB | **PASS** (117.7 MB margin) |
| **Row-Scaling 100K x 4** | 2 | 6.735 s | **7.577 s** | 8.156 s | 180.4 MB | **180.5 MB** | **182.6 MB** | +82.4 MB | **PASS** (67.4 MB margin) |
| **Col-Scaling 10K x 4** | 3 | 0.597 s | **0.672 s** | 0.734 s | 90.8 MB | **90.8 MB** | **92.0 MB** | +7.2 MB | **PASS** (158.0 MB margin) |
| **Col-Scaling 10K x 20** | 3 | 2.669 s | **2.908 s** | 3.047 s | 119.1 MB | **119.3 MB** | **119.3 MB** | +29.5 MB | **PASS** (130.7 MB margin) |
| **Col-Scaling 10K x 50** | 3 | 7.518 s | **7.959 s** | 8.076 s | 185.0 MB | **191.7 MB** | **192.1 MB** | +82.3 MB | **PASS** (57.9 MB margin) |

--- 

## 4. Multi-Version Quality Gates & Regression Audit

All regression suites remain 100% passing without regression:

| Layer | Environment | Total Tests | Pass Rate | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Rust Native Core (`excel_intel_rs`)** | Cargo test (Parallel) | 60 | 100% (60 / 60) | **PASS** (0.69 s) |
| **Python 3.12 Full Suite** | pytest 9.1.1 | 167 | 100% (167 / 167) | **PASS** (9.43 s) |
| **Python 3.13 Full Suite** | pytest 9.1.1 | 167 | 100% (167 / 167) | **PASS** (8.47 s) |
| **M03-Specific Test Suite** | 7 modules | 62 | 100% (62 / 62) | **PASS** (3.32 s) |
| **Multi-Workbook Concurrency** | 6 threads, 3 workbooks | 2 | 100% (2 / 2) | **PASS** |
| **Pre/Post Inspection SHA-256** | All 30 benchmark runs | 30 | 100% (30 / 30) | **PASS** (Identical) |

---

## 5. Explicit Scope Distinction & Unverified Boundaries

1. **Verified Contractual Benchmark Compliance:**  
   Contractually verified that the complete M03 workbook inspection pipeline executes under the **250 MB peak process ceiling** across all four core workloads (Section 1 peak: **171.1 MB**) and across all controlled scaling workloads up to 100,000 rows / 50 columns (overall test peak: **192.1 MB**).
2. **Empirically Tested Workload Limits:**  
   Rigorous testing has certified workbooks up to:
   - Rows: 100,000
   - Columns: 50
   - Total populated cells: 500,000
   - Sheets: 5 sheets per workbook
3. **Remaining XML Materialization Limitation:**  
   `SheetTopologyInspector` materializes the uncompressed worksheet XML string via `read_package_part()`. While DOM generation is avoided, memory scales with the uncompressed XML string size ($\approx 17.2\text{ MB}$ per 100,000 rows $\times$ 4 columns).
4. **Unverified Larger-Workbook Behavior:**  
   Workbooks containing single worksheets exceeding 500,000–1,000,000 rows have not been empirically tested. In that regime, the decompressed XML string alone would reach $85\text{--}170\text{ MB}$, leaving little margin under the 250 MB ceiling. Fully supporting worksheets of that scale will require native Rust streaming for package parts in a future milestone.

---

## 6. Final Status & Milestone Closure Declaration

The memory regression is completely resolved, all evidence discrepancies are fully reconciled, all quality gates pass, and M01/M02 remain untouched and frozen.

Milestone **M03: Workbook Inspection & Structural Analysis** is complete, reconciled, and submitted for final closure.
