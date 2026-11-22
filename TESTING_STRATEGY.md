# Autonomous Excel Intelligence Platform V2
## Quality Assurance & Testing Strategy (TESTING_STRATEGY.md)
### Status: Proposed Architectural Draft (Reconciled with Approved PROTOCOL-QA-01 Standards)

---

### 1. Testing Philosophy: Probabilistic vs. Deterministic

The testing strategy rigorously separates the evaluation of probabilistic cognitive reasoning from the validation of the deterministic execution core:

```
+-----------------------------------------------------------------------------------+
|                             TESTING ARCHITECTURE                                  |
+-----------------------------------------------------------------------------------+

   COGNITIVE TIER (PROBABILISTIC)             EXECUTION TIER (DETERMINISTIC)
   - Benchmark-Driven Evaluation              - Property-Based Testing (Hypothesis)
   - PROTOCOL-QA-01 Cluster-Aware Sampling    - Bitwise Pre-State Recovery (.bak)
   - Schema Conformance Suites                - COR-01 Durability & WAL Tests
   - Prompt Regression Golden Fixtures        - Tarjan SCC Static Cycle Interception
```

---

### 2. Multi-Tier Testing Pyramid

```
                       / \
                      /   \
                     / E2E \  Tier 4: End-to-End Pipeline & HITL Scenarios
                    /-------\
                   /  QA-01  \  Tier 3: PROTOCOL-QA-01 Cluster-Aware Extended Certification
                  /-----------\
                 /  Isolation  \  Tier 2: Tool & Analytical Facade Mock Contract Tests
                /---------------\
               /  Deterministic  \  Tier 1: Core Engine, Parser & OpenXML Property Tests
              /-------------------\
```

---

### 3. Detailed Test Tier Specifications

#### 3.1 Tier 1: Deterministic Engine & Property Verification
* **Scope:** M02 Streaming Parser, M03 Inspector, M04 Spatial Detector, M05 Formula Parser, and Tier 3 DEL.
* **Test Suites:**
  - `test_scratch_lifecycle.py`, `test_bounded_memory.py`: Validates sampled event-driven memory guard:
    - Warning tripwire at exactly **235,000,000 bytes** working set (`WARNING_TRIPWIRE_WORKING_SET_BYTES`).
    - Typed hard-error ceiling at exactly **250,000,000 bytes** working set (`HARD_CEILING_WORKING_SET_BYTES`).
    - Attributable burst allocation delta trigger at **8,000,000 bytes** (`EVENT_DRIVEN_DELTA_THRESHOLD_BYTES = 8_000_000` in `crates/excel_intel_rs/src/memory_guard.rs`).
    - Dual-cadence telemetry verification (sampled periodically every 1,000 rows or on attributable $\ge 8,000,000\text{ bytes}$ burst deltas; not an instantaneous OS-level RSS cap).
  - `test_m05_formula_parser.py`: Scoped EBNF grammar, operator precedence, root statuses `PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, `PARSE_ERROR` (M05 Prompt 3). Pure AST and reference nodes only.
  - COR-01 Durability Verification: Exact 7-step sequence: (1) Establish pre-state backup snapshot (`.bak`); (2) Persist and flush durable WAL intent (`INTENT_RECORDED`); (3) Write staged replacement copy to `.staging/<session_id>/`; (4) Fsync staged file data and metadata; (5) Atomic replacement via `os.replace` on same volume; (6) Parent-directory durability step where supported by the operating system (explicitly verifying the Windows NTFS durability limitation: Windows NTFS does not provide POSIX directory `fsync()`, and NTFS journal persistence is not an equivalent guaranteed durability primitive, leaving directory entry metadata subject to OS flushing semantics); (7) Mark transaction `COMMITTED` in WAL.
  - OpenXML Preservation Tests: Verified bitwise preservation of non-targeted package parts (`vbaProject.bin`, drawings, slicers, media, themes, unedited `sheetK.xml` streams) and semantic/structural preservation of modified worksheets under targeted patching on local NTFS. Universal bitwise preservation is disclaimed.

#### 3.2 Tier 2: Analytical Facade & Tool Isolation Tests
* **Scope:** Strongly-typed analytical facades without live LLM calls.
* **Methodology:**
  - Golden Fixtures: Raw token maps tested against expected `SpatialAnalysisReport`, `ColumnInferenceResult`, and AST trees.
  - Schema Conformance: 100% of tool outputs pass JSON Schema validation.

#### 3.3 Tier 3: PROTOCOL-QA-01 Statistical Certification Suite (Approved Baseline)
* **Mathematical Justification:**
  In accordance with ADR-007, PROTOCOL-QA-01, and COR-02, cells and rows within a workbook share generator characteristics; naive pooling of cells across workbooks is statistically invalid due to intra-workbook correlation.
  - Design effect: $DEFF = 1 + (m - 1)\text{ICC} = 1 + (5 - 1)(0.15) = 1.60$.
  - Precision requirement: Two-sided 95% Wilson margin $E \le \pm 1.20\%$ at $\hat{p} \approx 0.98$. Sizing audit reveals that $N_{\text{pos}} = 850$ ($N_{\text{eff}} = 531.25$) yields $W = \pm 1.2353\%$ and fails precision; achieving $\le \pm 1.20\%$ precision requires $N_{\text{eff}} = 561.25 \implies N_{\text{pos}} = 898$ positive defect units per category.
* **Five Explicit Defect Categories:**
  1. *Category 1 (Formula Evaluation Errors):* Formula cells containing `#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, `#N/A`.
  2. *Category 2 (Circular References):* Formula dependency components participating in genuine static circular loops.
  3. *Category 3 (Jagged Rows):* Table rows whose populated cell span diverges from declared/inferred column boundary.
  4. *Category 4 (Unmapped Source Fields):* Source columns with no valid destination in target Master table schema.
  5. *Category 5 (Candidate Key Collisions):* Record pairs with matching primary candidate keys but conflicting attribute values.
