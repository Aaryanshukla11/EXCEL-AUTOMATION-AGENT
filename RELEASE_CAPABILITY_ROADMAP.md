# Autonomous Excel Intelligence Platform
## Release Capability Roadmap

**Document Type:** Strategic Product & Engineering Roadmap  
**Document Version:** 2.6-Approved-Baseline  
**Document Status:** Phase 0 Authorized by Project Owner (2026-11-21)  
**Governance Gate Status:**  
- **Gate 1 (PDR-01 through PDR-06):** APPROVED (2026-11-21)  
- **Gate 2 (Phase 0 Technical Experiments):** AUTHORIZED (2026-11-21)  
- **Gate 3 (Production Implementation):** STRICTLY NOT AUTHORIZED  

---

## 1. Phasing Philosophy: Non-Constraining Evolution

The core architectural requirement is that **Release 1.0 must not permanently constrain the universal platform**. 
- Release 1.0 delivers the shared **Universal Discovery & Execution Engine** paired with the **Multi-Workbook Consolidation Capability (Profile 1)** and **Static Structural & Quality Auditing**.
- Source file ingestion in Release 1.0 includes `.xlsx`, `.xlsm`, and planned read-only `.xlsb` (pending empirical verification in EXP-05). Writing `.xlsb` binary format is strictly unsupported.
- Subsequent releases layer on formula intelligence, cross-sheet relational restructuring, and generative reporting as additional operational profiles without rewriting the foundation.

```
+==================================================================================================+
|                                    PHASED RELEASE ROADMAP                                        |
+==================================================================================================+
|  Phase 0: Architecture Spikes & Technical Decision Resolution (Weeks 1 - 4)                      |
|  - Execute Spikes EXP-01 through EXP-09; resolve PDR-01 through PDR-06; formalize contracts.     |
|  - Curate and label pilot corpus BENCH-AUDIT-200 and specify BENCH-AUDIT-EXTENDED.               |
|  - Execute baseline performance benchmarks on BENCH-PERF-MULTI-5 and BENCH-SCALE-100K.           |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase 1 (Release 1.0): Universal Foundation + Multi-Workbook Consolidation (Profile 1)          |
|  - Universal Ingestion (.xlsx, .xlsm, planned ro-.xlsb), Topological Discovery, Type Profiling.   |
|  - Multi-source ingestion, deduplication, missing-field enrichment gate, audit ledger.          |
|  - Static Structural & Formula Quality Audit:                                                    |
|    (1) #REF!, #VALUE!, #DIV/0!, #NAME?, #N/A, (2) static cycles, (3) jagged rows, (4) unmapped,  |
|    (5) candidate key collision anomalies. Verified via PROTOCOL-QA-01 (cluster-adjusted).        |
|  - Dual Performance Criteria: V1.2 Multi-Workbook (<=60s, <=4x RAM) & Streaming (<250MB RSS).   |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase 2 (Release 2.0): Formula Intelligence, Auditing & Cross-Sheet Lookups (Profile 2)        |
|  - Calculated metric synthesis, automated XLOOKUP relationship modeling.                         |
|  - Advanced Formula Model Auditing (cross-sheet calculation chains, orphaned islands).           |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase 3 (Release 3.0): Generative Reporting, Restructuring & Conversational Analytics (Profile 3)|
|  - Natural language summary tab generation, table pivoting/unpivoting, autonomous reporting.     |
+==================================================================================================+
```

---

## 2. Detailed Milestone Specifications

### Phase 0: Technical Spikes & Architectural Baseline Formalization
* **Scope:** Non-implementation engineering research, benchmarking, and fixture corpus curation.
* **Prerequisites:** Project-owner authorization to execute empirical spikes.
* **Complete Technical Spike Activity Checklist (All 9 Spikes Mandatory):**
  1. [ ] **EXP-01:** OpenXML part preservation comparative spike (Python `openpyxl`/`defusedxml` vs. Rust `quick-xml`/PyO3 vs. Custom Python Archive Part-Patcher).
  2. [ ] **EXP-02:** Streaming ingestion and process memory benchmarks on 100k-row sheets (`BENCH-SCALE-100K`) and V1.2 multi-workbook consolidation profiling (`BENCH-PERF-MULTI-5`).
  3. [ ] **EXP-03:** Formula recalculation & headless value caching compatibility matrix.
  4. [ ] **EXP-04:** Dynamic & volatile formula AST dependency boundaries and quarantine rules.
  5. [ ] **EXP-05:** Format compatibility boundaries & opaque VBA binary stream preservation (`vbaProject.bin`) with zero macro execution; empirical viability of read-only `.xlsb`.
  6. [ ] **EXP-06:** Storage transactions across Local NVMe (staged flush + parent dir sync + atomic swap + WAL), SMB network shares (target), and OneDrive sync directories (hypothesis).
  7. [ ] **EXP-07:** In-memory shadow dry-run validation and pre/post condition verification.
  8. [ ] **EXP-08:** Scoped HMAC-SHA256 approval token lifecycle, atomic nonce consumption, concurrent race tests, and TTL expiry.
  9. [ ] **EXP-09:** Cognitive architecture 3-way comparative benchmark (8-Agent Swarm vs. 4-Subsystem Pipeline vs. Tool-Augmented Cognitive Orchestrator) evaluated via repeated-measures Linear Mixed-Effects Models (LMM) and task-level paired Wilcoxon signed-rank tests across exploratory pilot (`BENCH-CONSOL-20`) and formal statistical benchmark (`BENCH-COGNITIVE-100`).
  10. [ ] **Audit Corpus Curation:** Curate, label, and freeze `BENCH-AUDIT-200` pilot corpus (100 clean negative controls, 50 isolated positive defects, 50 mixed fixtures) with ground-truth unit manifests, and author the specification for `BENCH-AUDIT-EXTENDED`.
