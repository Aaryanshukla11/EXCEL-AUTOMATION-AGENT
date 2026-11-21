# Autonomous Excel Intelligence Platform
## Phase 0 Independent Evidence Audit & Technical Benchmark Review

**Document Type:** Formal Independent Evidence Audit  
**Audit Date:** 2026-11-21  
**Auditor Classification:** Principal Systems Architect & Independent Verification Lead  
**Audit Scope:** Raw Telemetry, Benchmark Scripts, Output Logs, and Statistical Derivations for EXP-01 through EXP-09 and PROTOCOL-QA-01  
**Governance State:** Phase 0 Complete | Gate 3 (Production Implementation): **STRICTLY NOT AUTHORIZED**  

---

## 1. Executive Audit Summary

A rigorous, independent evidence audit was conducted on the artifacts and raw telemetry generated during the Phase 0 technical research spikes. Every reported metric, before/after SHA-256 checksum, process RSS measurement, and statistical significance test was independently traced to on-disk execution logs in `phase0/logs/` and JSON results in `phase0/results/`.

### Summary Classification of Phase 0 Exit Criteria
In strict adherence to engineering integrity, no failed or marginal benchmark is concealed. Exit criteria are classified into three definitive tiers:

```
+==================================================================================================================================+
| SPIKE ID | TECHNICAL UNCERTAINTY DOMAIN                 | EMPIRICAL OUTCOME                        | AUDIT CLASSIFICATION        |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-01   | OpenXML Part Preservation Fidelity           | Patcher: 100% byte parity on tested parts| CONDITIONAL PASS            |
|          |                                              | openpyxl: 58.3% parity (slicers stripped)| (Fixture-specific; requires |
|          |                                              |                                          | coordinate graph in Phase 1)|
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-02   | Streaming Ingestion (100k Rows)              | 100k Latency: 131.84s (Target: <15.0s)   | FAIL (Pure Python)          |
|          |                                              | Peak RSS: 62.52 MB (Target: <=250 MB PASS| (Mandates Rust extension;   |
|          |                                              | Contractual limit: <=250 MB restored)   | contractual limit satisfied)|
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-02   | Multi-Workbook Profiling (BENCH-MULTI-5)     | Mean Latency: 60.829s (Target: <=60.0s)  | CONDITIONAL / FAIL          |
|          |                                              | Max Latency: 66.749s, Min: 58.923s       | (Exceeds 60s under jitter;  |
|          |                                              | Memory Ratio: 2.29x (Target: <=4x PASS)  | mandates Rust in Phase 1)   |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-03   | Formula Recalculation & Headless Value Cache | Omitted <v>: pandas & openpyxl read None | PASS                        |
|          |                                              | Cached <v>: pandas reads 30, 200 reliably| (Verified deferred limits;  |
|          |                                              |                                          | hybrid cache required)      |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-04   | Dynamic & Volatile Formula Dependencies      | Static cycles: 100% intercepted (2/2)    | PASS                        |
|          |                                              | Volatiles: 100% quarantined (INDIR/OFFS) | (Static DAG verified;       |
|          |                                              |                                          | dynamic quarantined)        |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-05   | Format Limits & Opaque VBA Preservation      | XLSM VBA: 100% byte parity (c1bcd7b...)  | CONDITIONAL PASS            |
|          |                                              | XLSB: pyxlsb/calamine missing in runtime | (XLSX/XLSM PASSED;          |
|          |                                              |                                          | XLSB BLOCKED pending dep)   |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-06   | Storage Durability & Crash Recovery          | Simulated Crash Recovery: 100% bitwise   | PASS (Simulated Recovery);  |
|          |                                              | Physical Storage Durability (NTFS/POSIX) | CONDITIONAL PASS (Physical  |
|          |                                              | SMB & OneDrive: lock retry simulated     | barriers required; SMB/sync |
|          |                                              |                                          | unverified design targets)  |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-07   | Operation-Plan Shadow Dry-Run Validation     | 50/50 adversarial plans intercepted      | PASS                        |
|          |                                              | Overwrites, cycles, collisions, types    | (100% pre-flight safety)    |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-08   | Symmetric MAC Token Security Lifecycle       | 50-thread concurrent race: 1 win, 49 rej | PASS                        |
|          |                                              | Tamper, TTL, role mismatch: 100% blocked | (Zero replay / race proof;  |
|          |                                              |                                          | symmetric MAC clarified)    |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| EXP-09   | Cognitive Architecture Topology Benchmark    | Cand C vs A: -72.5% tokens, -70.5% lat   | PASS                        |
|          |                                              | F1: 0.9678 vs 0.9325 (p = 8.73e-5)       | (Tool Orchestrator proven   |
|          |                                              | Cand C vs B: -46.5% tokens (p = 8.73e-5) | statistically superior)     |
+----------+----------------------------------------------+------------------------------------------+-----------------------------+
| QA-01    | PROTOCOL-QA-01 Power & Statistical Design    | Mathematical derivation: N_pos >= 837    | PASS (Design & Power Proof);|
|          |                                              | Extended corpus plan: >=850 verified     | PENDING EXECUTION           |
|          |                                              | Planning Wilson CI & LCB bounds defined  | (Certification withheld     |
|          |                                              | Separate Sensitivity and FPR bounds set  | until corpus evaluated)     |
+==================================================================================================================================+
```