* **Corpus Sizing & Acceptance Standards:**
  - **Positive Corpus:** At least 1,000 positive-corpus workbooks providing $N_{\text{pos}} \ge 898$ positive defect units per category across all five categories.
  - **Negative Corpus:** Approved 308-workbook clean control corpus ($K_{\text{clean}} \ge 308, N_{\text{neg}} \ge 3,080$).
  - **Cluster-Aware Inference:** Final certification strictly requires workbook-cluster-aware inference (Cluster Bootstrap with $B \ge 2,000$ iterations, GEE, or GLMM with workbook as primary cluster).
  - **One-Sided 95% Sensitivity LCB Requirement:** Strict sensitivity standard requires:
    $$\text{LCB}_{95\%, 1\text{-sided}} \ge 98.00\%$$
    Preliminary effective-sample-size Wilson planning threshold requires $\ge 889 / 898$ detections ($\hat{p} \approx 99.00\%, \text{LCB} = 98.03\% \ge 98.00\%$).
  - **False Positive Rate (FPR) Standard:** Boundary threshold $P \le 0.005$ with margin $E = \pm 0.003$ ($\text{UCB}_{95\%, 1\text{-sided}} \le 0.50\%$).
* **Two-Tier Phased Deployment:**
  - *Phase 1 Pilot Gate (`BENCH-AUDIT-200`):* 200 workbooks (50 clean, 50 isolated single-defect, 100 mixed). Serves as an operational screening gate ($E \approx \pm 4.5\%$).
  - *Extended Release Certification (`BENCH-AUDIT-EXTENDED`):* $\ge 1,000$ workbooks satisfying the 898-unit cluster requirement for definitive certification.

#### 3.4 Tier 4: End-to-End Pipeline & HITL Verification
* **Scope:** Integration tests validating end-to-end execution from natural language prompt to updated workbook.
* **Key Scenarios:**
  - Verification that proposed Tier 0 execution (even with confident types $H \ge 0.95, S \ge 0.90$) is BLOCKED and halted for human approval pending explicit Project Owner sign-off on Decision 8. Actual autonomous append testing is strictly conditional on future Decision 8 authorization. Heuristic support scores are verified as empirical token frequency statistics, never probabilities.
  - Mandatory HITL halt on `AMBIGUOUS` (including all-null-marker columns) or `INSUFFICIENT_DATA`.
  - Mandatory HITL halt on ADR-005 boundary collisions.
  - Recovery verification via pre-state `.bak` swap under verified backup integrity conditions on local NTFS.
  - In-session transactional rollback via reverse WAL deltas.
