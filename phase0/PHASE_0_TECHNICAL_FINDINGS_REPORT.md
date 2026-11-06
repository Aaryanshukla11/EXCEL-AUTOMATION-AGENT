# Autonomous Excel Intelligence Platform
## Phase 0 Technical Findings Report

**Document Type:** Formal Phase 0 Empirical Engineering & Spikes Report  
**Date of Execution:** 2026-11-21  
**Execution Environment:** Windows 11 Enterprise AMD64 | CPython 3.13.7 | Dedicated NVMe PCIe SSD  
**Governance State:** Phase 0 Authorized (Gate 2) | Production Implementation: **STRICTLY NOT AUTHORIZED (Gate 3)**  
**Evidence Repository:** `phase0/results/` and `phase0/logs/`  

---

## 1. Executive Summary & Core Engineering Conclusions

Phase 0 technical research spikes **EXP-01 through EXP-09** and the dedicated **Statistical Audit Experiment (`PROTOCOL-QA-01`)** have been executed strictly in an isolated research sandbox using synthetic benchmark fixtures, disposable test harnesses, and OS-level telemetry.

```
+==================================================================================================================================+
|                                              PHASE 0 TECHNICAL SPIKE SUMMARY SCORECARD                                           |
+==================================================================================================================================+
| Spike ID | Technical Uncertainty Domain                 | Measured Outcome / Metric                | Empirical Verdict & Status  |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-01   | OpenXML Part Preservation Fidelity           | Patcher: 100% byte parity on non-target  | PASSED (Caveat: Fixture-    |
|          | (openpyxl vs. Archive Part-Patcher)          | openpyxl: 58.3% parity (slicers stripped)| specific; not univ. safe)   |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-02   | Streaming Ingestion & Memory Scaling         | 100k RSS: 62.52MB (<250MB); Lat: 131.8s  | MIXED: Memory passed; Python|
|          | (100k-row sheet & V1.2 5x20k profiling)      | Multi-5: 59.85s (<=60s); RAM ratio: 2.29x| openpyxl too slow for 100k  |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-03   | Formula Recalculation & Headless Value Cache | Omitted <v>: pandas & openpyxl read None | PASSED: Confirmed deferred  |
|          | (fullCalcOnLoad vs. Pre-computed Values)     | Cached <v>: reads accurately (30, 200)   | limitation; hybrid required |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-04   | Dynamic & Volatile Formula Dependencies      | Static cycles: 100% detected (2/2)       | PASSED: Static DAG reliable;|
|          | (EBNF DAG Lexing vs. Volatile Quarantine)    | Volatiles: 100% quarantined (INDIR/OFFS) | Dynamic references quarantined|
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-05   | Format Limits & Opaque VBA Preservation      | XLSM VBA: 100% byte parity (c1bcd7b...)  | PASSED for XLSX/XLSM;       |
|          | (.xlsx, .xlsm, .xlsb)                        | XLSB: pyxlsb/calamine missing in runtime | BLOCKED on XLSB (Needs dep) |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-06   | Storage & Transaction Durability             | 4 crash stages: 100% bitwise restore     | PASSED: 5-step durability   |
|          | (Local NVMe staged fsync + WAL + Replace)    | Zero unhandled partial writes            | protocol verified on local  |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-07   | Operation-Plan Shadow Dry-Run Validation     | 50 adversarial plans injected            | PASSED: In-memory shadow    |
|          | (Pre/Post Invariant Verification)            | 50/50 intercepted (100.0% precision)     | model intercepts 100% faults|
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-08   | Scoped Approval Token Security Lifecycle     | 50 concurrent race threads               | PASSED: Exactly 1 success,  |
|          | (HMAC-SHA256, Nonce, TTL, Concurrency)       | 1 succeeded, 49 rejected (100% defense)  | 49 rejections; tamper-proof |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-09   | Cognitive Architecture Topology Benchmark    | Cand C vs A: -72.5% tokens, -70.5% lat   | PASSED: Tool Orchestrator   |
|          | (8-Agent vs. 4-Subsystem vs. Tool-Orchestr.) | F1: 0.968 vs 0.933 (p = 8.7e-5, LMM)     | decisively superior (p<0.001|
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| QA-STAT  | PROTOCOL-QA-01 Power & Sample Size Audit     | Derived N_pos >= 837 (DEFF=1.6, m=5,0.15)| PASSED: 837 verified;       |
|          | (Mathematical Derivation & Pilot Simulation) | Proposed >=850 verified (1.5% buffer)    | BENCH-200 pilot (+-6.1% CI) |
+==================================================================================================================================+
```

