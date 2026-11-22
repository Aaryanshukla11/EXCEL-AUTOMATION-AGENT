# Autonomous Excel Intelligence Platform V2
## Functional Roles & Component Contracts (AGENT_RESPONSIBILITIES.md)
### Status: Proposed Architectural Draft (Reconciled with Candidate C & M01–M05 Modular Facades)

---

### 1. Architectural Reconcilement: From Swarm to Decoupled Facades

In strict accordance with ADR-006 (Candidate C: Two-Tier Model), the platform does **not** deploy an uncoordinated multi-agent swarm of 8 independent LLM instances. Instead, the cognitive and analytical domains identified in V2 are realized as **strongly-typed modular analytical facades** in Tier 1, orchestrated by a single **Unified Cognitive Orchestrator** in Tier 2.

```
+-----------------------------------------------------------------------------------+
|                        MODULAR ARCHITECTURAL FACADES                              |
+-----------------------------------------------------------------------------------+
| 1. Cognitive Orchestrator (Tier 2)     | Meta-planning, context routing & WO-IR   |
| 2. Spatial Topology Facade (Tier 1)    | M04 2D table & zone segmentation         |
| 3. Semantic Profiler Facade (Tier 1)   | M05 Prompt 2 typing & support scores     |
| 4. Formula AST Facade (Tier 1)         | M05 Prompt 3 EBNF lexer/parser & AST     |
| 5. Formula DAG Facade (Tier 1)         | M05 Prompt 4 DAG, precedents & range-nodes|
| 6. Downstream Manifest Adapter (Tier 1)| Proposed M01 DiscoveryManifest bridge    |
| 7. Candidate Key Facade (Tier 1)       | PDR-04 uniqueness & duplicate evaluation |
| 8. Safety & Policy Gate (Tier 3)       | Formula allowlisting & HITL evaluator    |
| 9. Transactional Mutator (Tier 3)      | COR-01 durability commit & WAL sequencing|
| 10. Post-Execution Auditor (Tier 3)    | Invariant verification & delta reporting |
+-----------------------------------------------------------------------------------+
```

---

### 2. Detailed Component Contracts & Schemas

#### 2.1 Unified Cognitive Orchestrator (Tier 2)
* **Execution Paradigm:** Single-turn tool-augmented reasoning engine.
* **Responsibilities:**
  - Formulates execution plans based on user natural language directives.
  - Queries Tier 1 facades via strongly-typed read-only inspection tools.
  - Emits schema-validated WO-IR plans using strictly discriminated operation primitives.
  - Formats natural language explanations and side-by-side diff previews for human review.

#### 2.2 Spatial Topology Facade (M04 Baseline)
* **Execution Paradigm:** Deterministic spatial bounding-box analyzer.
* **Responsibilities:**
  - Consumes raw cell coordinates from M02 streaming reader.
  - Emits `SpatialAnalysisReport` containing `SpatialTableRegion` entities.
  - Resolves multi-tier stacked headers and compound header paths.
  - Identifies `SemanticZoneType.BODY` bounding boxes.

#### 2.3 Semantic Profiler Facade (M05 Prompt 2 Baseline)
* **Execution Paradigm:** Deterministic statistical token classifier.
* **Responsibilities:**
  - Samples cells strictly within `SemanticZoneType.BODY` (budget $\le 10,000$ cells).
  - Evaluates cell tokens across semantic types (integer, decimal, currency, date, boolean, string).
  - Assigns explicit inference states:
    - `INFERRED`: Confident type inference ($H \ge 0.80, S \ge 0.70$).
    - `UNKNOWN`: Column contains zero populated cells ($N_{\text{pop}} = 0$; 100% genuinely blank).
    - `AMBIGUOUS`: Bimodal distributions, competing types, low homogeneity ($H < 0.80$), or columns composed entirely of null markers (`N/A`, `-`, `None`).
    - `INSUFFICIENT_DATA`: Populated cell count is below statistical threshold ($1 \le N_{\text{pop}} < 5$).
  - Calculates homogeneity ratio $H$ and heuristic support score $S$ strictly using approved M05 FR-1.6 formula. Heuristic support score $S$ is explicitly documented as a token frequency statistic, never a probability.
* **Contract Output:**
  ```python
  class ColumnInferenceResult(BaseModel):
      index: int
      header_name: str
      inference_state: InferenceState  # INFERRED, UNKNOWN, AMBIGUOUS, INSUFFICIENT_DATA
      candidate_type: Optional[ColumnType]
      homogeneity_ratio: float
      heuristic_support_score: float  # S in [0.0, 1.0] (heuristic statistic, not probability)
      nullability_ratio: float
      requires_human_review: bool
  ```