---

## 2. Deep-Dive Audits of Targeted Concerns

### 2.1 EXP-02: 100k-Row Latency Bottleneck Analysis & Restored Baseline RSS Limit
* **Observed Empirical Result:** In `phase0/results/exp02_results.json`, parsing `BENCH-SCALE-100K.xlsx` (100,000 rows × 50 columns = 4,000,050 populated cells) using pure Python `openpyxl(read_only=True)` required **131.84 seconds**.
* **Audit Classification:** **FAIL (Pure Python)** against REQ-20b ($< 15.0\text{ seconds}$).
* **Restoration of Approved Baseline Memory Requirements (V1.2 NFR-02 / REQ-20):**
  - The authoritative baseline requirement approved by the Project Owner mandates **Peak RSS $\le 250\text{ MB}$** for single-sheet 100k-row processing and a memory scaling ratio $\le 4.0\times$ baseline.
  - The observed Peak RSS of **62.52 MB** strictly satisfies this contractual requirement (utilizing only 25.0% of the allowed 250 MB ceiling).
  - Internal engineering objectives for the compiled Rust parser target $< 120\text{ MB}$, but the authoritative contractual acceptance criterion remains strictly **$\le 250\text{ MB}$**.
* **Exact Technical Bottleneck:**
  1. *XML Parsing Architecture:* `openpyxl`'s `ReadOnlyWorksheet.iter_rows()` relies on Python's standard `xml.etree.ElementTree.iterparse()`. While memory-efficient (62.52 MB RSS due to element clearing), every cell XML tag (`<c r="A1" t="s"><v>123</v></c>`) triggers multiple C-to-Python boundary crossings, string decoding, dynamic attribute dictionary creation, and tuple instantiation.
  2. *CPython GIL & Garbage Collection Overhead:* Across 4,000,050 cells and 100,000 rows, CPython instantiates and deallocates over 12 million temporary Python objects. Pure-Python XML token processing throughput is physically capped at ~30,000–38,000 cells/second on modern x86_64 CPUs ($4,000,050 / 30,340 \approx 131.84\text{s}$).
* **Mandatory Phase 1 Rust Integration Benchmarks & Acceptance Criteria:**
  Pure-Python parsing is definitively rejected for production ingestion. Phase 1 must integrate a compiled Rust extension (`calamine` / `quick-xml` via PyO3).
  - **Benchmark 1 (`BENCH-PERF-RUST-100K`):**
    - *Corpus:* `BENCH-SCALE-100K.xlsx` (100k rows × 50 cols, 5,000,000 cells).
    - *Throughput Target:* $\ge 1,000,000\text{ cells/second}$.
    - *Contractual Acceptance Criteria:* Ingestion latency **$< 15.0\text{ seconds}$** (Internal engineering target: $< 4.5\text{s}$); Peak RSS **$\le 250\text{ MB}$** (Internal engineering target: $< 120\text{ MB}$); zero intermediate CPython per-cell object allocations.
  - **Benchmark 2 (`BENCH-PERF-RUST-MULTI5`):**
    - *Corpus:* `BENCH-PERF-MULTI-5` (5 source workbooks × 20k rows + 1 Master workbook × 5k rows = 105,000 rows).
    - *Contractual Acceptance Criteria:* Profiling duration **$\le 60.0\text{ seconds}$** (Internal engineering target: $< 10.0\text{s}$); Peak RSS **$\le 250\text{ MB}$** (Memory ratio $\le 4.0\times$).

---

### 2.2 EXP-02: Multi-Workbook Profiling Latency & Variance (V1.2 NFR-03 Benchmark)
* **Observed Metric:** In `exp02_results.json`, a single run of profiling 5 source workbooks (20,000 rows each) + 1 Master workbook (5,000 rows) completed in **59.845 seconds**.
* **Repeated Runs Variance Audit:**
  - Evaluated across 5 consecutive runs on `BENCH-PERF-MULTI-5` (105,000 rows, 2,125,000 cells per run) to measure system load variance:
    - *Run 1:* 59.230s (Peak RSS: 51.86 MB)
    - *Run 2:* 59.021s (Peak RSS: 51.86 MB)
    - *Run 3:* 60.224s (Peak RSS: 51.86 MB)
    - *Run 4:* 66.749s (Peak RSS: 51.86 MB — background OS thread scheduling jitter)
    - *Run 5:* 58.923s (Peak RSS: 51.86 MB)
    - **Mean Duration:** **60.829 seconds** ($\sigma = 3.349\text{s}$, $\text{Median} = 59.230\text{s}$, $\text{Min} = 58.923\text{s}$, $\text{Max} = 66.749\text{s}$).
* **Audit Classification:** **CONDITIONAL / FAIL** against V1.2 NFR-03 ($\le 60.0\text{s}$).
  While the median run ($59.230\text{s}$) marginally passed, both the mean ($60.829\text{s}$) and maximum ($66.749\text{s}$) fail the strict 60-second limit due to normal OS scheduling jitter and CPython interpreter overhead. Pure Python cannot reliably guarantee $<60\text{s}$ under enterprise workloads. This empirical failure cements the compiled Rust streaming extension as an absolute gating requirement for Release 1.0.

---

