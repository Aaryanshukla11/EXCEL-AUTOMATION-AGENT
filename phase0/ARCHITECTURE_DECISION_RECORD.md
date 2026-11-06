# Autonomous Excel Intelligence Platform
## Architecture Decision Record (ADR Suite)

**Document Type:** Formal Architectural Decision Records  
**Document Status:** APPROVED BASELINE  
**Effective Date:** 2026-11-21  
**Project Owner Sign-Off:** Formally Approved (PDR-01 through PDR-06 & Quality Audit Strategy)  
**Implementation Authorization:** STRICTLY NOT GRANTED (Gate 3 Pending Review)  

---

## ADR-001: Universal Spreadsheet Intelligence Foundation with Pluggable Capability Profiles
* **Status:** APPROVED (Governed by PDR-01 Alternative A)
* **Context:** The platform requires an architectural charter that resolves whether the product is permanently scoped as a multi-workbook consolidation tool, or structured as a universal, domain-agnostic spreadsheet intelligence platform where consolidation is an initial operational capability.
* **Decision:** Chartered as a **Universal Excel Intelligence Platform**. The core foundation (Topological Segmentation, Dynamic Type Inference, Static Quality Auditing, Invariant Enforcement, Air-Gapped Execution) is domain-agnostic and shared across all releases. Capabilities are encapsulated into pluggable operational profiles:
  - *Profile 1 (Release 1.0):* Multi-Workbook Data Consolidation (incorporating approved V1.2 specifications).
  - *Profile 2 (Release 2.0):* Formula Intelligence, Advanced Model Auditing & Cross-Sheet Lookups.
  - *Profile 3 (Release 3.0):* Generative Reporting, Structural Restructuring & Conversational Analytics.
* **Consequences:** Eliminates architectural throwaway; provides long-term extensibility; ensures that Release 1.0 consolidation components are built on decoupled, domain-agnostic abstractions.

---

## ADR-002: Context-Gated Comprehensive Structural Policy Across Lifecycle
* **Status:** APPROVED (Governed by PDR-02 Alternative B)
* **Context:** Operating safely on enterprise spreadsheets requires strict rules defining when and how the platform may create or modify worksheets, tables, columns, formulas, and formatting.
* **Decision:** Adopt a **Context-Gated / Profile-Specific Structural Policy**:
  - *Consolidation Profile (Release 1.0):* Absolute zero-creation invariant. The engine is strictly prohibited from creating worksheets, tables, or business columns, or inventing business formulas. Mutations are confined to expanding existing Master tables and appending records.
  - *Formula Intelligence Profile (Release 2.0):* Zero-creation of worksheets/tables maintained; allocation of formula metric columns in calculation zones is authorized.
  - *Generative Reporting Profile (Release 3.0):* Creation of summary worksheets, aggregation tables, and executive dashboards is authorized **only** when explicitly instructed by user prompt and confirmed via human approval preview.
* **Consequences:** Guarantees 100% structural safety during consolidation while avoiding permanent architectural dead-ends for future generative capabilities.

---

## ADR-003: Deferred Formula Recalculation for R1.0 with Hybrid Value Caching Strategy
* **Status:** APPROVED (Governed by PDR-03 Alternative A + EXP-03 Empirical Evidence)
* **Context:** Downstream spreadsheet consumers vary: desktop Excel natively recalculates formulas when `<calcPr fullCalcOnLoad="1"/>` is set, but headless ETL readers (`pandas`, `calamine`, `openpyxl(data_only=True)`) read the cached `<v>` tag and return `None` or `NaN` if `<v>` is omitted (empirically confirmed in EXP-03).
* **Decision:** 
  - For **Release 1.0**, the platform writes formula text to `<f>` tags and sets `<calcPr fullCalcOnLoad="1"/>`, guaranteeing portable recalculation for desktop Excel users without heavyweight OS-dependent COM processes.
  - The limitation for headless consumers is prominently documented. For automated headless pipelines, Phase 1 architecture incorporates an optional lightweight headless evaluation worker (e.g. `pycel` / `formulas`) to populate standard `<v>` tags for basic mathematical/logical expressions.
* **Consequences:** Maximizes portability and headless safety in Release 1.0 while establishing an evidence-backed upgrade path for headless ETL pipelines.

---

