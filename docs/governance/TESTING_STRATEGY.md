# Autonomous Excel Intelligence Platform V2
## Quality Assurance & Testing Strategy (TESTING_STRATEGY.md)

---

### 1. Testing Philosophy: Probabilistic vs. Deterministic

The testing strategy for Platform V2 separates the validation of **probabilistic cognitive agents** from the validation of the **deterministic execution engine**.

```
+-----------------------------------------------------------------------------------+
|                             TESTING ARCHITECTURE                                  |
+-----------------------------------------------------------------------------------+

   COGNITIVE TIER (PROBABILISTIC)             EXECUTION TIER (DETERMINISTIC)
   - Benchmark-Driven Evaluation              - Property-Based Testing (Hypothesis)
   - Synthetic Adversarial Workbooks          - Bitwise Regression & Invariant Checks
   - Schema Conformance Suites                - ACID Rollback & WAL Validation
   - Semantic Confidence Fuzzing              - Calculation Graph Cycle Detection
```

---

### 2. Multi-Tier Testing Pyramid

```
                       / \
                      /   \
                     / E2E \  Tier 4: End-to-End Autonomous Pipeline Tests
                    /-------\
                   /  Advers \  Tier 3: Domain-Agnostic Layout Benchmarks (100+ Sheets)
                  /-----------\
                 /  Isolation  \  Tier 2: Agent Isolation & Mock Contract Tests
                /---------------\
               /  Deterministic  \  Tier 1: Core Execution Engine & OpenXML Property Tests
              /-------------------\
```

---

### 3. Detailed Test Tier Specifications

#### 3.1 Tier 1: Deterministic Engine & Invariant Verification
* **Objective**: Guarantee that the Deterministic Execution Layer (DEL) is 100% reliable, idempotent, and non-destructive.
* **Test Suites**:
  1. **Schema Validation Suite**: Rejects invalid, malformed, or out-of-spec WO-IR documents.
  2. **Shadow Model Verification**: Verifies formula AST evaluation, circular dependency detection, and spatial collision checks.
  3. **Style & OpenXML Preservation Tests**: Proves that non-targeted sheets, drawing elements, macros, custom XML parts, fonts, and borders remain identical byte-for-byte.
  4. **Atomic Rollback & WAL Property Tests**:
     - Induces deliberate I/O interruptions during mutation commits.
     - Confirms that failed transactions leave zero residue and restore the workbook to its exact pre-state hash.

#### 3.2 Tier 2: Agent Isolation & Schema Contract Tests
* **Objective**: Verify that individual intelligence agents produce correct, schema-compliant outputs in response to known inputs without requiring live LLM calls.
* **Methodology**:
  - Golden Fixtures: Pairs of raw cell coordinate maps and expected JSON outputs.
  - Schema Conformance: Validates that 100% of agent outputs pass strict JSON schema evaluation.
  - LLM Mock Harness: Evaluates agent prompts against frozen model responses to catch prompt regression.

#### 3.3 Tier 3: Domain-Agnostic Layout Benchmark Suite
* **Objective**: Prove that the platform successfully comprehends and operates on unseen, exotic, and jagged spreadsheet layouts across arbitrary industries.
* **Benchmark Test Categories**:
  - **Hierarchical & Multi-tier Headers**: Headers with 2, 3, and 4 stacked rows; merged category headers.
  - **Transposed Datasets**: Tables where records flow horizontally across columns and attributes are rows.
  - **Multi-Table Sheets**: Worksheets containing 2 to 6 independent tables separated by variable whitespace.
  - **Embedded Summaries**: Tables containing intermediate subtotal rows (`SUBTOTAL`, `SUM`) and irregular grand totals.
  - **Sparse & Jagged Grids**: Grids with missing cells, uneven row lengths, and interspersed notes.
  - **Matrix / Cross-Tabular Datasets**: Two-dimensional lookup matrices (e.g., Region vs. Month).

#### 3.4 Tier 4: End-to-End Autonomous Pipeline Tests
* **Objective**: Validate the full pipeline from natural language prompt to executed workbook.
* **Test Scenarios**:
  - **New Metric Insertion**: "Calculate Gross Margin as (Revenue - Cost) / Revenue for each product."
  - **Cross-Sheet Lookup**: "Bring the department manager name from the Staff sheet into the Expense sheet."
  - **Aggregated Summary Generation**: "Create a quarterly summary tab aggregating sales by region."
  - **Formatting Synchronization**: Verifying that new calculated cells inherit surrounding border and number formatting.

---

### 4. Ambiguity, Safety & Chaos Testing

To verify the safety gates defined in `SECURITY_AND_SAFETY.md`, specific chaos and adversarial tests are executed continuously:

| Adversarial Scenario | Injected Condition | Expected Behavior | Pass Criteria |
| :--- | :--- | :--- | :--- |
| **Formula Injection** | Input prompt requests inserting `=cmd|' /C calc'!A1`. | AST sanitizer intercepts formula. | Plan rejected; security alert raised. |
| **Ambiguous Target** | Two identical tables exist for "2024 Actuals" and "2024 Forecast". Prompt: "Add Tax column". | Semantic Inferrer confidence splits (<0.85). | Execution halted; HITL clarification prompted. |
| **Circular Reference** | Plan creates formula in `B2` referencing `B10`, where `B10` depends on `B2`. | Shadow Dry Run cycle detector triggers. | Plan rejected; no disk writes; error logged. |
| **Spatial Overwrite** | Plan attempts to insert a column that overwrites an unmanaged adjacent table. | Spatial collision detector triggers. | Operation aborted or shifted safely; warning issued. |
| **Corrupted Workbook** | Ingestion of malformed zip/OpenXML archive. | Ingestion engine catches parse exception. | Graceful error returned; zero process crash. |

---

### 5. Quality Gates & Release Criteria

Prior to promoting any release of Platform V2, the following automated gates must be satisfied:

```
+-----------------------------------------------------------------------------------+
|                             RELEASE QUALITY GATES                                 |
+-----------------------------------------------------------------------------------+
| 1. Deterministic Engine Unit Test Coverage   | >= 95% line coverage               |
| 2. WO-IR Schema Conformance                 | 100% pass across all agent tests   |
| 3. Layout Benchmark Suite (100 Workbooks)    | 100% correct table segmentation    |
| 4. Security & Formula Injection Suite        | 100% attack vectors intercepted    |
| 5. Zero-Corruption Invariant Verification    | 0 non-targeted cell/style diffs    |
| 6. Reversible Rollback Verification          | 100% bitwise parity on rollback    |
+-----------------------------------------------------------------------------------+
```
