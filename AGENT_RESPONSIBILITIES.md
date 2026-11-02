# Autonomous Excel Intelligence Platform V2
## Specialized Agent Responsibilities & Contracts (AGENT_RESPONSIBILITIES.md)

---

### 1. Agent Design Principles

Every intelligence agent within Platform V2 adheres to five fundamental software engineering principles:
1. **Single Responsibility**: Each agent owns exactly one cognitive domain.
2. **Stateless Deliberation**: Agents do not maintain internal mutable state across requests; all context is provided in the invocation payload.
3. **Strict Input/Output Contracts**: All communication occurs via rigid, schema-validated JSON payloads. Markdown, free-text or unstructured code responses are rejected.
4. **LLM Agnosticism & Mockability**: Agent interfaces are decoupled from specific model backends, allowing deterministic test harnesses to mock responses.
5. **Zero Domain Knowledge**: No agent may contain hardcoded business vocabulary, predefined accounting templates, or domain-specific heuristics.

---

### 2. Comprehensive Agent Catalog

```
+-----------------------------------------------------------------------------------+
|                        INTELLIGENCE AGENT ROSTER                                  |
+-----------------------------------------------------------------------------------+
| 1. Cognitive Orchestrator Agent       | Global coordination & context assembly    |
| 2. Structural Topology Profiler Agent | Sheet segmentation & table boundary agent  |
| 3. Semantic & Schema Inferrer Agent   | Dynamic typing, entities, & relationships |
| 4. Intent Grounding Agent             | Maps user goals onto discovered topology   |
| 5. Formula Dependency Graph Agent     | Parses formula ASTs & tracks dependencies  |
| 6. Plan Synthesizer & IR Agent        | Generates declarative WO-IR instructions  |
| 7. Risk & Ambiguity Sentinel Agent    | Confidence scoring & HITL escalation      |
| 8. Post-Execution Verification Agent  | Audit delta analysis & invariant checking |
+-----------------------------------------------------------------------------------+
```

---

### 3. Detailed Agent Specifications

#### 3.1 Cognitive Orchestrator Agent
* **Role**: Primary coordinator of system intelligence.
* **Responsibilities**:
  - Receives initial user directives and pairs them with parsed workbook topologies.
  - Formulates the meta-plan and sequences agent invocations.
  - Aggregates multi-agent discoveries into a unified Grounded Context Model.
  - Handles clarifications from and responses to the human user.
* **Input Schema**:
  ```json
  {
    "user_instruction": "string",
    "workbook_id": "string",
    "execution_session_id": "string",
    "interaction_history": ["array of prior steps/clarifications"]
  }
  ```
* **Output Schema**:
  ```json
  {
    "meta_plan_id": "string",
    "pipeline_stages": ["array of scheduled agent tasks"],
    "requires_clarification": "boolean",
    "clarification_prompt": "string | null"
  }
  ```

#### 3.2 Structural Topology Profiler Agent
* **Role**: Visual and spatial analyzer of the raw cell grid.
* **Responsibilities**:
  - Ingests raw sparse cell coordinate maps (coordinates, basic value types, styles).
  - Performs connected-component spatial clustering to isolate independent data blocks.
  - Resolves multi-tier and hierarchical headers into full column paths.
  - Identifies transposed tables, matrix grids, and summary row/column vectors.
  - Detects merged cell regions and maps logical spans without loss of value anchors.
* **Input Schema**:
  ```json
  {
    "sheet_name": "string",
    "sheet_index": 0,
    "dimensions": {"max_row": 0, "max_col": 0},
    "non_empty_cells": [
      {"coord": "A1", "type": "string|number|formula|blank", "is_merged": false, "style_signature": "string"}
    ]
  }
  ```
