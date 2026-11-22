# Autonomous Excel Intelligence Platform V2
## Architectural Constraints & Invariants (ARCHITECTURAL_CONSTRAINTS.md)
### Status: Proposed Architectural Draft (Reconciled with Baseline Constraints & Invariants)

---

### 1. Inviolable System Invariants ("The Golden Rules")

The following constraints are non-negotiable architectural invariants of Platform V2:

```
+-----------------------------------------------------------------------------------+
|                        THE INVIOLABLE SYSTEM INVARIANTS                           |
+-----------------------------------------------------------------------------------+
| INVARIANT 1: DECLARATIVE EXECUTION ISOLATION                                      |
| Cognitive tier is mathematically prohibited from directly writing to workbook     |
| files or executing arbitrary scripts. All mutations must be expressed             |
| exclusively as schema-validated Intermediate Representation (WO-IR).              |
+-----------------------------------------------------------------------------------+
| INVARIANT 2: ZERO-DOMAIN HARDCODING                                               |
| No component may contain hardcoded sheet names ("Sheet1", "Data", "Summary"),     |
| column names ("Date", "ID", "Amount"), or domain templates. All structural and    |
| semantic properties must be derived from empirical evidence.                      |
+-----------------------------------------------------------------------------------+
| INVARIANT 3: LOSSLESS OPENXML PRESERVATION                                        |
| Distinguishes semantic preservation from bitwise preservation. Under experimentally|
| verified local NTFS conditions, non-targeted package parts (vbaProject.bin,        |
| drawings, shapes, slicers, media, themes, unedited sheets) are bitwise preserved.  |
| Targeted sheets undergo schema-conformant re-serialization, semantically           |
| preserving cell formatting, palettes, borders, and comments. Universal byte-for-   |
| byte preservation across arbitrary package features is explicitly disclaimed.     |
+-----------------------------------------------------------------------------------+
| INVARIANT 4: DETERMINISTIC MUTATION EXECUTION                                     |
| The execution of a validated WO-IR package against an identical workbook state     |
| must be 100% reproducible and deterministic, producing identical targeted changes.|
+-----------------------------------------------------------------------------------+
| INVARIANT 5: CONTEXT-GATED HUMAN AUTHORITY (HITL)                                 |
| Any operation with inference state != INFERRED (including AMBIGUOUS all-null      |
| marker columns), support S < 0.70, destructive overwrites, or boundary collisions |
| must halt for explicit human approval.                                            |
+-----------------------------------------------------------------------------------+
| INVARIANT 6: THREE-TIER RECOVERY & DURABILITY                                     |
| Durability must follow COR-01 7-step sequence (pre-state backup .bak, durable WAL |
| intent, staged write, fsync, atomic swap, parent-dir durability, WAL commit) with |
| transactional undo via WAL deltas and pre-state .bak recovery on local NTFS.      |
+-----------------------------------------------------------------------------------+
```

---

### 2. Architectural Boundary Constraints

#### 2.1 Cognitive Tier Constraints
1. **Candidate C Topology (No LLM Swarm):**
   The cognitive architecture is strictly Candidate C (Two-Tier Model: Deterministic Core + Tool-Augmented Orchestrator). It does not deploy an uncoordinated multi-agent LLM swarm.
2. **No Code Generation for Execution:**
   The cognitive orchestrator must never emit Python, VBA, or shell code intended for execution. Its sole mutation output is the declarative WO-IR JSON contract.
3. **Context Window Protection:**
   Raw tabular matrices are never sent directly to LLM context. Token routing must use progressive topological summarization (~500 tokens) and targeted 5-row sampling.

#### 2.2 Execution Tier Constraints
1. **Deterministic Sandboxing:**
   Tier 3 DEL executes in an isolated environment with zero dynamic `eval()` execution. DEL is a sandboxed Python engine with targeted Rust extensions where specified.
2. **Sampled Memory Guard:**
   Working set memory must respect the 235,000,000 bytes warning tripwire (`WARNING_TRIPWIRE_WORKING_SET_BYTES`), 250,000,000 bytes typed hard-error ceiling (`HARD_CEILING_WORKING_SET_BYTES`), and 8,000,000 bytes burst allocation delta trigger (`EVENT_DRIVEN_DELTA_THRESHOLD_BYTES = 8_000_000` in `crates/excel_intel_rs/src/memory_guard.rs`) via M02 sampled dual-cadence telemetry (sampled every 1,000 rows or on attributable $\ge 8,000,000\text{ bytes}$ burst deltas; not an instantaneous OS-level RSS cap).