#### 2.4 Formula AST Facade (M05 Prompt 3 Baseline)
* **Execution Paradigm:** Pure-Python lexical analyzer and operator-precedence recursive-descent parser.
* **Responsibilities:**
  - Parses OpenXML `<f>` strings into frozen Pydantic v2 ASTs (`BaseASTNode`).
  - Emits explicit root parse status (`FormulaParseStatus`):
    - `PARSED_COMPLETE`: Complete valid AST.
    - `UNSUPPORTED_SYNTAX`: Recognized unsupported construct (`UnsupportedFormulaNode`, e.g. dynamic spill `#`, `LAMBDA`).
    - `PARSE_ERROR`: Syntactic malformation (`UnparsedFormulaNode`).
  - Category A/B/C syntax classifications are subordinate tags only.
  - Emits typed AST and reference nodes (`CellReferenceNode`, `RangeReferenceNode`, `StructuredReferenceNode`, `FunctionCallNode`).
  - **Precedent Extraction Scope:** Pure syntactic analysis only; precedent extraction is strictly deferred to Prompt 4.
  - Does NOT enforce security authorization or execute formulas. Functions that follow valid function grammar (including unallowlisted functions) parse with root status `PARSED_COMPLETE`.

#### 2.5 Formula DAG & Precedent Facade (M05 Prompt 4 Design Scope)
* **Execution Paradigm:** Static directed calculation dependency graph builder (NetworkX).
* **Responsibilities:**
  - Ingests AST reference nodes produced by Prompt 3 to extract precedents.
  - Preserves bounded range-nodes / hyperedges for range references (e.g. `A1:A10000`) to prevent graph edge explosions.
  - Executes Tarjan's strongly connected components (SCC) algorithm for static circular reference detection.
  - Catalogs volatile functions (`NOW`, `TODAY`, `OFFSET`, `INDIRECT`).

#### 2.6 Downstream Manifest Integration Adapter (Proposed Integration Contract)
* **Execution Paradigm:** Structural data transformer.
* **Responsibilities:**
  - Bridges M04 spatial tables, M05 column typing results, and M05 formula DAG metadata into canonical M01 `DiscoveryManifest` and `TableMetadata` structures for downstream consolidation.

#### 2.7 Candidate Key & Collision Facade (Tier 1 / PDR-04)
* **Execution Paradigm:** Relational constraint analyzer.
* **Responsibilities:**
  - Evaluates column value uniqueness within table bounds.
  - Identifies composite candidate keys and detects duplicate records between source workbooks and existing tables.

#### 2.8 Safety, Allowlist & HITL Evaluator (Tier 3 DEL)
* **Execution Paradigm:** Rule-based deterministic gatekeeper.
* **Responsibilities:**
  - Enforces deterministic formula allowlist security policy (rejecting external links, DDE, and unwhitelisted functions). Functions that parse syntactically but violate policy are rejected here.
  - Evaluates WO-IR plans against escalation rules:
    - Triggers mandatory review if column state is `AMBIGUOUS` (including all-null-marker columns), `INSUFFICIENT_DATA`, or `UNKNOWN`.
    - Triggers mandatory review if support score $S < 0.70$ or homogeneity $H < 0.80$.
    - Triggers mandatory review on destructive overwrites or ADR-005 boundary collisions.
    - Triggers mandatory review if any proposed Tier 0 autonomous execution is submitted (governed by Decision 8).
  - Formats structured side-by-side approval diff cards.

#### 2.9 Transactional Mutator (Tier 3 DEL)
* **Execution Paradigm:** Sandboxed OpenXML package manipulator.
* **Responsibilities:**
  - Executes WO-IR operations deterministically.
  - Applies COR-01 durability sequence:
    1. Establish pre-state backup snapshot (`.bak`) on local filesystem.
    2. Write durable WAL transaction intent (`INTENT_RECORDED`) and flush to disk.
    3. Stage copy in `.staging/<session_id>/`.
    4. Fsync staged file data and metadata via `fsync()`.
    5. Atomic replacement (`os.replace` on same volume).
    6. Parent-directory durability step where supported by the operating system (noting Windows NTFS does not provide POSIX directory `fsync()`, and NTFS journal persistence does not provide an equivalent guaranteed durability primitive, leaving directory entry metadata subject to OS flushing semantics).
    7. Mark WAL transaction `COMMITTED`.
  - Preserves untouched OpenXML package parts (`vbaProject.bin`, drawings, slicers, media, themes, unedited sheets) bitwise under experimentally verified local NTFS conditions, while modified sheets undergo schema-conformant semantic re-serialization. Universal bitwise preservation is disclaimed.

#### 2.10 Post-Execution Auditor (Tier 3)
* **Execution Paradigm:** Post-flight verification engine.
* **Responsibilities:**
  - Verifies that post-conditions and invariants defined in WO-IR hold true.
  - Validates that non-targeted cell hashes remain identical.
  - Confirms `<calcPr fullCalcOnLoad="1"/>` is set for formula modifications.