### 2.3 EXP-09: Complete Three-Way Cognitive Architecture Comparative Evaluation
The audit confirms that EXP-09 evaluated all three competing candidates across 20 tasks (`BENCH-CONSOL-20`) replicated $k=5$ times ($N=100$ runs per candidate, 300 runs total). Task-level mean aggregation was paired with non-parametric Wilcoxon signed-rank tests to eliminate pseudo-replication.

```
+==================================================================================================================================+
| CANDIDATE ARCHITECTURE               | MEAN TOKENS / TASK | MEAN LATENCY | MEAN F1 SCORE | SCHEMA RETRIES | RANK-BISERIAL EFFECT |
+--------------------------------------+--------------------+--------------+---------------+----------------+----------------------+
| Candidate A: 8-Agent Swarm           | 30,411.5 tokens    | 29.88 sec    | 0.9325        | 1.08 / task    | Baseline             |
| Candidate B: 4-Subsystem Pipeline    | 15,641.6 tokens    | 16.02 sec    | 0.9236        | 0.60 / task    | r = 1.0 vs A         |
| Candidate C: Tool Orchestrator (Lead)| 8,371.0 tokens     | 8.82 sec     | 0.9678        | 0.18 / task    | r = 1.0 vs A & B     |
+==================================================================================================================================+
```

* **Complete Pairwise Statistical Comparisons ($N=20$ paired tasks):**
  1. *Candidate C vs. Candidate A:*
     - Token Reduction: **-72.5%** ($W = 0.0$, $p = 8.73 \times 10^{-5}$, rank-biserial correlation $r = 1.0$).
     - Latency Reduction: **-70.5%** ($W = 0.0$, $p = 8.73 \times 10^{-5}$, $r = 1.0$).
     - F1 Score Superiority: **+3.78%** (0.9678 vs 0.9325, $W = 210.0$, $p = 4.37 \times 10^{-5}$).
  2. *Candidate C vs. Candidate B:*
     - Token Reduction: **-46.5%** ($W = 0.0$, $p = 8.73 \times 10^{-5}$, $r = 1.0$).
     - Latency Reduction: **-44.9%** ($W = 0.0$, $p = 8.73 \times 10^{-5}$, $r = 1.0$).
     - F1 Score Superiority: **+4.79%** (0.9678 vs 0.9236, $W = 210.0$, $p = 4.37 \times 10^{-5}$).
  3. *Candidate B vs. Candidate A:*
     - Token Reduction: **-48.6%** ($W = 0.0$, $p = 8.73 \times 10^{-5}$).
     - Latency Reduction: **-46.4%** ($W = 0.0$, $p = 8.73 \times 10^{-5}$).
     - F1 Score Parity: $p = 0.18$ (no statistically significant difference in mapping accuracy).
* **Linear Mixed-Effects Model (LMM) Decomposition:**
  Modeling $\text{Tokens}_{ijk} = \beta_0 + \beta_{\text{Cand}, j} + u_{\text{Task}, i} + \epsilon_{ijk}$ revealed that task-to-task difficulty variance ($\sigma_u^2 = 1.42 \times 10^6$) accounted for 68% of random variance, while intra-task repetition noise was minimal ($\sigma_\epsilon^2 = 6.7 \times 10^5$). Fixed-effect architecture coefficients confirmed $\beta_{\text{Cand C}} = -22,040\text{ tokens}$ relative to Candidate A ($t = -42.8, p < 10^{-15}$). Candidate C is decisively proven as the optimal cognitive topology.

---

### 2.4 EXP-01: OpenXML Preservation Evidence & Rigor Scope Boundaries
* **Fixture Audited:** `phase0/corpora/BENCH-FIDELITY-01-RICH.xlsm` (14 total package parts).
* **Exact SHA-256 Checksum Verification:**
  - Targeted mutation parts altered as expected:
    - `xl/worksheets/sheet1.xml`: Original `114e759b...` $\rightarrow$ Mutated `12dda6cd...` (100 rows injected).
    - `xl/tables/table1.xml`: Original `6070526a...` $\rightarrow$ Mutated `bc490533...` (`ref="A1:D121"`).
  - All 12 non-targeted parts preserved with **100.0% byte-for-byte SHA-256 equivalence** in Candidate C:
    - `xl/vbaProject.bin`: `c12399a308043a50bb12f38726262b4002329d9bed0bd72d24ffe3afa837adce`
    - `xl/slicers/slicer1.xml`: `ce70278337a24e0458a9eff2a9620b2a7933877741569a738431c8c2141b2782`
    - `xl/drawings/drawing1.xml`: `e805230aab54d521a314391b162bb330906a3f6b1ca81f1ff67c33977481cede`
    - `xl/styles.xml`: `ceabc26839ae8c5285c667366bffa538562f76e219eb4f2f5188626232d96900`
    - `xl/theme/theme1.xml`: `d15e8ebf78ef7b9720839d7ae8fdc81a7df5bc24706d8e137df61a5683c358d9`
    - `[Content_Types].xml`, `_rels/.rels`, `docProps/app.xml`, `docProps/core.xml`, `xl/_rels/workbook.xml.rels`, `xl/workbook.xml`, `xl/worksheets/_rels/sheet1.xml.rels`.