* **Measurable Exit Criteria:**
  - 100% of technical spikes EXP-01 through EXP-09 completed and documented with empirical data.
  - Final technology stack approved by project owner based on spike evidence.
  - Formal JSON Schema specifications frozen for Discovery Manifests and Operation Contracts.
  - `BENCH-AUDIT-200` ground-truth manifests finalized and peer-reviewed.

---

### Phase 1 (Release 1.0): Universal Discovery Foundation + Multi-Workbook Consolidation
* **Target Objective:** Deliver an enterprise-grade autonomous consolidation platform that populates existing Master workbooks safely from disparate source files, including baseline static quality auditing.
* **Included Capabilities:**
  - **Universal Discovery Engine:** Ingestion of `.xlsx`, `.xlsm`, and planned read-only `.xlsb` source files (pending EXP-05); spatial bounding-box segmentation; dynamic type profiling; header hierarchy resolution.
  - **Static Structural & Quality Auditing Engine (Release 1.0):** Pre-execution audit detecting and cataloging five explicit defect categories:
    1. Formula evaluation errors (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, `#N/A`).
    2. Formula circular reference dependency cycles (statically resolvable).
    3. Jagged rows (structural row length variance violating table boundary).
    4. Unmapped source fields (source columns with no destination in target Master).
    5. Candidate key collision anomalies (partial matches or duplicate keys with divergent attributes).
  - **Consolidation Profile (Profile 1):** Multi-source ingestion; semantic field mapping; candidate key discovery; evidence-based record deduplication; blank-field enrichment approval gate (FR-09); populated cell overwrite gate (FR-10); cross-source conflict adjudication (DR-A2); non-table boundary safety (DR-A3).
  - **Deterministic Execution Layer:** Air-gapped OpenXML mutation; table expansion (`ListObject`); table formula column propagation; in-memory shadow dry run; multi-step crash-consistent rollback protocol; post-flight invariant verification.
  - **Security & Governance:** Scoped HMAC-SHA256 approval tokens; untrusted content neutralization; append-only audit trail with SHA-256 chain; safe parser quotas.
  - **Storage Adaptability:** Atomic namespace replacement, file/directory flush, and WAL on local filesystems; sync-safe staging with retry on OneDrive and SMB shares (design targets pending EXP-06).
* **Prerequisites:** Phase 0 completion.
* **Measurable Exit Criteria:**
  - >=98% precision and >=95% recall on semantic field mapping benchmark (`BENCH-MAP-100`).
  - 0.0% false positive duplicate insertions on `BENCH-DEDUP-500`.
  - >=98.0% defect detection rate (Sensitivity) and <=1.0% false positive rate (FPR) across all 5 defect categories under `PROTOCOL-QA-01` on `BENCH-AUDIT-200` pilot (with cluster-adjusted confidence intervals reported).
  - V1.2 Consolidation Performance: Ingestion, profiling, and mapping across 5 source workbooks ($\le 20\text{k}$ rows each) + Master completed in $\le 60$ seconds; peak memory $\le 4\times$ uncompressed sheet size (`BENCH-PERF-MULTI-5`).
  - Streaming Engine Performance: 100k-row sheet parsed with peak process RSS < 250MB and latency < 15 seconds (`BENCH-SCALE-100K`).
  - 100% enforcement of blank-field enrichment gate (zero unapproved writes).
  - 100% bitwise recovery on simulated write failures (atomic rollback on local filesystem).
  - 100% multi-run idempotency: reprocessing same sources results in exactly 0 duplicate insertions.

---

### Phase 2 (Release 2.0): Formula Intelligence, Auditing & Cross-Sheet Relationships
* **Target Objective:** Expand platform capabilities to user-directed calculation synthesis and cross-sheet relational lookups without modifying the core discovery engine.
* **Included Capabilities:**
  - **Formula Intelligence Profile (Profile 2):** Natural-language-driven calculation synthesis (e.g., *"Add Gross Margin as (Revenue - Cost) / Revenue"*); formula syntax verification; cycle detection; safe formula column append.
  - **Cross-Sheet Relationship Engine:** Automated foreign-key discovery; dynamic generation of `XLOOKUP` / `INDEX-MATCH` formulas linking disparate sheets.
  - **Advanced Formula Model Auditing (Release 2.0):** Cross-sheet calculation chain audits, semantic formula consistency checks across tabular columns, and orphaned calculation island detection.
* **Prerequisites:** Release 1.0 operational in production.
* **Measurable Exit Criteria:**
  - >=95% accuracy on formula synthesis benchmark suite against ground-truth financial models.
  - Zero introduction of circular references or broken dependencies across 100 test runs.

---

### Phase 3 (Release 3.0): Generative Reporting, Structural Restructuring & Conversational Analytics
* **Target Objective:** Deliver the full universal spreadsheet intelligence vision: open-ended reporting, restructuring, and interactive conversational analytics.
* **Included Capabilities:**
  - **Generative Reporting Profile (Profile 3):** Intent-authorized creation of new summary worksheets, aggregation tables, and executive dashboard tabs.
  - **Data Restructuring:** Unpivoting cross-tabular matrices into normalized transaction tables; splitting compound columns; restructuring denormalized lists.
  - **Conversational Analytics:** Natural language multi-turn Q&A over complex multi-sheet workbooks with visual diff previews.
* **Prerequisites:** Release 2.0 operational.
* **Measurable Exit Criteria:**
  - Verified ability to generate complex multi-table summary tabs from natural language directives without manual cell mapping.
  - Strict preservation of non-targeted source data sheets during generative report creation.
