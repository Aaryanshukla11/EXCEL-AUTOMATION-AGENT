# Autonomous Excel Intelligence Platform
## Product Decision Register (PDR)

**Document Type:** Formal Architectural & Product Decision Register  
**Document Version:** 2.6-Approved  
**Document Status:** APPROVED BY PROJECT OWNER (2026-11-21)  
**Governance Gate Status:**  
- **Gate 1 (Product Decisions PDR-01 to PDR-06):** **APPROVED** (2026-11-21)  
- **Gate 2 (Phase 0 Technical Experiment Authorization):** **AUTHORIZED** (2026-11-21)  
- **Gate 3 (Production Implementation Authorization):** **STRICTLY NOT AUTHORIZED**  

---

## 1. Decision Governance & Status Overview

This register formally records the six foundational decisions approved by the Project Owner on 2026-11-21 to establish the platform's architectural baseline and authorize Phase 0 technical spikes.

```
+==================================================================================================================================+
|                                              PRODUCT DECISION SUMMARY REGISTER                                                   |
+==================================================================================================================================+
| Decision ID | Decision Title                         | Formal Status  | Owner Approval Date | Approved Decision Summary          |
+-------------+----------------------------------------+----------------+---------------------+------------------------------------+
| PDR-01      | Universal Platform vs. Consolidation   | APPROVED       | 2026-11-21          | Alternative A: Universal Platform  |
|             |                                        |                |                     | with Pluggable Capability Profiles |
+-------------+----------------------------------------+----------------+---------------------+------------------------------------+
| PDR-02      | Comprehensive Structural Policy        | APPROVED       | 2026-11-21          | Alternative B: Context-Gated /     |
|             |                                        |                |                     | Profile-Specific Policy across rel.|
+-------------+----------------------------------------+----------------+---------------------+------------------------------------+
| PDR-03      | Formula Recalculation Strategy         | APPROVED       | 2026-11-21          | Alternative A (fullCalcOnLoad R1.0)|
|             |                                        |                |                     | + EXP-03 Value Cache Spike         |
+-------------+----------------------------------------+----------------+---------------------+------------------------------------+
| PDR-04      | Cross-Source Duplicate & Conflict      | APPROVED       | 2026-11-21          | Alternative B: Co-Provenance for   |
|             |                                        |                |                     | duplicates + Mandatory HITL review |
+-------------+----------------------------------------+----------------+---------------------+------------------------------------+
| PDR-05      | Non-Table Insertion Boundary           | APPROVED       | 2026-11-21          | Alternative B/C: Halt on Collision |
|             |                                        |                |                     | + Table Conversion Proposal Gate   |
+-------------+----------------------------------------+----------------+---------------------+------------------------------------+
| PDR-06      | Cognitive Architecture Topology        | APPROVED       | 2026-11-21          | Authorize EXP-09 3-Way Comparative |
|             |                                        |                |                     | Benchmark (Leading: Alternative C) |
+==================================================================================================================================+
```

---

## 2. Detailed Decision Records