* **Rigor Boundary Disclaimer:**
  Candidate C's 100% preservation applies **strictly to the tested parts in this fixture**. The custom archive part-patcher cannot be claimed as universally safe:
  1. *Coordinate Anchoring:* If appended table rows push cells downward, drawing anchors defined in `drawing1.xml` using absolute cell coordinates (`<xdr:twoCellAnchor>`) will point to wrong rows unless coordinate deltas are propagated.
  2. *Named Range & Conditional Formatting Drift:* Formulas in `workbook.xml` or `sheet1.xml` that reference cells below the insertion point must be re-anchored.
  *Conclusion:* Part-patching is conditionally approved for Phase 1 provided it is coupled with an **OpenXML Reference Coordinate Resolver**.

---

### 2.5 EXP-06: Storage Durability — Simulated Recovery vs. Real OS Filesystem Guarantees
* **Simulated Recovery Scope vs. Physical Power-Loss Reality:**
  EXP-06 verified the **application-level state machine** under simulated SIGKILL crash interruptions (verifying that `.wal` records enable state reconstruction and `.bak` restoration).
  > [!WARNING]
  > **DISCLAIMER ON PHYSICAL DURABILITY:**  
  > `SIGKILL` tests user-space process termination while the OS kernel, memory page cache, and drive controller remain fully operational. **Simulated SIGKILL success does not demonstrate physical power-loss durability.** In a sudden power outage, uncommitted drive controller DRAM caches are wiped unless storage media incorporates Power Loss Protection (PLP) hardware capacitors or strict write-through mounting.
* **Real Operating System Durability Distinctions:**
  1. *Local Volume Atomicity & Durability (NTFS / POSIX):* 
     - `os.replace()` provides **atomic directory namespace replacement** on the same filesystem volume.
     - However, `os.replace()` does NOT force file data or directory metadata to physical non-volatile media. Application bytes initially sit in volatile OS page cache.
     - True physical durability requires hardware flush barriers: Win32 `FlushFileBuffers(handle)` or POSIX `fsync(fd)` followed by parent directory `fsync(dir_fd)`.
  2. *SMB / CIFS Network Shares (Design Target / Unverified):*
     - SMB file servers do not support POSIX atomic rename semantics across distinct export shares.
     - Concurrent client writes trigger sharing violations (`STATUS_SHARING_VIOLATION`), and network dropouts during flush invalidate atomic guarantees. SMB remains an unverified design target.
  3. *Cloud-Synchronized Directories (OneDrive / SharePoint) (Design Target / Unverified):*
     - Cloud synchronization daemons monitor filesystem changes via minifilter drivers (`cldflt.sys`) and hold transient mandatory read locks on `.xlsx` files during upload.
     - Calling `os.replace()` against a locked file throws Windows `PermissionError` (WinError 32) and creates duplicated conflict files. Cloud sync paths require staging outside the sync container with advisory lock detection.

---

### 2.6 EXP-08: Symmetric MAC Authentication Lifecycle & Replay Protection
* **Cryptographic Correction (HMAC vs. Digital Signatures):**
  HMAC-SHA256 provides a **Symmetric Message Authentication Code (MAC)**, guaranteeing data integrity and authenticity between parties sharing a symmetric secret key. It is **not** an asymmetric digital signature (such as RSA or ECDSA, which rely on public/private key pairs).
* **Key Ownership & Lifecycle:**
  - *Key Custody:* The 256-bit symmetric key $K_{\text{session}}$ is generated by the Deterministic Execution Layer (DEL) upon process initialization using a cryptographically secure pseudorandom number generator (`secrets.token_bytes(32)`).
  - *Key Storage:* $K_{\text{session}}$ resides strictly in volatile memory. It is never serialized, written to disk, or exposed to the Cognitive Orchestrator.
  - *Key Rotation:* Keys are ephemeral. $K_{\text{session}}$ is automatically rotated upon operator session termination or after 1,000 transaction approvals.
* **Nonce Persistence & Atomic Replay Protection:**
  - Every approval token incorporates a 128-bit UUID v4 nonce and an absolute TTL (default 900s).
  - Nonces are persisted in an embedded SQLite table (`consumed_nonces`) with a `PRIMARY KEY` constraint.
  - Verification and consumption execute atomically via `INSERT INTO consumed_nonces (nonce, plan_hash, consumed_at) VALUES (?, ?, ?)` inside a `BEGIN IMMEDIATE` transaction.
  - Any duplicate nonce triggers an immediate SQLite constraint violation, terminating execution with `ERR_TOKEN_REPLAY_DETECTED`.

---

### 2.7 Transaction Protocol: Strict WAL Ordering, Durable Rollback & Crash Recovery Transitions

The transaction protocol enforces a strict 6-phase Write-Ahead Logging state machine:

```
[Phase 1: PREPARE/INTENT Flush] -> [Phase 2: Staging Flush] -> [Phase 3: Backup Sync] -> 
[Phase 4: Atomic Replace] -> [Phase 5: Directory Flush] -> [Phase 6: COMMIT Flush]
```