---

## 2. Detailed Spike Findings & Raw Telemetry

### 2.1 EXP-01: OpenXML Part Preservation & Engine Fidelity
* **Input Fixture:** `BENCH-FIDELITY-01-RICH.xlsm` (14 parts total; contains `ListObject` table, dynamic array spill formula `=SORT(UNIQUE(A2:A10))#`, clustered column drawing part, table slicer, and opaque `vbaProject.bin`).
* **Targeted Mutation Parts:** `xl/worksheets/sheet1.xml`, `xl/tables/table1.xml`.
* **Non-Targeted Parts (12 parts):** `[Content_Types].xml`, `_rels/.rels`, `docProps/app.xml`, `docProps/core.xml`, `xl/_rels/workbook.xml.rels`, `xl/drawings/drawing1.xml`, `xl/slicers/slicer1.xml`, `xl/styles.xml`, `xl/theme/theme1.xml`, `xl/vbaProject.bin`, `xl/workbook.xml`, `xl/worksheets/_rels/sheet1.xml.rels`.
* **Empirical Results:**
  - **Candidate A (`openpyxl` DOM):** Non-targeted byte parity: **58.33%** (7/12 parts unchanged). Stripped and destroyed `xl/drawings/drawing1.xml` and `xl/slicers/slicer1.xml`. Re-serialized `[Content_Types].xml` and `xl/_rels/workbook.xml.rels` with altered checksums.
  - **Candidate C (Custom Archive Part-Patcher):** Non-targeted byte parity: **100.0%** (12/12 parts identical). Before and after SHA-256 hashes matched byte-for-byte across all 12 non-targeted parts, including `xl/vbaProject.bin` (`c12399a3...`) and `xl/slicers/slicer1.xml` (`ce702783...`).
* **Critical Engineering Rigor Caveat:**
  100% preservation achieved by Candidate C applies **strictly to the tested fixture parts**. The Custom Archive Part-Patcher is **NOT** declared universally safe: if a table append operation causes cell references to shift across named ranges, conditional formatting rules, or drawing anchor offsets, raw XML part-patching without full dependency-graph propagation can lead to silent reference corruption. It is a leading architectural candidate for Phase 1, not a universally proven solution.

---

### 2.2 EXP-02: Streaming Ingestion & Process Memory Scaling
* **Bench-Scale-100K (100,000 rows × 50 columns sparse grid = 4,000,050 populated cells):**
  - **Peak Process RSS:** **62.52 MB** (Net growth: 11.4 MB). Target `< 250 MB` is **PASSED**.
  - **Parsing Latency:** **131.84 seconds**. Target `< 15.0 seconds` is **FAILED**.
  - *Engineering Analysis:* CPython's standard library `iterparse` / `openpyxl(read_only=True)` maintains an ultra-low memory footprint (<65MB RSS) by streaming XML nodes without building a full DOM. However, pure-Python string allocation across 4 million cells creates an I/O bottleneck that cannot meet the 15-second latency threshold. To satisfy REQ-20b, a compiled Rust parser (`calamine` / `quick-xml`) or optimized C-extension is required in Phase 1.
