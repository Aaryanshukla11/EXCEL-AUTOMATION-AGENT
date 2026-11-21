# Autonomous Excel Intelligence Platform
## Technical Experiment Register

**Document Type:** Formal Engineering Experiment Register  
**Document Version:** 2.6-Reconciled-Draft  
**Document Status:** DRAFT — Subject to Project-Owner Review  
**Implementation Authorization:** STRICTLY NOT GRANTED  
**Objective:** Maintain strict empiricism. No technology stack, library, or architectural mechanism may be adopted without validated experimental evidence.

---

## 1. Experiment Overview & Governance

This register defines nine mandatory technical spikes (EXP-01 through EXP-09) and the dedicated Quality Audit Validation Protocol (`PROTOCOL-QA-01`) required to resolve technical uncertainties prior to final architectural selection. Every experiment adheres to an 8-part scientific protocol.

### 1.1 Standardized Experimental Benchmark Environment
To guarantee reproducibility across all experiments, all benchmark tests must run under controlled baseline conditions:
- **Hardware Specification:** 8-core x86_64 CPU (minimum 3.2 GHz base clock), 16 GB DDR4/DDR5 RAM, dedicated NVMe PCIe 4.0 SSD storage.
- **Operating Systems Tested:**
  1. Windows 11 Enterprise (NTFS filesystem, active OneDrive synchronization client installed).
  2. Ubuntu 22.04 LTS (ext4 filesystem, Linux kernel 5.15+).
- **Runtime Environment:** Python 3.11.x and 3.12.x 64-bit; Rust toolchain 1.75+ (for Rust candidates).
- **Repetition Protocol:** Minimum 10 cold runs (fresh OS process, cleared file system disk cache) followed by 10 warm runs per test scenario.
- **Statistical Reporting:** Report median, p95, p99, and standard deviation. Outliers beyond 3 standard deviations must be flagged and investigated.
- **Test Corpus Specification:** Standardized benchmark suites:
  - `BENCH-FIDELITY-01`: OpenXML part preservation test workbook.
  - `BENCH-SCALE-100K`: Massive 100k-row single-sheet streaming memory benchmark.
  - `BENCH-PERF-MULTI-5`: Multi-workbook consolidation benchmark (5 source workbooks up to 20,000 rows each + Master) to verify V1.2 NFR-03 latency ($\le 60$s) and relative memory ($\le 4\times$ uncompressed OpenXML sheet size).
  - `BENCH-AUDIT-200`: Initial 200-workbook quality audit acceptance gate pilot corpus.
  - `BENCH-AUDIT-EXTENDED`: Large-scale statistical validation corpus ($\ge 1,000$ workbooks) for high-precision audit verification.
  - `BENCH-CONSOL-20`: 20-task cognitive architecture exploratory pilot.
  - `BENCH-COGNITIVE-100`: 100-task repeated-measures formal cognitive benchmark.

### 1.2 Dedicated Static Quality Audit Validation Protocol (`PROTOCOL-QA-01`)
*Milestone Alignment: Curated in Phase 0; formally executed as the Phase 1 (Release 1.0) Acceptance & Quality Gate Verification Activity.*  
*Scope Clarification: Technical Spikes EXP-04 (dynamic formula AST limits) and EXP-07 (shadow dry-run plan validation) validate formula AST boundaries and plan preconditions, but do NOT substitute for this dedicated protocol.*