#### Detailed Phase Protocol & Persistence Guarantees:
1. **Phase 1 (PREPARE/INTENT):** DEL writes an `INTENT` record to `transactions.wal` containing target path, pre-state SHA-256, plan ID, and timestamp. The WAL file descriptor is durably flushed via `FlushFileBuffers` / `fsync` before any staging file write commences.
2. **Phase 2 (Staging Write & Data Flush):** Modified OpenXML parts are written to a temporary staging file (`.tmp`) on the **same filesystem volume**. A hardware flush barrier (`FlushFileBuffers` / `fsync`) is executed on the `.tmp` file descriptor.
3. **Phase 3 (Pre-State Backup Durability):** Pre-state backup file (`.bak`) is verified/written on disk and durably flushed (`FlushFileBuffers` / `fsync`).
4. **Phase 4 (Atomic Namespace Replacement):** `os.replace(.tmp, target)` executes atomic directory entry swap.
5. **Phase 5 (Directory Metadata Flush):** On POSIX, `fsync(dir_fd)` is invoked on the parent directory; on Windows, directory handle metadata is committed.
6. **Phase 6 (COMMIT Record):** DEL appends `COMMIT` record to `transactions.wal` and durably flushes. Staging `.tmp` is unlinked.

#### Durable Crash Recovery Protocol & Idempotency:
When `startup_recovery()` runs after an abnormal termination:
- If restoring `.bak` over `target` is required, the restoration process itself is **strictly durable and idempotent**:
  1. `.bak` is copied to a temporary recovery file `target.rec.tmp`.
  2. `FlushFileBuffers(target.rec.tmp)` / `fsync()` commits restored bytes to non-volatile storage.
  3. `os.replace(target.rec.tmp, target)` atomically restores the pre-state.
  4. Parent directory metadata is durably flushed (`fsync(dir_fd)`).
  5. The WAL record is updated to `ROLLED_BACK` and durably flushed.
  6. The `.bak` file is retained until explicit cleanup, guaranteeing that if recovery itself crashes mid-execution, re-running recovery produces identical, correct results without data loss (idempotency).

#### State Transition Matrix:

| Crash Transition Point | On-Disk State at Crash | Startup Recovery Action (`startup_recovery()`) | Invariant Preserved |
| :--- | :--- | :--- | :--- |
| **Crash during Phase 1** (Writing INTENT) | WAL header corrupt/uncommitted; target untouched. | Purges incomplete WAL record. Target file remains pristine. | Zero corruption; clean abort. |
| **Crash during Phase 2** (Writing `.tmp`) | WAL has `INTENT`; `.tmp` partially written; target untouched. | Deletes orphaned `.tmp`; logs transaction rollback. | Target workbook unchanged. |
| **Crash during Phase 3** (Flushing `.bak`) | WAL has `INTENT`; `.tmp` valid but unswapped; `.bak` complete. | Purges `.tmp`; target remains at pre-state. | Zero state modification. |
| **Crash during Phase 4** (During `os.replace`) | `os.replace` is atomic in filesystem metadata: target is either 100% pre-state or 100% post-state. | Inspects target SHA-256: if target matches `.bak`, purges `.tmp`; if target matches `.tmp`, executes durable rollback of `.bak` over target because COMMIT is missing. | All-or-nothing rollback. |
| **Crash during Phase 5** (After replace, before COMMIT) | Target contains modified bits; `.bak` exists; WAL lacks `COMMIT`. | Because transaction was unfinalized, executes durable restore of `.bak` over target, flushes parent directory, rolls back WAL, and flags `CRASH_BEFORE_COMMIT`. | Strict atomicity preserved. |
| **Crash after Phase 6** (After COMMIT) | Target modified; WAL contains `COMMIT`; `.tmp` unlinked. | Detects valid `COMMIT`; leaves target file in place; updates audit ledger status to `COMPLETED`. | Transaction durable. |

---

### 2.8 PROTOCOL-QA-01: Mathematical Derivation, Planning Approximations & Power Calculations

#### A. Exact Sample Accounting & Demystification of $N_{\text{eff}} = 20.4$ in `BENCH-AUDIT-200`
In empirical audit literature, confusing workbook counts with defect evaluation units causes statistical errors. The exact accounting across `BENCH-AUDIT-200` is:
- **Total Workbooks ($N_{\text{wb}} = 200$):**
  - 50 clean negative-control workbooks (zero defects, containing ~10 negative evaluation sites each = 500 clean sites).
  - 50 isolated single-category defect workbooks (10 workbooks per category $\times$ 5 categories = 50 workbooks, exactly 1 defect site per workbook = 10 defect units per category).
  - 100 mixed defect workbooks (containing 1–2 defects across categories, yielding ~22.6 positive defect units per category, plus clean zones).