* **Output Schema**:
  ```json
  {
    "detected_blocks": [
      {
        "block_id": "blk_001",
        "bounding_box": {"start_col": 1, "start_row": 1, "end_col": 8, "end_row": 150},
        "orientation": "VERTICAL | HORIZONTAL | MATRIX",
        "header_hierarchy": [
          {"level": 0, "row": 1, "labels": ["..."]},
          {"level": 1, "row": 2, "labels": ["..."]}
        ],
        "data_boundary": {"start_row": 3, "end_row": 149},
        "summary_vector": {"has_summary_row": true, "row": 150, "formula_signatures": ["SUM"]}
      }
    ],
    "unstructured_cells": ["array of standalone comment or metadata cell coordinates"]
  }
  ```

#### 3.3 Semantic & Schema Inferrer Agent
* **Role**: Discovers empirical semantics, data types, and entity relationships.
* **Responsibilities**:
  - Evaluates column/row data distributions using statistical profiling.
  - Deduces fine-grained semantic types (e.g., continuous numeric, discrete code, temporal date, currency, categorical text).
  - Identifies unique keys and candidate primary keys within detected blocks.
  - Performs cross-block and cross-sheet value overlap analysis to uncover foreign key candidates and dimensional relationships.
  - Assigns semantic roles to discovered blocks (e.g., Fact Table, Dimension Lookup, Pivot Aggregation, Parameter Block).
* **Input Schema**:
  ```json
  {
    "detected_blocks": ["output from Structural Topology Profiler"],
    "sample_data": {"block_id": [{"col": 1, "values": ["..."], "null_count": 0}]}
  }
  ```
* **Output Schema**:
  ```json
  {
    "block_semantics": [
      {
        "block_id": "blk_001",
        "semantic_role": "TRANSACTION_FACT | DIMENSION_LOOKUP | SUMMARY_MATRIX",
        "columns": [
          {
            "col_index": 1,
            "header_label": "string",
            "inferred_type": "INTEGER | DECIMAL | CURRENCY | DATE | CATEGORICAL | IDENTIFIER",
            "is_unique": true,
            "is_candidate_primary_key": true,
            "null_ratio": 0.0
          }
        ],
        "relationships": [
          {
            "foreign_block_id": "blk_002",
            "local_col": 3,
            "foreign_col": 1,
            "match_confidence": 0.96,
            "relationship_type": "MANY_TO_ONE"
          }
        ]
      }
    ]
  }
  ```

#### 3.4 Intent Grounding Agent
* **Role**: Translates human objectives into explicit, topological targets.
* **Responsibilities**:
  - Correlates the entities and metrics mentioned in the user prompt with the discovered semantic schema.
  - Establishes unambiguous target blocks, target columns, and intended transformations.
  - Identifies semantic gaps or ambiguities where the user's directive cannot be uniquely mapped.
* **Input Schema**:
  ```json
  {
    "user_instruction": "string",
    "grounded_schema": "output from Semantic & Schema Inferrer"
  }
  ```
* **Output Schema**:
  ```json
  {
    "grounded_operations": [
      {
        "intent_type": "CALCULATE_COLUMN | FILTER_DATA | GENERATE_SUMMARY | INSERT_METRIC",
        "target_block_id": "blk_001",
        "target_fields": ["..."],
        "semantic_expression": "string",
        "ambiguity_detected": false
      }
    ],
    "unresolved_ambiguities": ["array of descriptions if any"]
  }
  ```

#### 3.5 Formula Dependency Graph Agent
* **Role**: Graph and AST expert for Excel formula calculations.
* **Responsibilities**:
  - Parses existing formulas across all sheets into Abstract Syntax Trees (ASTs).
  - Constructs a global Directed Acyclic Graph (DAG) of cell and range dependencies.
  - Simulates the downstream impact of proposed modifications on dependent calculation chains.
  - Checks for potential circular reference loops (`#CIRCULAR!`) or broken references (`#REF!`).
* **Input Schema**:
  ```json
  {
    "sheet_formulas": [
      {"cell": "D2", "formula": "=B2*C2"},
      {"cell": "D150", "formula": "=SUM(D2:D149)"}
    ],
    "proposed_modifications": ["array of target ranges to be inserted/updated"]
  }
  ```