### PDR-01: Universal Platform Charter vs. Dedicated Consolidation Point Solution
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Alternative A (Universal Platform with Pluggable Capability Profiles)**.
* **Scope Specification:**
  - The platform is officially chartered as a **Universal, Domain-Agnostic Excel Intelligence Platform**.
  - Multi-Workbook Data Consolidation is formally designated as **Capability Profile 1 (Release 1.0)**, preserving and incorporating the approved [REQUIREMENTS_SPECIFICATION.md](file:///c:/Users/Aaryan%20shukla/OneDrive/Desktop/agent%20v2/REQUIREMENTS_SPECIFICATION.md) V1.2 baseline.
  - Core components (Discovery, Static Quality Auditing, Air-Gapped Execution, Invariant Enforcement) are designed as shared foundational infrastructure.
  - Subsequent releases (Release 2.0 Formula Intelligence & Release 3.0 Generative Reporting) layer onto this foundation as distinct operational profiles.

---

### PDR-02: Comprehensive Structural Creation & Modification Policy
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Alternative B (Context-Gated / Profile-Specific Policy)**.
* **Policy Enforcement:**
  - *Consolidation Profile (Release 1.0):* Zero-creation strictly enforced. Independent creation of worksheets, business tables, or business columns is prohibited. Appends are strictly confined to existing Master structures.
  - *Formula Intelligence Profile (Release 2.0):* Creation of worksheets/tables prohibited; allocation of formula columns in designated calculation zones permitted.
  - *Generative Reporting Profile (Release 3.0):* Intent-authorized creation of summary worksheets, aggregation tables, and executive dashboards permitted **only** when explicitly instructed by user prompt and confirmed via preview approval.

---

### PDR-03: Formula Recalculation Strategy for Headless Environments
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Alternative A for Release 1.0 (`fullCalcOnLoad="1"`) + EXP-03 Technical Spike**.
* **Specification:**
  - For Release 1.0, formula text is written to `<f>` tags and `<calcPr fullCalcOnLoad="1"/>` is set, avoiding heavy runtime dependencies while guaranteeing native recalculation when opened in desktop Excel.
  - Technical Spike **EXP-03** is authorized to evaluate headless formula evaluation engines (e.g. `pycel`, `formulas`) to determine the necessity and fidelity of pre-populating `<v>` tags for downstream headless ETL consumers.

---

### PDR-04: Multi-Source Duplicate Collision & Conflict Authority
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Alternative B (Multi-Source Co-Provenance for Duplicates + Mandatory HITL Review for Conflicts)**.
* **Specification:**
  - Identical records from multiple sources not present in Master are inserted once, with both source files recorded as joint originators in the immutable audit ledger.
  - Divergent values for matching primary keys halt execution and present a comparison card for human adjudication. If unapproved or timed out, the conflicting record is quarantined and neither value is written.

---

### PDR-05: Non-Excel Table Insertion Boundary Policy
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Alternative B/C (Halt on Collision + Interactive Table Conversion Proposal)**.
* **Specification:**
  - When appending into an ordinary range that has summary rows or formulas immediately below it with zero spare space, automated row shifting (Alternative A) is strictly prohibited.
  - The system halts execution (Alternative B) and presents an interactive proposal to the user to convert the range to an official Excel Table (`ListObject`) so Excel natively manages boundary expansion (Alternative C). Append executes only upon explicit approval.

---

### PDR-06: Cognitive Architecture Topology
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Authorize EXP-09 Three-Way Comparative Benchmark**.
* **Specification:**
  - Technical Spike **EXP-09** is authorized to empirically benchmark all three candidates:
    1. Candidate A: Legacy 8-Agent Swarm (JSON-RPC).
    2. Candidate B: Four-Subsystem Decoupled Pipeline.
    3. Candidate C: Two-Tier Model (Deterministic Core + Tool-Augmented Orchestrator) — *Leading Hypothesis*.
  - Evaluation is conducted under frozen reproducibility conditions using repeated-measures Linear Mixed-Effects Models (LMM) and task-level paired Wilcoxon tests to eliminate pseudo-replication.

---

### Section 3: Static Quality Audit Statistical Validation Strategy
* **Status:** `APPROVED BY PROJECT OWNER (2026-11-21)`
* **Approved Decision:** **Two-Tier Phased Strategy**.
* **Specification:**
  - *Tier 1 (`BENCH-AUDIT-200`):* Curated during Phase 0; serves as the mandatory **Phase 1 Acceptance Gate Pilot** for operational screening.
  - *Tier 2 (`BENCH-AUDIT-EXTENDED`):* $\ge 1,000$ workbooks ($\ge 850$ positive defect units per category); curated during Phase 1 for formal statistical certification ($\ge 98.0\%$ Sensitivity, $\le 1.0\%$ FPR, $\le \pm 1.2\%$ margin of error under cluster-robust bootstrap).
