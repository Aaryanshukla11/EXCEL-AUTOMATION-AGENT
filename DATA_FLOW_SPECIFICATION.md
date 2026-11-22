# Autonomous Excel Intelligence Platform V2
## Data Flow & Intermediate Representation Specification (DATA_FLOW_SPECIFICATION.md)
### Status: Proposed Architectural Draft (Reconciled with M01–M05 Contracts & Reconciled Operations)

---

### 1. End-to-End Data Lifecycle

Data progresses through a strictly defined unidirectional pipeline governed by declarative execution isolation and progressive context windowing.

```
+-----------------------------------------------------------------------------------+
|                            END-TO-END DATA PIPELINE                               |
+-----------------------------------------------------------------------------------+

  [Target Workbook (.xlsx / .xlsm)]
          |
          v
  (1. Streaming Parser - M02)       ---> [Sampled Event-Driven Memory Guard (235M/250M)]
          |
          v
  (2. Spatial Segmentation - M04)   ---> [SpatialTableRegions & Semantic Zones]
          |
          v
  (3. Semantic Profiler - M05 P2)   ---> [Column Types, States & Support Scores]
          |
          v
  (4. Formula Lexer/Parser - M05 P3)---> [Typed AST & Ref Nodes (PARSED_COMPLETE..)]
          |
          v
  (5. Dependency DAG - M05 P4)      ---> [Precedents, Static Cycles & Range Hyperedges]
          |
          v
  (6. Proposed M01 Adapter)         ---> [Canonical DiscoveryManifest Object]
          |
          v
  (7. Progressive Context Windowing)---> [Topological Summary (~500 - 1500 tokens)]
          |
          v
  (8. Cognitive Plan Synthesis)     ---> [Workbook Operation IR (WO-IR v2.0)]
          |
          v
  (9. Pre-Execution Safety Gate)    ---> [Discriminated Schema, Allowlist & Shadow Run]
          |                                      |
          | (Escalation Triggered)                v
          +----------------------------> [Side-by-Side Diff Card & Human Approval]
          | (Approved)
          v
  (10. Pre-State Snapshot .bak)     ---> [Atomic Pre-State Snapshot Established]
          |
          v
  (11. WAL Intent Logging)          ---> [Durable INTENT_RECORDED Logged & Flushed]
          |
          v
  (12. Staged Mutation & fsync)     ---> [Written to .staging/ and fsynced]
          |
          v
  (13. Atomic Replacement)          ---> [os.replace on same volume]
          |
          v
  (14. Directory Sync & WAL Commit) ---> [Parent Dir Durability Step + COMMITTED]
```

---

### 2. Progressive Context Windowing Architecture

To prevent saturating LLM context windows on enterprise workbooks (50k–100k rows), raw tabular grids are **never** passed directly to the cognitive orchestrator.

1. **Topological Summary Abstraction (~500 tokens):**
   - Transmits sheet names, dimensions, detected `SpatialTableRegion` bounding boxes.
   - Transmits resolved header hierarchies and inferred semantic roles.
2. **Column Statistical Profiling (~500–1000 tokens):**
   - Transmits column headers, inferred `ColumnType`, `InferenceState`, homogeneity ratio $H$, heuristic support score $S$, and nullability ratio.
3. **Targeted Sub-Windowing (On Demand):**
   - If the orchestrator requires granular cell inspection to disambiguate intent, it queries a targeted window of up to 5 representative sample rows from the `BODY` zone.

---

### 3. Workbook Operation Intermediate Representation (WO-IR Schema v2.0)