* **Output Schema**:
  ```json
  {
    "dependency_graph_summary": {"total_nodes": 150, "root_cells": ["..."], "leaf_cells": ["..."]},
    "conflict_analysis": {
      "has_circular_dependency": false,
      "broken_references": [],
      "impacted_dependents_count": 1
    }
  }
  ```

#### 3.6 Plan Synthesizer & IR Agent
* **Role**: Compiler of cognitive intentions into deterministic execution instructions.
* **Responsibilities**:
  - Generates the formal, declarative Workbook Operation Intermediate Representation (WO-IR).
  - Encapsulates discrete steps: range shifts, cell value assignments, formula insertions, style copying.
  - Emits explicit pre-conditions and post-conditions for deterministic verification.
* **Input Schema**:
  ```json
  {
    "grounded_operations": "output from Intent Grounding Agent",
    "dependency_analysis": "output from Formula Dependency Graph Agent",
    "topology_model": "output from Structural Topology Profiler"
  }
  ```
* **Output Schema**: Formal WO-IR JSON Document (defined in `DATA_FLOW_SPECIFICATION.md`).

#### 3.7 Risk & Ambiguity Sentinel Agent
* **Role**: Safety gatekeeper and human-escalation evaluator.
* **Responsibilities**:
  - Calculates a holistic Risk Index for the proposed WO-IR plan based on:
    - Blast radius (number of modified cells).
    - Destructive actions (overwriting existing non-empty cells vs. inserting into vacant space).
    - Statistical inference confidence (certainty of column identity and relationships).
    - Formula criticality (modification of formulas with high downstream fan-out).
  - Flags mandatory Human-in-the-Loop approval requests whenever risk exceeds thresholds.
* **Input Schema**:
  ```json
  {
    "candidate_plan": "WO-IR document",
    "inference_confidence_scores": {"semantic_score": 0.82, "intent_score": 0.95},
    "impact_analysis": {"cells_modified": 148, "destructive_overwrites": 0}
  }
  ```
* **Output Schema**:
  ```json
  {
    "risk_score": 0.35,
    "escalation_required": true,
    "escalation_reasons": ["Semantic confidence for target column falls below 0.85 threshold (0.82)"],
    "human_review_payload": {
      "summary_for_human": "We identified 'Col E' as the target for margin calculations with 82% confidence based on adjacent values.",
      "proposed_diff_preview": {"cell_range": "E2:E149", "operation": "Inject formula =D2/C2"},
      "alternatives_considered": ["Col F (Net Margin)"]
    }
  }
  ```

#### 3.8 Post-Execution Verification Agent
* **Role**: Auditor of committed changes.
* **Responsibilities**:
  - Ingests the execution delta produced by the Deterministic Execution Layer.
  - Verifies that post-conditions and invariants defined in the WO-IR hold true.
  - Confirms untouched regions remain bitwise identical to their pre-execution state.
  - Formulates natural language explanations of executed operations for the user.
* **Input Schema**:
  ```json
  {
    "original_state_hash": "string",
    "executed_wo_ir": "WO-IR document",
    "execution_delta_ledger": "delta summary from DEL"
  }
  ```
* **Output Schema**:
  ```json
  {
    "verification_status": "PASSED | FAILED",
    "invariant_violations": [],
    "user_summary_report": "Successfully added Margin calculation column to Table 1 across rows 2-149. Existing formatting and total formulas in row 150 preserved."
  }
  ```

---

### 4. Agent Isolation & Mocking Standards

To enable independent unit testing without live LLM calls:
- Every agent must have a deterministic Mock Fixture covering:
  1. Standard clean scenarios.
  2. Highly distorted/jagged inputs.
  3. Contradictory/adversarial inputs.
- Test suites must validate that agents adhere strictly to JSON schemas using automated JSON Schema validators.
- No agent may call another agent directly; all communication is routed through the Cognitive Orchestrator or the test harness.
