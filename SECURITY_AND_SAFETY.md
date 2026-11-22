# Autonomous Excel Intelligence Platform V2
## Security, Safety & Governance Specification (SECURITY_AND_SAFETY.md)
### Status: Proposed Architectural Draft (Reconciled with Policy Layer & Allowlisting Separation)

---

### 1. Threat Modeling & Attack Surfaces

Spreadsheets present complex security vectors including formula injection, malicious macros, dynamic data exchanges (DDE), and prompt injection via untrusted cell contents.

```
+-----------------------------------------------------------------------------------+
|                        SECURITY THREAT MATRIX & MITIGATIONS                       |
+-----------------------------------------------------------------------------------+
| THREAT VECTOR                | ATTACK SCENARIO             | MITIGATION MECHANISM |
+------------------------------+-----------------------------+----------------------+
| 1. Formula Injection (CSV/XLS)| User or file injects        | DEL Security Policy  |
|    Injection / DDE Execution | `=cmd|' /C calc'!A1`        | Layer rejects DDE &  |
|                              | to execute OS commands.     | unapproved protocols.|
+------------------------------+-----------------------------+----------------------+
| 2. Prompt Injection          | Cell strings contain        | Strict separation of |
|    via Cell Content          | instructions to override    | system instructions  |
|                              | safety constraints.         | from data tokens.    |
+------------------------------+-----------------------------+----------------------+
| 3. Malicious Macro Execution | Macro code (`.xlsm`)        | Quarantine mode: VBA |
|                              | executed during processing. | streams preserved as |
|                              |                             | opaque blobs; never  |
|                              |                             | executed by engine.  |
+------------------------------+-----------------------------+----------------------+
| 4. Unintended Data Overwrite | Hallucinated range overwrites| Spatial collision    |
|                              | adjacent summary formulas.  | detector & shadow run|
|                              |                             | intercept overwrite. |
+------------------------------+-----------------------------+----------------------+
| 5. Resource Exhaustion / DoS | Bomb-style sparse sheets    | Sampled dual-cadence |
|                              | referencing row 1,048,576.  | memory guard (M02:   |
|                              |                             | 235M/250M bounds,    |
|                              |                             | 8M burst delta).     |
+------------------------------+-----------------------------+----------------------+
```

---

### 2. Declarative Execution Isolation & Network Policy Status

The system boundary between the cognitive orchestrator and the physical spreadsheet is defined as **Declarative Execution Isolation**:

* **No Direct File Write Authority:** The LLM reasoning tier has zero file system write handles and cannot call OS write primitives.
* **No Code Generation for Execution:** The LLM does not write Python, VBA, or shell scripts that are executed against the file. It generates exclusively declarative WO-IR JSON payloads.
* **Execution Boundary:** All file modifications are performed exclusively by the sandboxed deterministic execution layer (Tier 3) within an ephemeral scratch workspace.

> [!NOTE]
> **UNRESOLVED ARCHITECTURAL DECISION: TIER 3 NETWORK ISOLATION POLICY (DECISION 7)**
> - **Current Status:** **PROPOSED / REQUIRES HUMAN APPROVAL**
> - **Trade-Off:**
>   - *Option A (Mandatory Invariant):* Hardware or container-level zero-outbound socket restriction strictly enforced on the Tier 3 runtime environment.
>   - *Option B (Deployment Policy):* Application-level isolation (DEL includes no networking code) with host or cloud network egress policies configured at deployment time.
> - **Resolution:** Requires explicit project owner sign-off prior to production authorization.

---

### 3. Formula Security Allowlist Policy Layer

The platform cleanly separates **formula syntax parsing** from **formula security authorization**:

1. **Syntax Parsing Subsystem (M05 Prompt 3):**
   - Syntactically parses formulas into AST representations.
   - Emits explicit root parse status: `PARSED_COMPLETE`, `UNSUPPORTED_SYNTAX`, or `PARSE_ERROR`.
   - Functions that follow standard function syntax (e.g. `CMD(...)` or `WEBSERVICE(...)` or arbitrary custom names) parse with root status `PARSED_COMPLETE`.
   - `UNSUPPORTED_SYNTAX` is reserved for recognized unsupported syntax (dynamic array spill `#`, `LAMBDA` parameters). Unwhitelisted functions are NOT classified as unsupported parser syntax.
2. **Deterministic Security Policy Layer (Tier 3 DEL):**
   - Evaluates syntactically parsed formulas against security allowlists before execution:
     - **Protocol Blacklist:** External workbook links (`='[external.xlsx]Sheet1'!$A$1`), DDE links (`=cmd|...`), and dynamic web functions (`WEBSERVICE(...)`) are strictly blocked.
     - **Function Allowlist:** Only approved mathematical, statistical, logical, date/time, lookup, and text functions are permitted.
     - **Coordinate Bounds Enforcement:** All cell and range references must fall strictly within valid Excel bounds ($1 \le \text{col} \le 16384, 1 \le \text{row} \le 1048576$).
   - Any function that is syntactically valid but unallowed is rejected here by policy validation, NOT by the parser.

---

### 4. Human-in-the-Loop (HITL) Governance Tiers

Operations are categorized into three governance tiers based on deterministic risk indicators:

```
+-----------------------------------------------------------------------------------+
|                        HITL OPERATIONAL SAFETY TIERS                              |
+-----------------------------------------------------------------------------------+

  TIER 0: FULL AUTONOMOUS EXECUTION (PROPOSED / REQUIRES HUMAN APPROVAL - DECISION 8)
  - Proposed non-destructive append into existing verified table structures.
  - Proposed thresholds: Target columns have InferenceState = INFERRED, homogeneity H >= 0.95, support S >= 0.90.
  - Zero existing non-empty cell overwrites.
  [Note: Status is PROPOSED and BLOCKED pending explicit Project Owner sign-off on Decision 8.
   Current approved baseline requires mandatory human review for consolidation operations.
   Heuristic support scores are empirical token frequency statistics, never probabilities].

  TIER 1: PASSIVE NOTIFICATION
  - Target columns have InferenceState = INFERRED with 0.80 <= H < 0.95, 0.70 <= S < 0.90.
  - Appending records into pre-existing ListObject tables where schema matches 100%.

  TIER 2: MANDATORY INTERACTIVE APPROVAL GATE (HALT & ESCALATE)
  - Target column InferenceState is AMBIGUOUS (including all-null-marker columns),
    INSUFFICIENT_DATA, or UNKNOWN.
  - Heuristic support score S < 0.70 or homogeneity H < 0.80.
  - Any operation involving overwriting existing non-empty cells or formulas.
  - ADR-005 boundary collisions (appending into plain range with adjacent summary formulas).
  - Creation of new worksheets or structural tables.
```

Heuristic support score $S$ is strictly defined as an empirical token frequency metric, never a probability.

#### 4.1 Interactive Escalation Presentation
When Tier 2 escalation occurs, execution halts and renders an interactive approval diff card:
- Natural language explanation of proposed modification.
- Empirical evidence justifying column/target selection.
- Side-by-side cell diff preview (current values vs. proposed values).
- Alternative interpretations considered.
- Explicit approval, rejection, or instruction refinement options.