- **Protocol Objective:** Statistically validate the Release 1.0 Static Structural & Quality Auditing Engine across all five defect categories with verifiable sensitivity, false-positive rate, and confidence bounds.
- **Exact Evaluation Units & Category-Specific Denominators:**
  To eliminate denominator ambiguity, each defect category evaluates an explicit, well-defined structural unit:
  1. *Category 1 (Formula Evaluation Errors):*
     - Evaluation Unit: Formula Cell.
     - Positive Denominator ($N_{\text{pos}, 1} = TP_1 + FN_1$): Total count of formula cells containing genuine `#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, or `#N/A` errors.
     - Negative Denominator ($N_{\text{neg}, 1} = TN_1 + FP_1$): Total count of valid, error-free formula cells evaluated.
  2. *Category 2 (Circular References):*
     - Evaluation Unit: Formula Dependency Component / Participating Cell.
     - Positive Denominator ($N_{\text{pos}, 2} = TP_2 + FN_2$): Total count of formula cells participating in genuine circular reference loops (restricted to statically resolvable formulas).
     - Negative Denominator ($N_{\text{neg}, 2} = TN_2 + FP_2$): Total count of formula cells participating in acyclic calculation chains.
  3. *Category 3 (Jagged Rows):*
     - Evaluation Unit: Table Row.
     - Positive Denominator ($N_{\text{pos}, 3} = TP_3 + FN_3$): Total count of rows whose populated cell span diverges from the declared or inferred table column boundary.
     - Negative Denominator ($N_{\text{neg}, 3} = TN_3 + FP_3$): Total count of conforming rectangular table rows.
  4. *Category 4 (Unmapped Source Fields):*
     - Evaluation Unit: Source Column (per Source-Master consolidation pair).
     - Positive Denominator ($N_{\text{pos}, 4} = TP_4 + FN_4$): Total count of source columns that have no valid destination in the target Master table schema.
     - Negative Denominator ($N_{\text{neg}, 4} = TN_4 + FP_4$): Total count of source columns that map legitimately to existing Master columns.
  5. *Category 5 (Candidate Key Collisions):*
     - Evaluation Unit: Candidate Record / Key Group (evaluated pairwise).
     - Positive Denominator ($N_{\text{pos}, 5} = TP_5 + FN_5$): Total count of record pairs possessing matching primary candidate keys but conflicting/divergent non-key attribute values.
     - Negative Denominator ($N_{\text{neg}, 5} = TN_5 + FP_5$): Total count of record pairs that are either uniquely distinct or perfectly identical duplicates.

- **Intra-Workbook Correlation & Clustered Statistical Methodology:**
  - *The Clustered Data Problem:* Cells, rows, and columns within the same workbook share generator characteristics, layout styles, and semantic domains; they do **not** represent independent identically distributed (i.i.d.) observations. Naive pooling of cells across workbooks drastically artificially inflates the effective sample size, underestimates standard errors, and invalidates standard binomial confidence intervals (such as standard Wilson score intervals).
  - *Clustering-Aware Evaluation:*
    - The workbook is treated as the primary sampling unit (cluster).
    - Statistical inference must utilize **Cluster-Robust Standard Errors** or **Cluster Bootstrap Resampling** ($B=2,000$ resamples at the workbook level), or Generalized Linear Mixed Models (GLMM) with workbook-level random intercepts:
      $$\text{logit}(P(\text{Detection}_{ij} = 1)) = \alpha + u_{\text{Workbook}, i}, \quad u_{\text{Workbook}, i} \sim \mathcal{N}(0, \sigma_u^2)$$
    - Sensitivity (Recall) and False Positive Rate (FPR) must be reported as cluster-adjusted estimates with 95% cluster-bootstrap confidence intervals.