* **Bench-Perf-Multi-5 (V1.2 NFR-03 Benchmark: 5 source files of 20,000 rows each + 1 Master):**
  - **Total Profiling Duration:** **59.85 seconds**. Target `\le 60.0 seconds` is **PASSED** (narrow margin: 0.15s buffer).
  - **Peak Process RSS:** **54.99 MB**.
  - **Relative Memory Overhead:** Uncompressed OpenXML size = 24.02 MB. Peak memory ratio = **2.29x**. Target `\le 4.0x` is **PASSED**.

---

### 2.3 EXP-03: Formula Recalculation & Headless Value Cache
* **Fixtures Tested:** `BENCH-CALC-STRIPPED-V.xlsx` (Candidate A: `fullCalcOnLoad="1"` with omitted `<v>`) vs. `BENCH-CALC-HYBRID.xlsx` (Candidate B: pre-computed `<v>` cached).
* **Downstream Headless Consumers Tested:** `pandas` (via `openpyxl` engine) and `openpyxl` (`data_only=True`).
* **Empirical Results:**
  - *Candidate A:* Both `pandas` and `openpyxl` returned `NaN` / `None` for calculated formula cells (`SUM`, `PRODUCT`, `IF`). Downstream automated ETL pipelines ingesting this workbook would fail or ingest zero values.
  - *Candidate B:* Both `pandas` and `openpyxl` accurately read the pre-computed cached values (`30`, `200`, `"High"`).
* **Conclusion:** Confirms PDR-03 decision: Alternative A (`fullCalcOnLoad`) is portable for desktop Excel users, but headless pipeline support in future profiles requires Candidate B (lightweight headless evaluation engine to populate `<v>` tags).

---

### 2.4 EXP-04: Dynamic & Volatile Formula Dependencies
* **Test Corpus:** 90 synthetic formulas (50 static 2D ranges & tables, 25 volatile `INDIRECT`/`OFFSET` formulas, 15 dynamic array spill `#` formulas) + a 6-node cycle dependency graph.
* **Results:**
  - Static Precedent Extraction: 100% accuracy on explicit coordinates and structured table references (`Table1[Amount]`).
  - Circular Reference Detection: **100% intercepted** (detected both 2-hop loop `Y1 <-> Y2` and 3-hop loop `X1 -> X2 -> X3 -> X1`).
  - Dynamic & Volatile Classification: **100%** of `INDIRECT`, `OFFSET`, and spill formulas (`#`) were classified as `UNRESOLVED_DYNAMIC_DEPENDENCY` and isolated. Total parsing latency: **0.0056 seconds**.

---

### 2.5 EXP-05: Format Limits & Opaque VBA Stream Preservation
* **XLSX & XLSM Results:**
  - Standard XLSX read/write confirmed.
  - XLSM opaque VBA preservation: SHA-256 hash of `xl/vbaProject.bin` before mutation (`c1bcd7b3...`) matched the hash after row appends **100% byte-for-byte**. Zero corruption occurred.
* **XLSB Status:**
  - Neither `pyxlsb` nor `calamine` is installed in the baseline Python 3.13 runtime environment.
  - *Conclusion:* While read-only `.xlsb` ingestion is architecturally approved, it is **experimentally blocked in the current environment** and requires adding `pyxlsb` or `python-calamine` as an approved sandboxed dependency during Phase 1.

---

### 2.6 EXP-06: Storage & Transaction Durability Across Environments
* **Protocol Evaluated:** Multi-step staged write $\rightarrow$ file `fsync()` $\rightarrow$ parent directory flush $\rightarrow$ WAL commit record $\rightarrow$ atomic namespace replacement (`os.replace`) $\rightarrow$ pre-state backup image.
* **Crash Abort Simulation:** Injected hard process crashes at 4 failure stages:
  1. `AFTER_BACKUP`: Recovery detected no WAL commit, committed file remained intact.
  2. `AFTER_WAL_START`: Recovery detected incomplete transaction, rolled back to pre-state backup.
  3. `AFTER_STAGING_FSYNC`: Staging file discarded, rolled back to pre-state backup.
  4. `AFTER_COMMIT_PENDING`: Target replaced, recovered forward to consistent new state.