The WO-IR is the formal declarative contract emitted by Tier 2 and executed by Tier 3 DEL. All operation primitive schemas are **strictly discriminated** with `additionalProperties: false` to reject unexpected parameters:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WorkbookOperationIntermediateRepresentation",
  "type": "object",
  "required": [
    "ir_version",
    "transaction_id",
    "target_workbook_sha256",
    "pre_conditions",
    "operations",
    "post_conditions"
  ],
  "additionalProperties": false,
  "properties": {
    "ir_version": {"type": "string", "enum": ["2.0"]},
    "transaction_id": {"type": "string", "format": "uuid"},
    "target_workbook_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
    "intent_summary": {"type": "string"},
    "pre_conditions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["condition_type", "target"],
        "additionalProperties": false,
        "properties": {
          "condition_type": {
            "type": "string",
            "enum": ["SHEET_EXISTS", "TABLE_EXISTS", "CELL_IS_EMPTY", "RANGE_HASH_EQUALS", "INFERRED_TYPE_MATCHES"]
          },
          "target": {"type": "string"},
          "expected_value": {}
        }
      }
    },
    "operations": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/WorkbookOperation"
      }
    },
    "post_conditions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["invariant_type", "target"],
        "additionalProperties": false,
        "properties": {
          "invariant_type": {
            "type": "string",
            "enum": ["NO_STATIC_FORMULA_CYCLES", "NON_TARGET_PARTS_UNTOUCHED", "CALC_PR_FULL_CALC_SET"]
          },
          "target": {"type": "string"}
        }
      }
    }
  },
  "$defs": {
    "WorkbookOperation": {
      "type": "object",
      "discriminator": {"propertyName": "primitive"},
      "oneOf": [
        {"$ref": "#/$defs/AppendRowsOp"},
        {"$ref": "#/$defs/InsertColumnOp"},
        {"$ref": "#/$defs/SetCellValueOp"},
        {"$ref": "#/$defs/SetCellFormulaOp"},
        {"$ref": "#/$defs/BatchSetFormulaOp"},
        {"$ref": "#/$defs/ApplyStyleOp"},
        {"$ref": "#/$defs/CreateSheetOp"}
      ]
    },
    "AppendRowsOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name", "target_table", "rows"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "APPEND_ROWS"},
        "sheet_name": {"type": "string"},
        "target_table": {"type": "string"},
        "rows": {
          "type": "array",
          "items": {"type": "array", "items": {}}
        }
      }
    },
    "InsertColumnOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name", "target_table", "col_index", "header_name"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "INSERT_COLUMN"},
        "sheet_name": {"type": "string"},
        "target_table": {"type": "string"},
        "col_index": {"type": "integer", "minimum": 1, "maximum": 16384},
        "header_name": {"type": "string"}
      }
    },
    "SetCellValueOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name", "cell_coord", "value"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "SET_CELL_VALUE"},
        "sheet_name": {"type": "string"},
        "cell_coord": {"type": "string", "pattern": "^\\$?[A-Z]{1,3}\\$?[1-9][0-9]{0,6}$"},
        "value": {}
      }
    },
    "SetCellFormulaOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name", "cell_coord", "formula"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "SET_CELL_FORMULA"},
        "sheet_name": {"type": "string"},
        "cell_coord": {"type": "string", "pattern": "^\\$?[A-Z]{1,3}\\$?[1-9][0-9]{0,6}$"},
        "formula": {"type": "string", "pattern": "^="}
      }
    },
    "BatchSetFormulaOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name", "target_range", "formula_template"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "BATCH_SET_FORMULA"},
        "sheet_name": {"type": "string"},
        "target_range": {"type": "string", "pattern": "^\\$?[A-Z]{1,3}\\$?[1-9][0-9]{0,6}:\\$?[A-Z]{1,3}\\$?[1-9][0-9]{0,6}$"},
        "formula_template": {"type": "string", "pattern": "^="}
      }
    },
    "ApplyStyleOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name", "target_range"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "APPLY_STYLE"},
        "sheet_name": {"type": "string"},
        "target_range": {"type": "string"},
        "style_source_cell": {"type": "string"},
        "style_properties": {"type": "object"}
      }
    },
    "CreateSheetOp": {
      "type": "object",
      "required": ["op_id", "primitive", "sheet_name"],
      "additionalProperties": false,
      "properties": {
        "op_id": {"type": "string"},
        "primitive": {"type": "string", "const": "CREATE_SHEET"},
        "sheet_name": {"type": "string", "minLength": 1, "maxLength": 31}
      }
    }
  }
}
```

#### 3.1 Strict Validation Examples

##### Valid Operation Example 1 (`SET_CELL_FORMULA`):
```json
{
  "op_id": "op_001",
  "primitive": "SET_CELL_FORMULA",
  "sheet_name": "Sheet1",
  "cell_coord": "D2",
  "formula": "=B2*C2"
}
```
*Validation Result:* **PASS** (Matches `$defs/SetCellFormulaOp`; all required fields present; `additionalProperties: false` satisfied).

##### Valid Operation Example 2 (`CREATE_SHEET`):
```json
{
  "op_id": "op_002",
  "primitive": "CREATE_SHEET",
  "sheet_name": "Q3_Summary"
}
```
*Validation Result:* **PASS** (Matches `$defs/CreateSheetOp`; correctly requires only `op_id`, `primitive`, and `sheet_name`; no irrelevant coordinate or range properties required).

##### Invalid Operation Example (Unexpected Property):
```json
{
  "op_id": "op_003",
  "primitive": "SET_CELL_VALUE",
  "sheet_name": "Sheet1",
  "cell_coord": "A1",
  "value": 100,
  "unexpected_extra_property": "MALICIOUS_INJECTION"
}
```
*Validation Result:* **FAIL** (Rejection: `unexpected_extra_property` violates `additionalProperties: false`).

##### Invalid Operation Example (Missing Required Operation Property):
```json
{
  "op_id": "op_004",
  "primitive": "INSERT_COLUMN",
  "sheet_name": "Sheet1",
  "target_table": "Table1",
  "col_index": 5
}
```
*Validation Result:* **FAIL** (Rejection: `header_name` is missing from `InsertColumnOp`).

---

### 4. Recovery & Durability Architecture (COR-01 Reconciled)

The platform implements a three-tier recovery and durability engine:

1. **Tier A: Pre-Transaction Snapshot Recovery (`.bak`):**
   - Prior to mutation, an atomic filesystem copy of the target workbook is staged.
   - Restoring this snapshot via atomic swap provides exact restoration when backup integrity is verified and restore succeeds on local NTFS under tested conditions. Universal disaster recovery across power failure is disclaimed.
2. **Tier B: Write-Ahead Log (WAL) Durability & In-Session Rollback:**
   - **Sequencing:** Durable transaction intent (`INTENT_RECORDED`) must strictly precede file mutation.
   - Durability follows the authoritative COR-01 sequence: pre-state `.bak` established $\rightarrow$ durable WAL intent logged & flushed (`INTENT_RECORDED`) $\rightarrow$ staged replacement write in `.staging/<session_id>/` $\rightarrow$ staged file fsync $\rightarrow$ atomic replacement (`os.replace` on same volume) $\rightarrow$ parent-directory durability step where supported by the operating system (explicitly noting that Windows NTFS does not provide POSIX directory `fsync()`, and NTFS journal persistence is not an equivalent guaranteed durability primitive; directory metadata updates remain subject to OS filesystem flushing semantics) $\rightarrow$ mark WAL transaction `COMMITTED`.
   - Provides logical undo/redo for committed transactions within the active session.
3. **Tier C: Semantic vs. Bitwise OpenXML Preservation:**
   - *Semantic/Structural Preservation (Targeted Sheets):* Modified worksheets undergoing XML mutation (`sheetN.xml`) are re-serialized conformant to OpenXML schema, preserving surrounding styles, cell formatting, font palettes, borders, and comments semantically. Universal byte-for-byte preservation of mutated XML streams is not guaranteed due to XML attribute ordering and namespace re-serialization.
   - *Bitwise Package Preservation (Non-Targeted Parts):* Package parts outside targeted worksheets and calculation chain (`vbaProject.bin`, drawings, slicers, media, themes, unedited `sheetK.xml` streams) are preserved bitwise (byte-for-byte) under experimentally verified local NTFS conditions. Universal bitwise preservation across arbitrary package features or unverified operations is explicitly disclaimed.