- **Corpus Sizing & Statistical Reassessment (`BENCH-AUDIT-200` vs. `BENCH-AUDIT-EXTENDED`):**
  - *Mathematical Corpus Sizing Analysis:* To demonstrate a Sensitivity $\ge 98.0\%$ with a margin of error $E \le \pm 1.2\%$ at 95% confidence ($\alpha = 0.05, z = 1.96$), elementary sample size calculation for an unclustered proportion requires:
    $$N_{\text{pos}, \text{eff}} \ge \frac{z^2 \cdot p(1-p)}{E^2} = \frac{1.96^2 \cdot 0.98 \cdot 0.02}{0.012^2} \approx 523 \text{ independent positive units}$$
    Accounting for clustering with an estimated intraclass correlation coefficient $\rho \approx 0.15$ and an average of $m \approx 5$ defect units per positive workbook, the Design Effect is:
    $$DEFF = 1 + (m-1)\rho = 1 + (5-1)(0.15) = 1.6$$
    The required total positive units per defect category is $N_{\text{pos}} \ge 523 \times 1.6 \approx 837$ units, requiring $\ge 150-250$ positive workbooks per category!
  - *Designation of Benchmark Tiers:*
    1. **`BENCH-AUDIT-200` (Phase 1 Acceptance Gate Pilot Corpus):**
       - 100 Clean Negative Controls (0 defects; evaluates false positives across clean sheets).
       - 50 Isolated Positive Defects (10 fixtures per category; provides initial functional verification).
       - 50 Mixed Realistic Workbooks (interleaved defects; tests boundary disambiguation).
       - *Role:* Serves as the mandatory **Phase 1 Acceptance Gate Pilot**, providing initial operational screening. However, its small positive count per category (~20–35 defect units) yields wider confidence intervals ($E \approx \pm 4.5\%$) and cannot mathematically guarantee $\le \pm 1.2\%$ margin of error.
    2. **`BENCH-AUDIT-EXTENDED` (Large-Scale Statistical Corpus):**
       - $\ge 1,000$ workbooks total ($\ge 500$ clean negative controls, $\ge 250$ positive fixtures per category, $\ge 850$ positive defect units per category, mathematically satisfying the $N_{\text{pos}} \ge 837$ clustered sample size requirement).
       - *Role:* Required to formally achieve definitive statistical validation of $\ge 98.0\%$ Sensitivity and $\le 1.0\%$ FPR with $\le \pm 1.2\%$ confidence margins under clustered conditions. Curated during Phase 1 for long-term platform certification.

```
+==================================================================================================================================+
|                                              TECHNICAL EXPERIMENT SPIKE MATRIX                                                   |
+==================================================================================================================================+
| Spike ID | Technical Uncertainty Domain                 | Focus Technology / Candidates                            | Status      |
+----------+----------------------------------------------+----------------------------------------------------------+-------------+
| EXP-01   | OpenXML Part Preservation & Engine Fidelity  | Python DOM vs. Rust quick-xml vs. Custom Python Archive  | PROPOSED    |
|          |                                              | Part-Patcher (using et_xmlfile strictly as serializer)   |             |
| EXP-02   | Streaming Ingestion & Process Memory Scaling | openpyxl DOM vs. openpyxl read_only vs. defusedxml.      | PROPOSED    |
|          |                                              | iterparse vs. Rust calamine streaming via PyO3           |             |
| EXP-03   | Formula Recalculation & Headless Value Cache | fullCalcOnLoad vs. Headless Engines (pycel / formulas)   | PROPOSED    |
| EXP-04   | Dynamic & Volatile Formula Dependencies      | Static EBNF Lexer on INDIRECT, OFFSET, and array spills  | PROPOSED    |
| EXP-05   | Format Compatibility & Opaque VBA Stream     | XLSX vs. XLSM (opaque VBA binary stream preservation)    | PROPOSED    |
|          | Preservation (Macro Execution Unsupported)   | vs. XLSB (read-only limits; pending empirical proof)     |             |
| EXP-06   | Storage & Transaction Guarantees             | Local NTFS/APFS vs. SMB Shares vs. OneDrive Sync Folders | PROPOSED    |
| EXP-07   | Operation-Plan Validation & Pre/Post Checks  | Shadow Dry-Run Simulator & AST Invariant Diff Verifier   | PROPOSED    |
| EXP-08   | Scoped Approval Token Security Lifecycle     | HMAC-SHA256 Token Lifecycle (TTL, Replay Nonce, Scoping, | PROPOSED    |
|          |                                              | Concurrent Replay, Revocation, Approver Identity)        |             |
| EXP-09   | Cognitive Architecture Topology Benchmarks   | 8-Agent Swarm vs. 4-Subsystem vs. Tool-Calling Model     | PROPOSED    |
|          |                                              | (Pilot Bench + LMM Repeated-Measures Statistical Bench)  |             |
+==================================================================================================================================+
```

---

## 2. Detailed 8-Part Experiment Protocols