## ADR-004: Multi-Source Co-Provenance for Duplicates and Mandatory HITL Review for Conflicts
* **Status:** APPROVED (Governed by PDR-04 Alternative B)
* **Context:** In multi-source consolidation, two source workbooks may contain identical new records (duplicate collision) or divergent attribute values for the same primary entity (data conflict).
* **Decision:** 
  - *Identical Multi-Source Duplicates:* Inserted once into the Master Workbook. Both source file identities, hashes, and cell coordinates are recorded as joint originators (co-provenance) in the immutable audit ledger.
  - *Attribute Conflicts:* Execution halts. The platform renders an interactive side-by-side comparison card displaying the conflicting values and source provenance. The user must explicitly select a value, provide an override, or quarantine. Non-response or cancellation defaults to quarantine (neither value is written).
* **Consequences:** Zero silent data loss; zero arbitrary automated tie-breaking; human authority enforced at conflict boundaries.

---

## ADR-005: Non-Excel Table Insertion Boundary Safety & Conversion Proposal
* **Status:** APPROVED (Governed by PDR-05 Alternative B/C)
* **Context:** Appending records into ordinary ranges (not official Excel `ListObject` tables) that have summary rows or formulas immediately below them with zero spare space risks corrupting sheet calculations if automated row shifting is executed.
* **Decision:**
  - Automated row shifting (Alternative A) is **strictly prohibited** due to extreme risk of breaking side-by-side tables and 3D formula references.
  - The engine halts execution upon detecting boundary collisions (Alternative B).
  - The platform presents an interactive escalation proposal to the user to convert the target range into an official Excel Table (`ListObject`), enabling Excel's native table expansion mechanics (Alternative C). Append executes only upon explicit user sign-off.
* **Consequences:** Prevents silent formula reference corruption while guiding users toward resilient tabular structures.

---

## ADR-006: Two-Tier Cognitive Topology (Deterministic Core + Tool-Augmented Orchestrator)
* **Status:** APPROVED (Governed by PDR-06 Alternative C + EXP-09 Statistical Validation)
* **Context:** Three cognitive architectures were evaluated: Legacy 8-Agent Micro-Service Swarm, Four-Subsystem Decoupled Pipeline, and Two-Tier Model (Deterministic Core + Tool-Augmented Orchestrator).
* **Decision:** Adopt **Candidate C (Two-Tier Model: Deterministic Core + Tool-Augmented Cognitive Orchestrator)**:
  - *Tier 1 (Deterministic Core):* High-performance, air-gapped OpenXML parsers, spatial bounding-box segmenter, static formula AST analyzer, schema validator, and 6-phase Write-Ahead Logging transaction manager.
  - *Tier 2 (Cognitive Orchestrator):* A unified reasoning model equipped with strongly-typed inspection tools (`inspect_table_bounds`, `sample_column_values`, `evaluate_duplicate`, `synthesize_plan`). Emits declarative JSON Schema 2020-12 Operation Contracts.
  - *Zero Direct Write Authority:* The LLM has strictly zero write access to the filesystem. All mutations must pass through deterministic in-memory shadow validation, static quality defect auditing, candidate key collision checks, and HMAC symmetric MAC approval.
* **Empirical Validation (EXP-09):** Conclusively demonstrated a **72.5% reduction in token consumption** and **70.5% reduction in latency** compared to the 8-Agent Swarm ($p < 0.001$), while achieving higher mapping accuracy (F1 = **0.968** vs. 0.933).
* **Consequences:** Dramatically lowers operational cost and latency while eliminating multi-agent cascading serialization failures.

---