3. **Formula Allowlist Policy Layer:**
   Separate deterministic allowlisting layer enforces protocol blacklisting (external links, DDE, dangerous functions) and function whitelisting prior to execution.
4. **Prompt 4 Graph Requirements:**
   Formula range references must be preserved as bounded range-nodes / hyperedges to prevent graph combinatorial explosion. Precedent extraction belongs exclusively to Prompt 4.

---

### 3. Explicit Status of Key Architectural Decisions

#### Decision 1: Cognitive Orchestration Topology
* **Status:** **RESOLVED & RECONCILED (Candidate C Adopted)**
* **Resolution:** In accordance with ADR-006, PDR-06, and EXP-09, Candidate C (Two-Tier Model: Deterministic Core + Tool-Augmented Orchestrator) is the binding architectural model. The 8 functional domains are structured as modular analytical facades in Tier 1, coordinated by one unified reasoning orchestrator in Tier 2.

#### Decision 2: Formula Handling, Parsing Scope & Allowlisting
* **Status:** **RESOLVED & RECONCILED (M05 Prompt Boundaries Honored)**
* **Resolution:** M05 Prompt 3 (Lexer/Parser/AST) is purely syntactic, emitting root statuses `PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, or `PARSE_ERROR`. Precedent extraction belongs exclusively to Prompt 4. Formula security allowlisting is an execution-layer policy in Tier 3 DEL. Deferred recalculation (`<calcPr fullCalcOnLoad="1"/>`) is maintained per ADR-003.

#### Decision 3: Type Inference Semantics & Scoring
* **Status:** **RESOLVED & RECONCILED (M05 FR-1 Baseline Honored)**
* **Resolution:** `UNKNOWN` is strictly reserved for $N_{\text{pop}} = 0$ (100% genuinely empty). All-null-marker columns (`N/A`, `-`, `None`) are `AMBIGUOUS`. Heuristic support score $S$ is computed strictly via approved M05 FR-1.6 formula. Described as heuristic score, not probability.

#### Decision 4: WAL Ordering & Durability Protocol
* **Status:** **RESOLVED & RECONCILED (COR-01 Sequencing Honored)**
* **Resolution:** Durable transaction intent (`INTENT_RECORDED`) must strictly precede mutation. Durability follows the authoritative COR-01 sequence: pre-state `.bak` establishment $\rightarrow$ durable WAL intent flushed $\rightarrow$ staged write in `.staging/<session_id>/` $\rightarrow$ file fsync $\rightarrow$ atomic swap (`os.replace`) $\rightarrow$ parent-directory durability step where supported by the operating system (explicitly noting Windows NTFS does not provide POSIX directory `fsync()` and NTFS journal persistence is not an equivalent durability primitive, leaving directory metadata subject to OS flushing semantics) $\rightarrow$ WAL commit marking.

#### Decision 5: Non-Local / Cloud Filesystem Durability (OneDrive / SMB)
* **Status:** **PROPOSED / REQUIRES HUMAN APPROVAL**
* **Context:** Atomic rename (`os.replace`) and fsync guarantees are experimentally established on local NTFS (EXP-06), but SMB shares and cloud sync folders (OneDrive) exhibit asynchronous lock-stealing and eventual consistency anomalies.
* **Resolution:** Open decision requiring human review and empirical validation prior to authorizing non-local targets.

#### Decision 6: Execution Sandbox Virtualization Technology
* **Status:** **PROPOSED / REQUIRES HUMAN APPROVAL**
* **Context:** Evaluating whether DEL sandboxing requires OS-level process isolation (e.g. Linux cgroups/seccomp, Windows AppContainer) or in-process capability boundaries.
* **Resolution:** Open decision requiring human review and deployment architecture sign-off.

#### Decision 7: Tier 3 Outbound Network Access Policy
* **Status:** **PROPOSED / REQUIRES HUMAN APPROVAL**
* **Context:** Evaluating whether zero-outbound network access is a hardware/container-enforced invariant (Option A) or an application-level deployment policy where DEL includes no networking code (Option B).
* **Resolution:** Open decision requiring human review and deployment architecture sign-off.

#### Decision 8: Autonomous (Tier 0) Mutation Thresholds
* **Status:** **PROPOSED / REQUIRES HUMAN APPROVAL**
* **Context:** Proposed autonomous execution thresholds ($H \ge 0.95, S \ge 0.90$) for Tier 0 non-destructive appends require explicit human approval; current approved baseline requires human review for consolidation operations.
* **Resolution:** Open decision requiring human review and sign-off.