### EXP-01: OpenXML Part Preservation & Engine Fidelity
1. **Objective:** Evaluate and compare OpenXML part preservation fidelity and table mutation capabilities between Python-based and Rust-based spreadsheet manipulation libraries.
2. **Hypothesis:** Python `openpyxl` handles basic table expansion but strips or corrupts dynamic array formula spill tags, slicers, and advanced chart formatting during DOM re-serialization. A custom archive part-patcher or Rust-based engine preserves 100% of non-targeted parts by avoiding full-tree re-serialization.
3. **Candidates:**
   - Candidate A: Enhanced Python DOM (`openpyxl` 3.1+ with `defusedxml`).
   - Candidate B: Rust OpenXML Core (`quick-xml` + `zip` with PyO3 bindings).
   - Candidate C: Custom Python Archive/Part-Patching Architecture (direct ZIP container extraction/re-assembly targeting only modified worksheet XML and table definitions, using `et_xmlfile` or `defusedxml` strictly as low-level streaming XML serializers, preserving all other ZIP parts byte-for-byte as opaque streams).
4. **Controlled Methodology:**
   - Fixture: `BENCH-FIDELITY-01.xlsm` containing an Excel `ListObject`, dynamic array formulas (`=SORT(UNIQUE(...))#`), custom conditional formatting, cell comments, a clustered column chart, a table slicer, and an opaque `vbaProject.bin`.
   - Action: Append 1,000 rows to the `ListObject` table and save.
   - Analysis: Unpack `.zip` archives before and after; perform AST node diffs on all `.xml` and `.rels` parts; open in Microsoft Excel Desktop to check for repair prompts.
5. **Metrics:**
   - OpenXML part preservation rate (% of untouched XML parts remaining identical).
   - Corruption incident rate (count of repair/warning dialogs in Excel Desktop).
   - Table boundary accuracy (correct `<table ref="A1:G1050"/>` and `<autoFilter>` update).
6. **Success Criteria:** 100% preservation of charts, slicers, dynamic array spills, and VBA streams; zero repair warnings in Excel Desktop.
7. **Failure Criteria:** Stripping of drawing parts, corruption of slicers, or invalidation of table filters.
8. **Evidence Required for a Decision:** Side-by-side diff matrix comparing Candidate A, B, and C on part preservation and serialization latency.

---

### EXP-02: Streaming Ingestion & Process Memory Scaling
1. **Objective:** Measure process-level memory footprint (Resident Set Size) and parsing speed across streaming vs. DOM architectures, validating both single-sheet streaming scaling (100k rows) and V1.2 multi-workbook profiling constraints.
2. **Hypothesis:** Full DOM parsing of a 50MB (100k rows × 50 cols) workbook exceeds 2GB process RSS; streaming SAX parsing processes the same sheet in <250MB process RSS.
3. **Candidates:**
   - Candidate A: `openpyxl` standard DOM (`load_workbook(read_only=False)`).
   - Candidate B: `openpyxl` streaming reader (`load_workbook(read_only=True)`).
   - Candidate C: Python streaming SAX via `defusedxml.iterparse` / `et_xmlfile`.
   - Candidate D: Rust `calamine` streaming parser via PyO3 bindings.
4. **Controlled Methodology:**
   - Two standardized benchmark corpora:
     1. Single-sheet massive grid: `BENCH-SCALE-100K` (100,000 rows × 50 columns sparse grid).
     2. Multi-workbook profiling: `BENCH-PERF-MULTI-5` (5 source workbooks up to 20,000 rows each + Master workbook, evaluating V1.2 NFR-03: profiling $\le 60$s, memory $\le 4\times$ uncompressed sheet size).
   - Execute extraction of cell coordinates, basic data types, and bounding-box coordinates under standardized benchmark conditions (§1.1).
   - Measure actual OS process-level Resident Set Size (RSS) using OS process sampling (`psutil.Process().memory_info().rss`), supplemented by Python `tracemalloc` for heap breakdown.