## ADR-007: Two-Tier Quality Audit Validation Strategy (Pilot Gate + Extended Certification)
* **Status:** APPROVED (Governed by QA-01 Power Derivation & Statistical Modeling)
* **Context:** Mathematical power calculations demonstrate that verifying Sensitivity with margin of error $\le \pm 1.2\%$ under intra-workbook clustering ($DEFF = 1.6$, $\text{ICC} = 0.15, m = 5$) requires $N_{\text{pos}} \ge 837$ positive defect units per category across $\ge 250$ workbooks. The initial 200-workbook corpus (`BENCH-AUDIT-200`) contains $N_{\text{wb}} = 200$ workbooks (50 clean controls, 50 isolated single-defect, 100 mixed), providing only $N_{\text{pos}, c} \approx 32.6$ positive defect units per category, which yields an effective sample size $N_{\text{eff}} = 32.64 / 1.6 \approx 20.4$ units per category. This yields an approximate Wilson 95% CI of $[80.96\%, 99.82\%]$ ($E \approx \pm 6.07\%$), mathematically proving that `BENCH-AUDIT-200` cannot certify the release.
* **Decision:** Adopt a **Two-Tier Phased Quality Audit Strategy** with explicit statistical precision, proposed acceptance rules, and cluster-aware methodologies:
  - *Cluster Definition & Analytical Methods:* The **workbook** is explicitly defined as the primary sampling cluster. While design-adjusted Wilson intervals ($N_{\text{eff}} = N / \text{DEFF}$) provide first-order planning approximations ("Effective-sample-size Wilson approximation (planning only)"), final release certification strictly requires workbook-cluster-aware inference (Cluster Bootstrap with $B \ge 2,000$ iterations across resampled workbooks, GEE with exchangeable working correlation, or GLMM mixed-effects models).
  - *Statistical Precision Criterion:* Two-sided 95% Wilson half-width margin $E \le \pm 1.20\%$ at $\hat{p} \approx 0.98$. Sizing audit reveals that $N_{\text{pos}} = 850$ ($N_{\text{eff}} = 531.25$) yields $W = \pm 1.2353\%$ and **FAILS PRECISION CRITERION**; achieving $\le \pm 1.20\%$ precision requires $N_{\text{eff}} = 561.25 \implies N_{\text{pos}} = 898$ raw positive defect units per category ($\text{DEFF} = 1.60$), which yields $W = \mathbf{1.19953\% \le \pm 1.20000\%}$.
  - *Approved Statistical Acceptance Rule (One-Sided 95% LCB):* The strict sensitivity acceptance standard requiring the one-sided 95% Lower Confidence Bound to satisfy $\text{LCB}_{95\%, 1\text{-sided}} \ge 98.00\%$ is formally **APPROVED by the Project Owner**. Neither corpus guarantees certification without empirical defect detection:
    - *Historical 850-Unit Candidate Corpus ($N_{\text{pos}} = 850, N_{\text{eff}} = 531.25$):* Boundary check demonstrates that $841 / 850$ yields $\text{LCB} = \mathbf{97.92\%} < 98.00\%$ (fails), while $\ge 842 / 850$ detections ($\hat{p} = 99.06\%$) yielded an effective-sample-size Wilson LCB of $98.08\% \ge 98.00\%$. (Superseded because it failed the $\le \pm 1.20\%$ precision criterion with $W = \pm 1.2353\%$).
    - *Approved 898-Unit Precision Corpus ($N_{\text{pos}} = 898, N_{\text{eff}} = 561.25$):* Formally approved to satisfy two-sided precision ($W = \mathbf{1.19953\%} \le \pm 1.2000\%$). Achieving the approved $\text{LCB}_{95\%, 1\text{-sided}} \ge 98.00\%$ criterion establishes a preliminary effective-sample-size Wilson planning threshold of **$\ge 889 / 898$ detections** ($\hat{p} = 0.989978 \approx 99.00\%$), achieving an effective-sample-size Wilson LCB of **$98.0338\% \approx 98.03\% \ge 98.00\%$** (whereas $888 / 898$ yields $97.89\%$, failing acceptance).
    - *Mandatory Cluster-Aware Inference:* The $889 / 898$ threshold is an effective-sample-size planning approximation ($N_{\text{eff}} = 561.25$). Final release certification strictly requires workbook-cluster-aware inference (Cluster Bootstrap, GEE, or GLMM), with the workbook explicitly designated as the primary sampling cluster.
  - *Reconciled False Positive Rate (FPR) Acceptance Rule:* Planned at the boundary threshold $P = 0.005$ with margin $E = \pm 0.003$, yielding $N_{\text{eff}} = 2,124$ and requiring $N_{\text{neg}} \ge 3,080$ negative evaluation units across $K_{\text{clean}} \ge 308$ clean workbooks ($\text{DEFF}_{\text{neg}} = 1.45, \rho = 0.05, m = 10$). An observed $\hat{p} \le 0.002$ achieves a one-sided $\text{UCB}_{95\%, 1\text{-sided}} = 0.435\% \le 0.50\% \implies \mathbf{ACCEPTED}$.
  - *Tier 1 (`BENCH-AUDIT-200`):* Curated during Phase 0; serves as the mandatory **Phase 1 Acceptance Gate Pilot** for operational defect screening.
  - *Tier 2 (`BENCH-AUDIT-EXTENDED`):* Specifications frozen during Phase 0; $\ge 1,000$ workbooks ($\ge 898$ positive defect units per category, $\ge 3,080$ negative units) curated and executed during Phase 1 for formal statistical certification.
  - *Certification Disclaimer:* Static defect auditing certification is **STRICTLY PENDING EXECUTION** until the Tier 2 Extended Corpus is generated and evaluated in Phase 1.
* **Consequences:** Enforces rigorous statistical discipline without delaying Phase 1 architecture design.