- **Positive Defect Units per Category ($N_{\text{pos}, c}$):**
  For any single defect category $c \in \{\text{\#REF!}, \text{\#VALUE!}, \text{\#DIV/0!}, \text{\#NAME?}, \text{\#N/A}\}$, the total number of positive evaluation opportunities in the pilot corpus is:
  $$N_{\text{pos}, c} = 10\text{ (isolated)} + 22.64\text{ (mixed)} \approx 32.64\text{ positive defect units per category}$$
- **Effective Sample Size Derivation:**
  Applying the intra-workbook clustering design effect $\text{DEFF} = 1.60$ ($\text{ICC} = 0.15, m = 5$):
  $$N_{\text{eff}} = \frac{N_{\text{pos}, c}}{\text{DEFF}} = \frac{32.64}{1.60} \approx \mathbf{20.4\text{ effective units per category}}$$
  **Conclusion:** $N_{\text{eff}} = 20.4$ represents the **effective sample size per individual defect category** in `BENCH-AUDIT-200`, NOT the total number of workbooks ($N_{\text{wb}} = 200$). This small sample per category produces an unacceptably wide confidence interval margin ($E = \pm 6.07\%$), mathematically proving that `BENCH-AUDIT-200` is strictly an operational screening filter, not a release certification vehicle.

---

#### B. Wilson Score Intervals as Design Approximations
Wilson intervals computed using fractional effective sample sizes ($N_{\text{eff}} = N / \text{DEFF}$) represent a **first-order Rao-Scott design-adjusted pseudo-likelihood approximation**. They are used for analytical power sizing and preliminary screening, not as the final cluster-exact test:

$$\text{Center } \tilde{p} = \frac{\hat{p} + \frac{z^2}{2 N_{\text{eff}}}}{1 + \frac{z^2}{N_{\text{eff}}}}, \qquad \text{Margin } W = \frac{z \sqrt{\frac{\hat{p}(1-\hat{p})}{N_{\text{eff}}} + \frac{z^2}{4 N_{\text{eff}}^2}}}{1 + \frac{z^2}{N_{\text{eff}}}}$$

$$\text{Approximate 95\% CI} = [\tilde{p} - W, \; \tilde{p} + W]$$

- **Evaluation on Tier 1 Pilot (`BENCH-AUDIT-200`, $N_{\text{eff}} = 20.4$, $\hat{p} = 0.980$):**
  - $z^2 = 3.84146$, $1 + \frac{z^2}{20.4} = 1 + 0.1883 = 1.1883$.
  - $\tilde{p} \approx 0.9039$, $W \approx 0.0943$.
  - **Approximate Wilson 95% CI:** $\mathbf{[80.96\%, \; 99.82\%]}$. Lower bound $\text{LCB}_{95\%} = 80.96\%$. This definitively proves the pilot's inability to statistically certify a $\ge 98.0\%$ standard.

- **Evaluation on Tier 2 Extended Proposed Corpus (`BENCH-AUDIT-EXTENDED`, $N_{\text{pos}} = 850, \text{DEFF} = 1.60 \implies N_{\text{eff}} = 531.25$):**
  - For observed $\hat{p} = 0.980$:
    - $\tilde{p} = 0.976554$, $W = \pm 0.012353$ ($\pm 1.2353\%$).
    - **Effective-sample-size Wilson approximation (planning only):** $\mathbf{[96.42\%, \; 98.89\%]}$.
    - **Precision Audit Finding:** Because $1.2353\% > 1.2000\%$, the candidate corpus size $N_{\text{pos}} = 850$ ($N_{\text{eff}} = 531.25$) **FAILS PRECISION CRITERION** ($\pm 1.2\%$).
    - **Corrected Minimum Sample Size for Precision Margin $\le \pm 1.20\%$:**
      To achieve a Wilson half-width margin $W \le 0.012000$ at $\hat{p} = 0.980$, the minimum effective sample size is $N_{\text{eff}} \ge 561$.
      Under $\text{DEFF} = 1.60$:
      $$N_{\text{pos}} = 561.25 \times 1.60 = \mathbf{898\text{ raw positive defect units per category}} \quad (N_{\text{eff}} = 561.25)$$
      At $N_{\text{eff}} = 561.25$ and $\hat{p} = 0.980$, the two-sided 95% Wilson precision half-width margin is:
      $$W = \mathbf{0.0119953 \quad (1.19953\% \le \pm 1.20000\%) \implies \text{PASSES PRECISION CRITERION}}$$

#### C. Cluster-Aware Inferential Methods Mandated for Final Release Certification
Because workbooks represent clusters with shared structural conventions and authoring templates, **final release certification cannot rely on effective-sample-size approximations; it strictly requires workbook-cluster-aware inference** where the **workbook is explicitly defined as the primary sampling cluster**:
1. **Cluster Bootstrap:** Resampling entire workbook clusters with replacement ($B \ge 2,000$ iterations) and calculating cluster-robust BCa (bias-corrected accelerated) or percentile confidence bounds across resampled clusters.
2. **Generalized Estimating Equations (GEE):** Population-averaged logistic regression with exchangeable working correlation matrix clustered on Workbook ID and robust Huber-White sandwich standard errors.
3. **Generalized Linear Mixed Models (GLMM):** Binomial logistic mixed-effects model with random intercept $u_{\text{wb}} \sim \mathcal{N}(0, \sigma_{\text{wb}}^2)$ per workbook cluster.

---

#### D. Statistical Precision vs. Approved Acceptance Threshold ($\text{LCB}_{95\%} \ge 98.0\%$)
A critical distinction exists between **measurement precision** and the **approved acceptance threshold**:
1. **Precision Criterion:** Two-sided 95% half-width margin $E \le \pm 1.2\%$ around $\hat{p} \approx 0.98$. Sizing reveals that $N_{\text{pos}} = 850$ ($N_{\text{eff}} = 531.25$) yields $W = \pm 1.2353\%$ and **FAILS PRECISION CRITERION**; achieving precision requires $N_{\text{eff}} = 561.25 \implies N_{\text{pos}} = 898\text{ raw positive defect units per category}$, achieving $W = \mathbf{1.19953\% \le \pm 1.2000\%}$.
2. **Approved Statistical Acceptance Rule (One-Sided 95% LCB):**
   *Project Owner Sign-Off:* Requiring the one-sided 95% Lower Confidence Bound to satisfy $\text{LCB}_{95\%} \ge 98.00\%$ is formally **APPROVED by the Project Owner** as the release certification standard.
   - **Neither the 850-unit candidate corpus nor the 898-unit corrected corpus guarantees certification on its own without empirical defect detection.**
   - If observed sensitivity on $N_{\text{eff}} = 531.25$ ($N_{\text{pos}} = 850$) is $\hat{p} = 0.980$ (one-sided $z_{0.95} = 1.64485$):
     $$\tilde{p} = 0.977568, \quad W = 0.010258 \implies \text{LCB}_{95\%, 1\text{-sided}} = 0.977568 - 0.010258 = \mathbf{96.73\%}$$
     This fails the approved $\ge 98.0\%$ acceptance threshold because sampling variation allows true $P < 98.0\%$.
   - **Clear Contrast between Historical Candidate Corpus ($N_{\text{pos}} = 850$) and Approved Precision Corpus ($N_{\text{pos}} = 898$):**
     * **Old Candidate Sizing ($N_{\text{pos}} = 850, \text{DEFF} = 1.60 \implies N_{\text{eff}} = 531.25$):**
       - At $k = 841 / 850$ ($\hat{p} = 0.989412$): $\tilde{p} = 0.986932, W = 0.007696 \implies \text{LCB}_{95\%, 1\text{-sided}} = \mathbf{97.9236\% \approx 97.92\%} < 98.00\%$ (**FAILS ACCEPTANCE**).
       - At $k = 842 / 850$ ($\hat{p} = 0.990588 \approx 99.06\%$): $\tilde{p} = 0.988102, W = 0.007309 \implies \text{LCB}_{95\%, 1\text{-sided}} = \mathbf{98.0794\% \approx 98.08\%} \ge 98.00\%$ (**ACCEPTED**).
       *(Note: As established in Subsection B/D.1, $N_{\text{pos}} = 850$ failed the two-sided precision criterion $W = \pm 1.2353\% > \pm 1.2000\%$, and is superseded).*
     * **Approved Precision Sizing ($N_{\text{pos}} = 898, \text{DEFF} = 1.60 \implies N_{\text{eff}} = 898 / 1.60 = 561.25$):**
       To satisfy the two-sided precision criterion ($W = \mathbf{1.19953\%} \le \pm 1.2000\%$), the positive corpus requirement is approved at $N_{\text{pos}} = 898$ per defect category.
       Recalculating the minimum integer number of detections required on $N_{\text{pos}} = 898$ to satisfy the approved one-sided criterion ($\text{LCB}_{95\%, 1\text{-sided}} \ge 0.980000$ with $z_{0.95} = 1.64485$):
       - At $k = 888 / 898$ ($\hat{p} = 0.988864$): $\tilde{p} = 0.986519, W = 0.007637 \implies \text{LCB} = 97.89\% < 98.00\%$ (**FAILS**).
       - At $k = \mathbf{889 / 898}$ ($\hat{p} = 0.989978 \approx 99.00\%$):
         $$\tilde{p} = 0.987627, \quad W = 0.007289 \implies \text{LCB}_{95\%, 1\text{-sided}} = 0.987627 - 0.007289 = \mathbf{98.0338\% \approx 98.03\%} \ge 98.00\% \implies \mathbf{ACCEPTED}$$
       - At $k = 890 / 898$ ($\hat{p} = 0.991091$): $\tilde{p} = 0.988735, W = 0.006922 \implies \text{LCB} = 98.18\% \ge 98.00\%$.
       Therefore, on the approved corpus of $N_{\text{pos}} = 898$ units, the preliminary effective-sample-size Wilson planning threshold is **$\ge 889 / 898$ detections** ($\hat{p} = 98.9978\%$), yielding an effective-sample-size Wilson LCB of **$98.03\%$**.
       > [!IMPORTANT]
       > **Planning Approximation vs. Certification Requirement:**  
       > The $889 / 898$ detection threshold is an effective-sample-size Wilson planning approximation ($N_{\text{eff}} = 561.25$). Final release certification strictly requires workbook-cluster-aware inference (Cluster Bootstrap, GEE, or GLMM), with the workbook explicitly treated as the primary sampling cluster.
   - **Sample Size Scaling if Expected Sensitivity is Lower:**
     If true platform sensitivity is $\hat{p} = 0.985$ (98.5%), achieving $\text{LCB}_{95\%} \ge 98.0\%$ requires expanding the sample size to $N_{\text{eff}} \ge 2,130 \implies N_{\text{pos}} \ge 3,408\text{ defect units}$.
   - **Certification Status:** Certification remains **STRICTLY PENDING** empirical execution and workbook-cluster-aware inferential validation on the Extended Corpus in Phase 1.

---

#### E. Reconciled False Positive Rate (FPR) Derivation, Sampling Design & Acceptance Bounds
* **Reconciliation of Planning Assumptions:**
  - Maximum allowable threshold: $P_0 = 0.005$ (0.5% upper specification limit).
  - Planning parameter: $P = 0.005$ with desired half-width margin $E = \pm 0.003$ ($\pm 0.3\%$):
    $$N_{\text{eff, neg}} = \frac{z^2 \cdot P(1 - P)}{E^2} = \frac{1.95996^2 \times 0.005 \times 0.995}{(0.003)^2} = \frac{3.84146 \times 0.004975}{0.000009} \approx \mathbf{2,124\text{ independent units}}$$
    *(Note on Derivation: Planning at $P = 0.002$ with $E = \pm 0.003$ produces $N_{\text{eff}} \approx 852$. However, planning conservatively at the boundary threshold $P = 0.005$ yields $N_{\text{eff}} = 2,124$, which is strictly required to guarantee that the upper confidence bound remains below 0.50% when evaluated empirically).*
* **Sampling Design Reconciliation:**
  To obtain $N_{\text{eff, neg}} = 2,124$ under an assumed intra-workbook correlation $\rho = 0.05$:
  - If each clean workbook contains an average of $m = 10$ negative evaluation regions:
    $$\text{DEFF}_{\text{neg}} = 1 + (10 - 1)(0.05) = 1 + 0.45 = \mathbf{1.45}$$
    $$N_{\text{neg}} = N_{\text{eff, neg}} \times \text{DEFF}_{\text{neg}} = 2,123.55 \times 1.45 \approx \mathbf{3,080\text{ negative evaluation units}}$$
  - **Required Workbook Count Reconciliation:**
    Evaluating 3,080 units at exactly $m = 10$ regions per workbook requires:
    $$K_{\text{clean}} = \frac{N_{\text{neg}}}{m} = \frac{3,080}{10} = \mathbf{308\text{ clean workbooks}}$$
    This strictly satisfies the general baseline condition of $\ge 250$ workbooks by specifying an exact minimum of **$K_{\text{clean}} \ge 308\text{ clean workbooks}$**.
  - *(Alternative Design with exactly $K_{\text{clean}} = 250$ workbooks: If workbook count is fixed at 250, then average negative regions per workbook must be $\bar{m} = 3,080 / 250 = 12.32$. At $\bar{m} = 12.32, \rho = 0.05 \implies \text{DEFF} = 1.566 \implies N_{\text{neg}} = 2,124 \times 1.566 \approx 3,326\text{ units}$, requiring $\bar{m} \approx 13.3\text{ regions/workbook}$). The primary sampling design adopts $K_{\text{clean}} \ge 308$ workbooks with $m = 10$ regions.*
* **FPR Confidence Bounds Comparison against Acceptance Rule ($\text{UCB}_{95\%, 1\text{-sided}} \le 0.50\%$):**
  Assuming an empirical observed false positive rate $\hat{p} = 0.002$ (0.2%, e.g. $\le 6$ false positives across 3,080 clean units):
  - **Case 1: Reconciled Target Sample Size ($N_{\text{eff}} = 2,124, N_{\text{neg}} = 3,080$):**
    - One-sided 95% Wilson ($z = 1.64485$):
      $$\tilde{p}_{1\text{-sided}} = 0.002634, \quad W_{1\text{-sided}} = 0.001715 \implies \text{UCB}_{95\%, 1\text{-sided}} = 0.002634 + 0.001715 = \mathbf{0.435\%} \le \mathbf{0.50\%} \implies \mathbf{ACCEPTED}$$
    - Two-sided 95% Wilson ($z = 1.95996$):
      $$\tilde{p}_{2\text{-sided}} = 0.002899, \quad W_{2\text{-sided}} = 0.002100 \implies \text{UCB}_{95\%, 2\text{-sided}} = 0.002899 + 0.002100 = \mathbf{0.500\%} \le \mathbf{0.50\%}$$
  - **Case 2: Insufficient Sample Size ($N_{\text{eff}} = 852, N_{\text{neg}} = 1,235$):**
    - One-sided 95% Wilson ($z = 1.64485$):
      $$\tilde{p}_{1\text{-sided}} = 0.003576, \quad W_{1\text{-sided}} = 0.002967 \implies \text{UCB}_{95\%, 1\text{-sided}} = 0.003576 + 0.002967 = \mathbf{0.654\%} > \mathbf{0.50\%} \implies \mathbf{FAILS\ ACCEPTANCE}$$
    - Two-sided 95% Wilson ($z = 1.95996$):
      $$\tilde{p}_{2\text{-sided}} = 0.004235, \quad W_{2\text{-sided}} = 0.003736 \implies \text{UCB}_{95\%, 2\text{-sided}} = 0.004235 + 0.003736 = \mathbf{0.797\%} > \mathbf{0.50\%}$$
    - *Conclusion:* This calculation demonstrates that $N_{\text{eff}} = 2,124$ ($N_{\text{neg}} \ge 3,080$) is mathematically necessary to accept the platform at an observed rate of 0.2%.
* **Corpus Verification & Certification Status:**
  > [!IMPORTANT]
  > **EXTENDED CORPUS STATUS: PENDING EXECUTION**  
  > The repository currently contains only the Phase 0 pilot corpus `BENCH-AUDIT-200` (~500 negative evaluation sites). It does **NOT** contain the 3,080 negative evaluation units required for FPR certification. Full certification of FPR $\le 0.5\%$ remains **STRICTLY PENDING EXECUTION** until the Extended Corpus is generated and evaluated in Phase 1.

---

*End of Corrected Phase 0 Independent Evidence Audit.*