5. **Metrics:** Peak process Resident Set Size (RSS) in MB; wall-clock parsing latency (seconds); relative memory ratio (RAM / uncompressed sheet size).
6. **Success Criteria:**
   - `BENCH-SCALE-100K`: 100k rows parsed in <15 seconds with peak process RSS <250MB.
   - `BENCH-PERF-MULTI-5`: 5 source workbooks + Master profiled in $\le 60$ seconds with peak memory $\le 4\times$ uncompressed sheet size.
7. **Failure Criteria:** Process out-of-memory crash (>1.5GB RSS) or execution time >60 seconds on single sheet; failure to complete multi-workbook profiling within 60s.
8. **Evidence Required for a Decision:** Process RSS memory vs. row-count scaling curves and parsing latency benchmarks across Candidates A–D.

---

### EXP-03: Formula Recalculation & Headless Value Cache
1. **Objective:** Determine the operational impact of deferred calculation (`fullCalcOnLoad="1"`) on downstream headless consumers.
2. **Hypothesis:** Downstream headless ETL libraries (pandas, calamine, Apache POI) read the cached `<v>` tag and return `None` or `0` when `<v>` is omitted, proving that `fullCalcOnLoad` is insufficient for headless pipelines.
3. **Candidates:**
   - Candidate A: Pure Deferred Recalculation (write `<f>`, set `fullCalcOnLoad="1"`, omit `<v>`).
   - Candidate B: Hybrid Evaluation using open-source formula engine (e.g., `pycel` or `formulas`) to populate standard `<v>` tags.
   - Candidate C: Headless LibreOffice / Excel COM calculation worker.
4. **Controlled Methodology:**
   - Generate test workbooks containing 20 standard formula types (`SUM`, `AVERAGE`, `IF`, `XLOOKUP`, `INDEX/MATCH`, `CONCATENATE`).
   - Read the generated workbooks using: (1) pandas `read_excel`, (2) Python `calamine`, (3) desktop Excel.
5. **Metrics:** Read accuracy (% of calculated values correctly retrieved by headless readers).
6. **Success Criteria:** Definitive empirical matrix documenting which headless tools fail without cached `<v>` tags, and whether Candidate B accurately computes standard formulas.
7. **Failure Criteria:** Silent zero-value ingestion by downstream headless tools without error warnings.
8. **Evidence Required for a Decision:** Compatibility report across headless readers and computation error rate of Candidate B vs. native Excel.

---

### EXP-04: Dynamic & Volatile Formula Dependencies
1. **Objective:** Identify the failure boundaries of static EBNF formula AST dependency analysis on dynamic and volatile Excel functions.
2. **Hypothesis:** Static formula AST analysis can reliably extract static references (`A1:B10`, `Table1[Col]`), but cannot resolve volatile functions (`INDIRECT`, `OFFSET`) and dynamic array spill ranges (`#`) without runtime evaluation. Such formulas must be classified as `UNRESOLVED_DYNAMIC_DEPENDENCY` and quarantined.
3. **Candidates:** Static EBNF Lexer/Parser with dependency DAG builder.
4. **Controlled Methodology:**
   - Feed 100 formulas containing: static 2D ranges, named ranges, cross-sheet references, structured table references (`Table1[Amount]`), `INDIRECT("Data!" & A1)`, `OFFSET(A1, 1, 0)`, and spill ranges (`SORT(A1:A50)#`).
   - Measure precedent extraction accuracy, static cycle detection, and volatile reference quarantine behavior.
5. **Metrics:** Dependency resolution accuracy (%); static cycle detection rate (%); false circular reference detection rate (%).
6. **Success Criteria:** 100% detection of static precedents and static cycles; 100% correct classification of volatile/dynamic formulas as `UNRESOLVED_DYNAMIC_DEPENDENCY`; zero false cycle errors on valid acyclic dynamic arrays.
7. **Failure Criteria:** Silent omission of a dynamic precedent that results in an unmanaged spatial collision; claiming cycle-detection guarantees on `INDIRECT` strings.
8. **Evidence Required for a Decision:** Formal classification grammar defining safe static vs. unresolvable volatile formula patterns and quarantine policies.