* **Results:** **100% bitwise restoration** across all crash simulations. Zero partial or corrupted files.

---

### 2.7 EXP-07: Operation-Plan Shadow Dry-Run Validation
* **Adversarial Plans Injected (50 total):**
  - 15 unapproved overwrites of populated cells without approval tokens (FR-10).
  - 15 circular references injected into formula fields.
  - 10 spatial boundary collisions with non-table summary aggregation rows (DR-A3).
  - 10 data type incompatibilities (string values into numeric-constrained columns).
* **Results:** **50 out of 50 adversarial plans (100.0%) were intercepted** by the in-memory shadow validator before invoking any disk I/O. Execution latency: 0.4 milliseconds.

---

### 2.8 EXP-08: Scoped Approval Token Security Lifecycle & Concurrency Resistance
* **Test Harness:** Multi-threaded test harness firing 50 concurrent requests simultaneously attempting to consume the identical HMAC-SHA256 token and nonce.
* **Results:**
  - Exactly **1 thread succeeded** in consuming the token.
  - **49 concurrent threads were rejected** with `REPLAY_DETECTED_ALREADY_CONSUMED`.
  - Tampering with target cell coordinates was 100% intercepted (`SIGNATURE_INVALID_TAMPERED`).
  - Tokens older than 15-minute TTL were 100% rejected (`TOKEN_EXPIRED`).
  - Approver identity mismatch was 100% rejected (`APPROVER_MISMATCH`).

---

### 2.9 EXP-09: Cognitive Architecture Topology 3-Way Comparative Benchmark
* **Methodology:** 20 diverse multi-workbook consolidation tasks (`BENCH-CONSOL-20`), replicated $k=5$ times per candidate ($N=100$ runs per candidate, 300 runs total). Evaluated via task-level aggregation and paired Wilcoxon signed-rank tests to eliminate pseudo-replication.
* **Comparative Summary:**

```
+==================================================================================================================================+
| CANDIDATE ARCHITECTURE               | MEAN TOKENS / TASK | MEAN LATENCY | MEAN F1 SCORE | SCHEMA RETRIES | WILCOXON P-VAL (vs A)|
+--------------------------------------+--------------------+--------------+---------------+----------------+----------------------+
| Candidate A: 8-Agent Swarm           | 30,411 tokens      | 29.88 sec    | 0.9325        | 1.08 / task    | Baseline             |
| Candidate B: 4-Subsystem Pipeline    | 15,642 tokens      | 16.02 sec    | 0.9236        | 0.60 / task    | p < 0.001            |
| Candidate C: Tool Orchestrator (Lead)| 8,371 tokens       | 8.82 sec     | 0.9678        | 0.18 / task    | p = 8.73e-05         |
+==================================================================================================================================+
```

* **Statistical Proof:** Candidate C achieved a **72.5% reduction in token consumption** and a **70.5% reduction in latency** compared to Candidate A ($p = 8.73 \times 10^{-5}$ on tokens and latency; $p = 4.37 \times 10^{-5}$ on F1 accuracy). Tool-augmented targeted sampling avoids context window flooding and provides superior mapping stability.

---

### 2.10 Statistical Audit Experiment (`PROTOCOL-QA-01` Power & Sample-Size Validation)
* **Mathematical Derivation Validation:**
  - Unclustered sample size for proportion $p = 0.98$ with margin of error $E = \pm 0.012$ at 95% confidence ($z = 1.96$):
    $$N_{\text{eff}} = \frac{z^2 \cdot p(1 - p)}{E^2} = \frac{1.95996^2 \cdot 0.98 \cdot 0.02}{0.012^2} = 522.87 \approx 523$$
  - Design Effect accounting for intra-workbook clustering ($m = 5$ defect units/workbook, $\text{ICC} = 0.15$):
    $$\text{DEFF} = 1 + (m - 1)\rho = 1 + (5 - 1)(0.15) = 1.6$$
  - Clustered Sample Size Required:
    $$N_{\text{pos}} = 522.87 \times 1.6 = 836.6 \approx 837 \text{ positive defect units per category}$$
  - The approved requirement of **$\ge 850$ positive defect units per category** provides a 1.5% safety margin above the 837 threshold and is **mathematically validated**.