---

### EXP-05: Format Compatibility & Opaque VBA Stream Preservation (Macro Execution Unsupported)
1. **Objective:** Establish verified read/write support boundaries across `.xlsx`, `.xlsm`, and `.xlsb`, focusing on opaque binary stream preservation and workbook integrity without macro execution.
2. **Hypothesis:** `.xlsx` and `.xlsm` support robust read, append, and verification; `.xlsb` is planned for read-only source ingestion via binary tokenizers (e.g. `pyxlsb`, `calamine`), but remains an unverified hypothesis until tested. In `.xlsm`, the opaque `vbaProject.bin` stream and macro relationship references can be preserved with 100% SHA-256 byte parity without executing VBA code. Macro execution is explicitly unsupported.
3. **Candidates:** Python `openpyxl`, `pyxlsb`, and Rust `calamine`.
4. **Controlled Methodology:**
   - Ingest identical tabular models stored in `.xlsx`, `.xlsm`, and `.xlsb`.
   - Attempt row appends, table expansions, and re-saving across `.xlsx` and `.xlsm`.
   - Measure SHA-256 hash of `vbaProject.bin` before and after write.
   - Inspect re-saved `.xlsm` in Microsoft Excel Desktop to confirm zero corruption or repair warnings upon open. Verify relationship `.rels` target integrity.
   - *Macro execution is explicitly omitted from testing and unsupported by the platform.*
5. **Metrics:** File read success rate (%); file write integrity rate (%); `vbaProject.bin` SHA-256 binary parity rate (%); Excel Desktop open corruption warning rate (0 count).
6. **Success Criteria:** 100% read across all three formats; 100% write integrity on `.xlsx` and `.xlsm`; 100% byte-for-byte SHA-256 preservation of `vbaProject.bin`; zero repair or corruption warnings in Microsoft Excel Desktop.
7. **Failure Criteria:** Alteration of `vbaProject.bin` binary hash; corruption of macro relationship parts; silent data truncation in `.xlsb`.
8. **Evidence Required for a Decision:** Format compatibility matrix backed by test logs across 30 test workbooks, resolving the empirical viability of `.xlsb` source ingestion.

---

### EXP-06: Storage & Transaction Guarantees Across Environments
1. **Objective:** Evaluate transaction atomicity, crash durability, file locking, and rollback reliability across local storage, network shares, and cloud-synced folders.
2. **Hypothesis:** Atomic namespace replacement (`os.replace`) combined with explicit file `fsync()`, parent directory metadata flushing, and Write-Ahead Logging (WAL) sequencing guarantees crash-consistent recovery on local NTFS/APFS/ext4 volumes (Established OS Primitives / Integration Pending Verification). However, network file shares (SMB/CIFS) and cloud-synced directories (OneDrive/SharePoint) experience lock contention and lack atomic rename across mount boundaries, requiring lock-aware staging and exponential retry logic (Design Target / Unverified Hypothesis).
3. **Candidates:**
   - Storage Environment 1: Local NVMe drive (NTFS / ext4) — Multi-step atomic swap and durability protocol.
   - Storage Environment 2: SMB / CIFS network file share — Lock-aware staging and staging-swap.
   - Storage Environment 3: Active Microsoft OneDrive / SharePoint local sync folder — Sync-daemon-aware local staging outside sync tree.
4. **Controlled Methodology:**
   - Execute 100 rapid file append transactions with simulated write aborts (SIGKILL and abrupt process termination at each stage of the write sequence: during staging, before fsync, before rename, during rename, before WAL commit).
   - On Environment 3, run transactions while cloud sync daemons actively upload files.
   - Test retry with exponential backoff on file lock exceptions.
   - Execute startup crash recovery protocol to verify rollback to pre-execution backup image.
5. **Metrics:** Atomic namespace replacement success rate (%); crash recovery success rate (% of aborted transactions cleanly restored to pre-state); conflict-copy creation count; lock contention retry rate (%).
6. **Success Criteria:** 100% bitwise recovery on aborted transactions; 0 corrupted or half-written files; 0 conflicted sync copies created on Environment 3.
7. **Failure Criteria:** Unhandled `PermissionError` crash; creation of "Conflicted Copy" files by OneDrive; incomplete file left in directory without automatic recovery.
8. **Evidence Required for a Decision:** Transaction protocol specification defining durability flush ordering, lock retry, and staging strategies for SMB and OneDrive.

---

### EXP-07: Operation-Plan Validation & Pre/Post Checks
1. **Objective:** Validate that an in-memory shadow model can intercept 100% of spatial overlaps, broken formulas, and schema violations before any disk write.
2. **Hypothesis:** Pre-condition checking on SHA-256 hashes and cell coordinate states coupled with shadow dry-run execution prevents 100% of invalid writes.
3. **Candidates:** In-memory shadow model simulator.
4. **Controlled Methodology:**
   - Inject 50 adversarial plans (circular references, invalid `#REF!` coordinates, non-empty cell overwrites without tokens, invalid types).
   - Measure detection rate at the shadow dry-run gate.
5. **Metrics:** Invariant breach detection rate (%); false positive rejection rate (%).
6. **Success Criteria:** 100% of invalid operations intercepted before invoking physical file mutation.
7. **Failure Criteria:** Any invalid operation proceeding to disk persistence.
8. **Evidence Required for a Decision:** Dry-run test harness logs across 50 adversarial test cases.

---

### EXP-08: Scoped Approval Token Security Lifecycle & Concurrency Resistance
1. **Objective:** Prove that HMAC-SHA256 scoped approval tokens prevent replay attacks, concurrent race conditions, unauthorized cell modification, or tampered values.
2. **Hypothesis:** Tokens bound to `{session_id, op_id, record_key, target_cells, approved_values, approver_identity, timestamp, nonce}` with atomic in-memory single-use tracking prevent 100% of replay, concurrent race, and tampering attempts.
3. **Candidates:** Scoped HMAC-SHA256 Token Manager with atomic mutex-protected nonce consumption.
4. **Controlled Methodology:**
   - Generate valid tokens for modifying cell `D45` to `"APPROVED"`.
   - Adversarial tests:
     1. *Concurrent Replay Attack:* Multi-threaded test harness firing 50 concurrent requests simultaneously with the identical token and nonce to verify zero duplicate executions.
     2. *Tampering Attack:* Tamper cell target to `D46` or value to `"MALICIOUS"`.
     3. *Approver Role Attack:* Execute token with an identity/role differing from the token's bound `approver_identity`.
     4. *TTL Expiry Attack:* Present token after 15-minute TTL has elapsed.
     5. *Session Invalidation:* Terminate session and verify that all previously unconsumed tokens are immediately rejected via the Revocation Blacklist.
5. **Metrics:** Concurrent race interception rate (%); tampering interception rate (%); expired token rejection rate (%).
6. **Success Criteria:** Exactly 1 execution succeeds in concurrent replay; 49 race attempts rejected; 100% of tampered, unauthorized, expired, or revoked tokens rejected.
7. **Failure Criteria:** More than 1 successful write in concurrent replay; acceptance of any modified token payload or replayed nonce.
8. **Evidence Required for a Decision:** Multi-threaded cryptographic security test harness report.

---

### EXP-09: Cognitive Architecture Topology Comparative Benchmarks & Statistical Methodology
1. **Objective:** Comprehensively compare token latency, execution cost, serialization error rates, and mapping accuracy across the three competing cognitive architectures under frozen, reproducible benchmark conditions using rigorous repeated-measures statistical analysis.
2. **Hypothesis:** Candidate C (Deterministic Core + Tool-Augmented Orchestrator) achieves comparable or superior mapping accuracy to Candidate A (8-Agent Swarm) with >60% lower token consumption and >50% lower end-to-end latency. Candidate B provides moderate token overhead but higher rigidness.
3. **Candidates:**
   - Candidate A: Legacy 8-Agent Micro-Service Swarm (JSON-RPC over internal message bus).
   - Candidate B: Four-Subsystem Decoupled Pipeline (Rigid sequential document passing).
   - Candidate C: Two-Tier Model (Deterministic Core + Tool-Augmented Cognitive Orchestrator).