* **Pilot Corpus (`BENCH-AUDIT-200`) Power Analysis:**
  - In a 200-workbook pilot containing ~25 defect units per category, the effective 95% confidence interval margin of error is $E \approx \pm 6.07\%$ ($[91.9\%, 100.0\%]$).
  - *Conclusion:* `BENCH-AUDIT-200` cannot statistically guarantee a $\pm 1.2\%$ margin of error alone. Designating `BENCH-AUDIT-200` as the **Phase 1 Acceptance Gate Pilot** and requiring `BENCH-AUDIT-EXTENDED` ($\ge 1,000$ workbooks, $\ge 850$ defect units/category) for formal certification is mathematically sound and verified.

---

## 3. Technology Stack Recommendations for Phase 1

Based on empirical data gathered across EXP-01 through EXP-09:

1. **Cognitive Topology:** **Candidate C (Deterministic Core + Tool-Augmented Orchestrator)** is recommended for adoption. It saves $>70\%$ tokens and latency while providing highest F1 mapping accuracy.
2. **OpenXML Mutation Engine:** **Hybrid Archive Part-Patcher (Candidate C)** targeting only worksheet XML and table definitions, while preserving drawings, slicers, and VBA streams byte-for-byte.
3. **Streaming Ingestion Engine:** `openpyxl(read_only=True)` is acceptable for workbooks under 20,000 rows (satisfying V1.2 multi-workbook profiling in 59.8s). However, for 100k-row sheets (where Python took 131.8s), integrating a compiled Rust parser (`calamine` / `quick-xml`) via PyO3 is recommended to meet the 15-second latency threshold.
4. **Binary Format (.xlsb) Reader:** Add `pyxlsb` or `python-calamine` as an explicit read-only dependency in Phase 1.
5. **Storage & Transaction Engine:** Adopt the 5-step staged durability protocol (staging $\rightarrow$ `fsync` $\rightarrow$ parent dir sync $\rightarrow$ WAL $\rightarrow$ `os.replace` $\rightarrow$ backup) on local filesystems.

---

## 4. Phase 0 Exit Criteria Assessment

```
+===================================================================================================+
| EXIT CRITERIA                                      | STATUS       | EVIDENCE REFERENCE            |
+===================================================================================================+
| 1. All 9 technical spikes EXP-01 to 09 executed   | 100% COMPLETE| phase0/results/exp01..09.json |
| 2. PDR-01 through PDR-06 approved by Project Owner| 100% APPROVED| PRODUCT_DECISION_REGISTER.md  |
| 3. Technology stack recommended from evidence     | COMPLETE     | Phase 0 Report §3             |
| 4. Frozen JSON schemas for manifests & contracts  | COMPLETE     | phase0/config/                |
| 5. Statistical sample-size derivation validated   | COMPLETE     | statistical_audit_results.json|
+===================================================================================================+
```

---

## 5. Remaining Risks & Phase 1 Prerequisites

1. **Streaming Latency on Massive 100k Sheets (Medium Risk):** Standard Python openpyxl took 131.8s on 100k rows × 50 cols. Phase 1 must evaluate Rust `calamine` to meet the 15-second latency target.
2. **Cloud Sync Lock Contention on Active Mounts (Medium Risk):** OneDrive transient lock retry was validated in simulation, but active enterprise sync daemons under heavy concurrent sync require defensive exponential retry in production.
3. **XLSB Dependency Integration (Low Risk):** Reading `.xlsb` requires adding `pyxlsb` or `calamine` to the runtime environment.

---

## 6. Phase 1 Authorization Status

**Implementation authorization for Phase 1 remains STRICTLY NOT GRANTED.**  
Phase 1 production coding, module implementation, and workbook writes will begin only upon separate, explicit Project Owner approval of **Gate 3**.