4. **Controlled Methodology & Reproducibility Controls:**
   - **Pinned LLM Model & Version:** Frozen model checkpoint ID (e.g., `gemini-1.5-pro-002`, `gpt-4o-2024-08-06`, or frozen local container). No floating API alias permitted.
   - **Pinned Prompt & Tool Schemas:** Prompt templates frozen with git commit hash; tool definitions pinned to JSON Schema Draft 2020-12 v1.2.
   - **Token & Context Budgets:** Max 8,192 input tokens per turn; max 2,048 completion tokens per generation step.
   - **Nondeterminism Controls:** Temperature = 0.0, top_p = 1.0, fixed random seed = 42 across all runs.
   - **Ground-Truth Labeling:** Independent human-annotated field mappings with Cohen's kappa $\ge 0.90$ inter-annotator agreement.
   - **Task-Level Pairing Across Candidates:** Candidates A, B, and C are evaluated on the exact same task set.
   - **Nested Repeated Measures (Avoiding Pseudo-Replication):**
     - Each task is evaluated across $k=5$ repeated runs.
     - Repeated runs of the same task are treated as **nested observations**, NOT independent samples.
     - Modeling is performed via a **Linear Mixed-Effects Model (LMM)** for token consumption and latency:
       $$\text{Metric}_{ijk} = \beta_0 + \beta_{\text{Candidate}, j} + u_{\text{Task}, i} + \epsilon_{ijk}$$
       where $u_{\text{Task}, i} \sim \mathcal{N}(0, \sigma^2_{\text{Task}})$ is the task random intercept, properly partitioning between-task and within-task variance.
     - For non-parametric validation, task-level median aggregation is paired with two-sided **Wilcoxon signed-rank tests** with Bonferroni-Holm multiple comparison correction.
     - Report 95% bootstrap confidence intervals (1,000 resamples) for effect sizes.
     - Outlier handling: Tasks with metrics $> 3 \times \text{IQR}$ from median are isolated and analyzed for schema parsing failures.
   - **Phased Evaluation Protocol:**
     - *Phase 1 (Exploratory Pilot Benchmark):* 20 real-world multi-workbook consolidation tasks with ambiguous headers and subtle duplicates (`BENCH-CONSOL-20`). Run each task 5 times per candidate under identical frozen settings ($N=100$ runs per candidate) to evaluate variance and prompt stability.
     - *Phase 2 (Formal Statistical Benchmark):* Expanded 100-task benchmark (`BENCH-COGNITIVE-100`) covering edge cases, jagged matrices, and multi-tier headers ($N=500$ runs per candidate).
5. **Metrics:**
   - Total token consumption (prompt + completion tokens per task).
   - End-to-end wall-clock latency (seconds).
   - Semantic field mapping F1 score (precision and recall against ground-truth keys).
   - JSON serialization / schema repair retry rate (count of retries per task).
   - System failure rate (unhandled agent communication errors or hallucinations).
6. **Success Criteria (Evaluation for All Candidates):**
   - Candidate C: Achieves F1 score >= 95% with >=40% lower token consumption and latency than Candidate A with statistical significance ($p < 0.01$).
   - Candidate B: Evaluated on F1 score and latency vs. C to determine if pipeline rigidity impairs iterative disambiguation.
   - Candidate A: Evaluated on whether multi-agent deliberation yields measurable precision gains over C that justify its token overhead.
7. **Failure Criteria:** A candidate failing to achieve F1 >= 90%, exhibiting >5% schema failure retry rate, or producing coordinate hallucinations.
8. **Evidence Required for a Decision:** Statistically rigorous benchmark report across `BENCH-COGNITIVE-100` with 95% confidence intervals, latency distributions, and cost-per-consolidation metrics across Candidates A, B, and C.
