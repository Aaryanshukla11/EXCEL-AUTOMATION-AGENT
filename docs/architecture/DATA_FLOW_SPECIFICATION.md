# Autonomous Excel Intelligence Platform
## Data Flow & Consolidation Operation Contract (DATA_FLOW_SPECIFICATION.md)

**Status:** Formal Engineering Specification — C-Op Contract v1.2  
**Implementation Status:** Strictly Not Authorized (Design Phase Only)  
**Governing Standard:** Section 8 & Section 9 Development-Agent Governance

---

## 1. End-to-End Data Flow Architecture (18-Step Pipeline)

The data pipeline enforces a strict, unidirectional progression with complete air-gap separation between cognitive deliberation and physical workbook persistence:

```
+===================================================================================+
|                        18-STEP DATA PIPELINE LIFECYCLE                            |
+===================================================================================+
  [User Action]
       |
       v
  1. Master & Source File Selection
       |
       v
  2. Format & Integrity Validation (ZIP/OpenXML integrity check)
       |
       v
  3. Independent Workbook Inspection (Stream extraction into Sparse Coordinate AST)
       |
       v
  4. Structure & Region Discovery (Table bounds, summary blocks, formula zones)
       |
       v
  5. Dynamic Semantic Field Mapping (Header semantics + value distributions)
       |
       v
  6. Candidate Record Identity Discovery (High-cardinality composite keys)
       |
       v
  7. Cross-Source & Master Deduplication (Exact hash matches + candidate pruning)
       |
       v
  8. Contextual Record Classification (LLM evaluation: New, Duplicate, Ambiguous)
       |
       v
  9. Missing-Field Enrichment Detection (Existing Master records with blanks)
       |
       v
  10. Cross-Source Conflict Detection (Divergent values for identical keys)
       |
       v
  11. Candidate C-Op Proposal Package Assembly (State: PROPOSED)
       |
       v
  12. Risk & Escalation Gate Evaluation (Isolate actions requiring explicit sign-off)
       |
       v
  13. Human-in-the-Loop Review (User signs off on enrichments, overwrites, conflicts)
       |
       v
  14. Authorized C-Op Package Assembly (State: AUTHORIZED, with HMAC approval tokens)
       |
       v
  15. In-Memory Shadow Dry Run (Pre-condition check, formula AST, spatial non-overlap)
       |
       v
  16. Atomic Master Mutation & WAL Commit (Table expansion, row append, inverse delta)
       |
       v
  17. Post-Flight Verification (Re-read Master, verify coordinates, verify invariants)
       |
       v
  18. Execution Report & Audit Ledger Commit (SHA-256 chained audit record)
```

### 1.1 Sequence Diagram & Failure Handling

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant S1 as Subsystem 1: Ingestion & Profiling
    participant S2 as Subsystem 2: Reasoning Engine
    participant S3 as Subsystem 3: HITL Coordinator
    participant S4 as Subsystem 4: Deterministic DEL
    participant FS as Local File System

    User->>S1: Provide Master & Source Workbooks
    activate S1
    S1->>FS: Open Stream & Validate Formats
    alt Corrupted File / Invalid Archive
        S1-->>User: InspectionAbortedError (Graceful failure)
    end
    S1->>S1: Extract Sparse AST, Tables, Formulas, Provenance
    S1-->>S2: Discovered Manifests (Master + Sources)
    deactivate S1

    activate S2
    S2->>S2: Map Semantic Fields & Identify Candidate Keys
    S2->>S2: Evaluate Duplicates, Enrichments & Conflicts
    S2-->>S3: Candidate C-Op Package (State: PROPOSED)
    deactivate S2

    activate S3
    S3->>S3: Evaluate Safety Gates (FR-08, FR-09, FR-10)
    alt Escalations Required (Enrichments, Overwrites, Ambiguities)
        S3->>User: Request Review (with Diff Previews & Explanations)
        alt User Rejects or Times Out
            S3->>S3: Strip Unapproved Actions (Enforce Safe Defaults)
        else User Explicitly Approves
            S3->>S3: Generate Scoped HMAC Approval Tokens
        end
    end
    S3-->>S4: Authorized C-Op Package (State: AUTHORIZED)
    deactivate S3

    activate S4
    S4->>S4: Validate C-Op JSON Schema Draft 2020-12
    S4->>S4: Verify Cryptographic Approval Tokens
    S4->>S4: Execute Shadow Dry Run & Pre-Conditions
    alt Shadow Validation Fails (#REF!, Cycle, Space Conflict)
        S4-->>User: Abort Execution & Generate Diagnostic Error
    end
    S4->>FS: Atomic Master Mutation + Write-Ahead Log
    S4->>FS: Post-Flight Verification (Re-read & Check Hashes)
    alt Verification Fails (Invariant Breach)
        S4->>FS: Trigger WAL Rollback (Restore Original File)
        S4-->>User: Rollback Completed; State Unchanged
    else Verification Succeeds
        S4->>FS: Commit Append-Only Audit Ledger
        S4-->>User: Verified Master Workbook + Execution Summary
    end
    deactivate S4
```

---

## 2. Formal JSON Schema Draft 2020-12: Consolidation Operation Contract

The C-Op Contract is a machine-validatable JSON specification strictly governing data exchange between all subsystems.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://excel-intelligence.internal/schemas/v1.2/c-op-contract.json",
  "title": "ConsolidationOperationContract",
  "type": "object",
  "required": [
    "contract_version",
    "session_id",
    "lifecycle_state",
    "master_reference",
    "sources_manifest",
    "field_mappings",
    "record_dispositions",
    "pre_conditions",
    "post_conditions"
  ],
  "properties": {
    "contract_version": { "type": "string", "const": "1.2-consolidation" },
    "session_id": { "type": "string", "format": "uuid" },
    "lifecycle_state": {
      "type": "string",
      "enum": ["PROPOSED", "REVIEWED", "AUTHORIZED", "EXECUTED", "REVERTED", "ABORTED"]
    },
    "master_reference": {
      "type": "object",
      "required": ["file_name", "file_sha256", "target_sheet", "target_table_id", "data_boundary"],
      "properties": {
        "file_name": { "type": "string" },
        "file_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
        "target_sheet": { "type": "string" },
        "target_table_id": { "type": "string" },
        "data_boundary": {
          "type": "object",
          "required": ["start_col", "start_row", "end_col", "end_row"],
          "properties": {
            "start_col": { "type": "integer", "minimum": 1 },
            "start_row": { "type": "integer", "minimum": 1 },
            "end_col": { "type": "integer", "minimum": 1 },
            "end_row": { "type": "integer", "minimum": 1 }
          }
        },
        "next_available_insert_row": { "type": "integer", "minimum": 2 }
      }
    },
    "sources_manifest": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["source_id", "file_name", "file_sha256", "sheet_name", "total_records"],
        "properties": {
          "source_id": { "type": "string" },
          "file_name": { "type": "string" },
          "file_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
          "sheet_name": { "type": "string" },
          "total_records": { "type": "integer", "minimum": 0 }
        }
      }
    },
    "field_mappings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["mapping_id", "source_id", "source_column", "master_column_index", "confidence", "status"],
        "properties": {
          "mapping_id": { "type": "string" },
          "source_id": { "type": "string" },
          "source_column": { "type": "string" },
          "master_column_index": { "type": "integer", "minimum": 1 },
          "master_column_header": { "type": "string" },
          "confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
          "semantic_rationale": { "type": "string" },
          "status": { "type": "string", "enum": ["AUTO_MATCHED", "HUMAN_APPROVED", "UNMAPPED_SOURCE"] }
        }
      }
    },
    "record_dispositions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["disposition_id", "source_provenance", "disposition_type", "approval_state"],
        "properties": {
          "disposition_id": { "type": "string" },
          "source_provenance": {
            "type": "object",
            "required": ["source_id", "source_file_sha256", "sheet_name", "row_index", "raw_values"],
            "properties": {
              "source_id": { "type": "string" },
              "source_file_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
              "sheet_name": { "type": "string" },
              "row_index": { "type": "integer", "minimum": 1 },
              "raw_values": { "type": "object" }
            }
          },
          "disposition_type": {
            "type": "string",
            "enum": ["INSERT_NEW", "SKIP_DUPLICATE", "PROPOSE_ENRICHMENT", "CROSS_SOURCE_CONFLICT", "AMBIGUOUS_MATCH"]
          },
          "target_master_row": { "type": ["integer", "null"] },
          "candidate_key_values": { "type": "object" },
          "duplicate_evidence": {
            "type": "object",
            "properties": {
              "matched_master_row": { "type": "integer" },
              "matching_fields": { "type": "array", "items": { "type": "string" } },
              "confidence_score": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
              "rationale": { "type": "string" }
            }
          },
          "proposed_values": { "type": "object" },
          "enrichment_details": {
            "type": "object",
            "properties": {
              "target_cell_coordinates": { "type": "string" },
              "master_header": { "type": "string" },
              "current_master_value": { "type": "null" },
              "proposed_fill_value": {}
            }
          },
          "conflict_details": {
            "type": "object",
            "properties": {
              "colliding_source_id": { "type": "string" },
              "colliding_source_row": { "type": "integer" },
              "divergent_fields": {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["field_name", "value_source_1", "value_source_2"],
                  "properties": {
                    "field_name": { "type": "string" },
                    "value_source_1": {},
                    "value_source_2": {}
                  }
                }
              }
            }
          },
          "approval_state": {
            "type": "string",
            "enum": ["NOT_REQUIRED", "PENDING_REVIEW", "EXPLICITLY_APPROVED", "REJECTED", "REJECTED_TIMEOUT"]
          },
          "approval_token": {
            "type": ["object", "null"],
            "properties": {
              "token_id": { "type": "string" },
              "decision_timestamp": { "type": "string", "format": "date-time" },
              "decision": { "type": "string", "enum": ["APPROVED", "REJECTED"] },
              "scoped_hmac_signature": { "type": "string" }
            }
          }
        }
      }
    },
    "pre_conditions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["assertion_type", "target", "expected"],
        "properties": {
          "assertion_type": { "type": "string", "enum": ["FILE_SHA256_MATCH", "CELL_IS_EMPTY", "TABLE_EXISTS", "FORMULA_CHECKSUM_MATCH"] },
          "target": { "type": "string" },
          "expected": {}
        }
      }
    },
    "post_conditions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["invariant_type", "target"],
        "properties": {
          "invariant_type": { "type": "string", "enum": ["ROW_COUNT_DELTA", "FORMULA_SYNTAX_HEALTH", "UNTOUCHED_CELL_HASH_MATCH"] },
          "target": { "type": "string" },
          "expected_delta": { "type": "integer" }
        }
      }
    },
    "execution_instructions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["instruction_id", "disposition_id", "action", "destination_row"],
        "properties": {
          "instruction_id": { "type": "string" },
          "disposition_id": { "type": "string" },
          "action": { "type": "string", "enum": ["APPEND_TABLE_ROW", "UPDATE_BLANK_CELL"] },
          "destination_row": { "type": "integer", "minimum": 1 },
          "cell_payloads": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["col_index", "value", "type"],
              "properties": {
                "col_index": { "type": "integer", "minimum": 1 },
                "value": {},
                "type": { "type": "string", "enum": ["STRING", "NUMBER", "DATE", "BOOLEAN", "FORMULA_PROPAGATION"] },
                "formula_source_col": { "type": "integer" }
              }
            }
          }
        }
      }
    },
    "execution_result": {
      "type": ["object", "null"],
      "properties": {
        "execution_timestamp": { "type": "string", "format": "date-time" },
        "rows_inserted": { "type": "integer", "minimum": 0 },
        "cells_enriched": { "type": "integer", "minimum": 0 },
        "records_skipped": { "type": "integer", "minimum": 0 },
        "post_state_sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
        "verification_status": { "type": "string", "enum": ["VERIFIED_SUCCESS", "FAILED_ROLLED_BACK"] },
        "wal_delta_id": { "type": "string" }
      }
    }
  }
}
```

---

## 3. Concrete Schema-Valid JSON Examples

### Example 1: Confirmed New Record Insertion (`INSERT_NEW`)
```json
{
  "contract_version": "1.2-consolidation",
  "session_id": "4a7b9c1d-8e2f-4a3b-9c1d-8e2f4a3b9c1d",
  "lifecycle_state": "AUTHORIZED",
  "master_reference": {
    "file_name": "Master_Financials_Q3.xlsx",
    "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "target_sheet": "Consolidated_Data",
    "target_table_id": "Table_Transactions",
    "data_boundary": { "start_col": 1, "start_row": 1, "end_col": 6, "end_row": 120 },
    "next_available_insert_row": 121
  },
  "sources_manifest": [
    {
      "source_id": "SRC_NORTH",
      "file_name": "North_Region_September.xlsx",
      "file_sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
      "sheet_name": "Sheet1",
      "total_records": 1
    }
  ],
  "field_mappings": [
    {
      "mapping_id": "MAP_01",
      "source_id": "SRC_NORTH",
      "source_column": "Invoice_No",
      "master_column_index": 1,
      "master_column_header": "Invoice ID",
      "confidence": 0.98,
      "semantic_rationale": "High alphanumeric code similarity and 100% unique regex pattern.",
      "status": "AUTO_MATCHED"
    },
    {
      "mapping_id": "MAP_02",
      "source_id": "SRC_NORTH",
      "source_column": "Total_Due",
      "master_column_index": 2,
      "master_column_header": "Amount",
      "confidence": 0.94,
      "semantic_rationale": "Continuous currency distribution.",
      "status": "AUTO_MATCHED"
    }
  ],
  "record_dispositions": [
    {
      "disposition_id": "DISP_001",
      "source_provenance": {
        "source_id": "SRC_NORTH",
        "source_file_sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "sheet_name": "Sheet1",
        "row_index": 5,
        "raw_values": { "Invoice_No": "INV-2024-998", "Total_Due": 4500.50 }
      },
      "disposition_type": "INSERT_NEW",
      "target_master_row": 121,
      "candidate_key_values": { "Invoice ID": "INV-2024-998" },
      "duplicate_evidence": {
        "matching_fields": [],
        "confidence_score": 0.02,
        "rationale": "Candidate key 'INV-2024-998' not found across 120 existing Master records."
      },
      "proposed_values": { "1": "INV-2024-998", "2": 4500.50 },
      "approval_state": "NOT_REQUIRED",
      "approval_token": null
    }
  ],
  "pre_conditions": [
    { "assertion_type": "FILE_SHA256_MATCH", "target": "Master_Financials_Q3.xlsx", "expected": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" },
    { "assertion_type": "CELL_IS_EMPTY", "target": "Consolidated_Data!A121", "expected": true }
  ],
  "post_conditions": [
    { "invariant_type": "ROW_COUNT_DELTA", "target": "Table_Transactions", "expected_delta": 1 },
    { "invariant_type": "FORMULA_SYNTAX_HEALTH", "target": "Consolidated_Data" }
  ],
  "execution_instructions": [
    {
      "instruction_id": "INST_001",
      "disposition_id": "DISP_001",
      "action": "APPEND_TABLE_ROW",
      "destination_row": 121,
      "cell_payloads": [
        { "col_index": 1, "value": "INV-2024-998", "type": "STRING" },
        { "col_index": 2, "value": 4500.50, "type": "NUMBER" }
      ]
    }
  ],
  "execution_result": null
}
```

---

### Example 2: Confirmed Duplicate Skip (`SKIP_DUPLICATE`)
```json
{
  "contract_version": "1.2-consolidation",
  "session_id": "4a7b9c1d-8e2f-4a3b-9c1d-8e2f4a3b9c1d",
  "lifecycle_state": "REVIEWED",
  "master_reference": {
    "file_name": "Master_Financials_Q3.xlsx",
    "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "target_sheet": "Consolidated_Data",
    "target_table_id": "Table_Transactions",
    "data_boundary": { "start_col": 1, "start_row": 1, "end_col": 6, "end_row": 120 },
    "next_available_insert_row": 121
  },
  "sources_manifest": [
    {
      "source_id": "SRC_SOUTH",
      "file_name": "South_Region_September.xlsx",
      "file_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
      "sheet_name": "Sheet1",
      "total_records": 1
    }
  ],
  "field_mappings": [
    {
      "mapping_id": "MAP_01",
      "source_id": "SRC_SOUTH",
      "source_column": "BillNum",
      "master_column_index": 1,
      "master_column_header": "Invoice ID",
      "confidence": 0.97,
      "semantic_rationale": "High alphanumeric code similarity.",
      "status": "AUTO_MATCHED"
    }
  ],
  "record_dispositions": [
    {
      "disposition_id": "DISP_002",
      "source_provenance": {
        "source_id": "SRC_SOUTH",
        "source_file_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
        "sheet_name": "Sheet1",
        "row_index": 14,
        "raw_values": { "BillNum": "INV-2024-001", "Val": 1200.00 }
      },
      "disposition_type": "SKIP_DUPLICATE",
      "target_master_row": 12,
      "candidate_key_values": { "Invoice ID": "INV-2024-001" },
      "duplicate_evidence": {
        "matched_master_row": 12,
        "matching_fields": ["Invoice ID", "Amount"],
        "confidence_score": 1.0,
        "rationale": "Exact primary key match on 'INV-2024-001' with identical amount."
      },
      "proposed_values": {},
      "approval_state": "NOT_REQUIRED",
      "approval_token": null
    }
  ],
  "pre_conditions": [],
  "post_conditions": [],
  "execution_instructions": [],
  "execution_result": null
}
```

---

### Example 3: Blank-Field Enrichment Awaiting Approval (`PROPOSE_ENRICHMENT`)
```json
{
  "contract_version": "1.2-consolidation",
  "session_id": "4a7b9c1d-8e2f-4a3b-9c1d-8e2f4a3b9c1d",
  "lifecycle_state": "PROPOSED",
  "master_reference": {
    "file_name": "Master_Financials_Q3.xlsx",
    "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "target_sheet": "Consolidated_Data",
    "target_table_id": "Table_Transactions",
    "data_boundary": { "start_col": 1, "start_row": 1, "end_col": 6, "end_row": 120 },
    "next_available_insert_row": 121
  },
  "sources_manifest": [
    {
      "source_id": "SRC_EAST",
      "file_name": "East_Region_September.xlsx",
      "file_sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
      "sheet_name": "Sheet1",
      "total_records": 1
    }
  ],
  "field_mappings": [
    {
      "mapping_id": "MAP_TAX",
      "source_id": "SRC_EAST",
      "source_column": "Tax_Code",
      "master_column_index": 4,
      "master_column_header": "Tax Jurisdiction",
      "confidence": 0.92,
      "semantic_rationale": "ISO state code pattern matching.",
      "status": "AUTO_MATCHED"
    }
  ],
  "record_dispositions": [
    {
      "disposition_id": "DISP_003",
      "source_provenance": {
        "source_id": "SRC_EAST",
        "source_file_sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
        "sheet_name": "Sheet1",
        "row_index": 8,
        "raw_values": { "Invoice_ID": "INV-2024-045", "Tax_Code": "NY-STATE" }
      },
      "disposition_type": "PROPOSE_ENRICHMENT",
      "target_master_row": 45,
      "candidate_key_values": { "Invoice ID": "INV-2024-045" },
      "duplicate_evidence": {
        "matched_master_row": 45,
        "matching_fields": ["Invoice ID"],
        "confidence_score": 0.99,
        "rationale": "Master row 45 matches 'INV-2024-045', but Column D ('Tax Jurisdiction') is blank."
      },
      "proposed_values": { "4": "NY-STATE" },
      "enrichment_details": {
        "target_cell_coordinates": "Consolidated_Data!D45",
        "master_header": "Tax Jurisdiction",
        "current_master_value": null,
        "proposed_fill_value": "NY-STATE"
      },
      "approval_state": "PENDING_REVIEW",
      "approval_token": null
    }
  ],
  "pre_conditions": [],
  "post_conditions": [],
  "execution_instructions": [],
  "execution_result": null
}
```

---

### Example 4: Approved Blank-Field Enrichment (`EXPLICITLY_APPROVED`)
```json
{
  "contract_version": "1.2-consolidation",
  "session_id": "4a7b9c1d-8e2f-4a3b-9c1d-8e2f4a3b9c1d",
  "lifecycle_state": "AUTHORIZED",
  "master_reference": {
    "file_name": "Master_Financials_Q3.xlsx",
    "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "target_sheet": "Consolidated_Data",
    "target_table_id": "Table_Transactions",
    "data_boundary": { "start_col": 1, "start_row": 1, "end_col": 6, "end_row": 120 },
    "next_available_insert_row": 121
  },
  "sources_manifest": [
    {
      "source_id": "SRC_EAST",
      "file_name": "East_Region_September.xlsx",
      "file_sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
      "sheet_name": "Sheet1",
      "total_records": 1
    }
  ],
  "field_mappings": [],
  "record_dispositions": [
    {
      "disposition_id": "DISP_003",
      "source_provenance": {
        "source_id": "SRC_EAST",
        "source_file_sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
        "sheet_name": "Sheet1",
        "row_index": 8,
        "raw_values": { "Invoice_ID": "INV-2024-045", "Tax_Code": "NY-STATE" }
      },
      "disposition_type": "PROPOSE_ENRICHMENT",
      "target_master_row": 45,
      "candidate_key_values": { "Invoice ID": "INV-2024-045" },
      "proposed_values": { "4": "NY-STATE" },
      "enrichment_details": {
        "target_cell_coordinates": "Consolidated_Data!D45",
        "master_header": "Tax Jurisdiction",
        "current_master_value": null,
        "proposed_fill_value": "NY-STATE"
      },
      "approval_state": "EXPLICITLY_APPROVED",
      "approval_token": {
        "token_id": "TOK_99812",
        "decision_timestamp": "2026-11-21T02:40:00Z",
        "decision": "APPROVED",
        "scoped_hmac_signature": "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
      }
    }
  ],
  "pre_conditions": [
    { "assertion_type": "CELL_IS_EMPTY", "target": "Consolidated_Data!D45", "expected": true }
  ],
  "post_conditions": [
    { "invariant_type": "ROW_COUNT_DELTA", "target": "Table_Transactions", "expected_delta": 0 }
  ],
  "execution_instructions": [
    {
      "instruction_id": "INST_002",
      "disposition_id": "DISP_003",
      "action": "UPDATE_BLANK_CELL",
      "destination_row": 45,
      "cell_payloads": [
        { "col_index": 4, "value": "NY-STATE", "type": "STRING" }
      ]
    }
  ],
  "execution_result": null
}
```

---

### Example 5: Cross-Source Value Conflict (`CROSS_SOURCE_CONFLICT`)
```json
{
  "contract_version": "1.2-consolidation",
  "session_id": "4a7b9c1d-8e2f-4a3b-9c1d-8e2f4a3b9c1d",
  "lifecycle_state": "PROPOSED",
  "master_reference": {
    "file_name": "Master_Financials_Q3.xlsx",
    "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "target_sheet": "Consolidated_Data",
    "target_table_id": "Table_Transactions",
    "data_boundary": { "start_col": 1, "start_row": 1, "end_col": 6, "end_row": 120 },
    "next_available_insert_row": 121
  },
  "sources_manifest": [
    {
      "source_id": "SRC_NORTH",
      "file_name": "North_Region_September.xlsx",
      "file_sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
      "sheet_name": "Sheet1",
      "total_records": 1
    },
    {
      "source_id": "SRC_SOUTH",
      "file_name": "South_Region_September.xlsx",
      "file_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
      "sheet_name": "Sheet1",
      "total_records": 1
    }
  ],
  "field_mappings": [],
  "record_dispositions": [
    {
      "disposition_id": "DISP_005",
      "source_provenance": {
        "source_id": "SRC_NORTH",
        "source_file_sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
        "sheet_name": "Sheet1",
        "row_index": 12,
        "raw_values": { "Invoice_ID": "INV-2024-555", "Amount": 1000.00 }
      },
      "disposition_type": "CROSS_SOURCE_CONFLICT",
      "target_master_row": null,
      "candidate_key_values": { "Invoice ID": "INV-2024-555" },
      "duplicate_evidence": {
        "matching_fields": ["Invoice ID"],
        "confidence_score": 0.99,
        "rationale": "Key 'INV-2024-555' appears in both SRC_NORTH (row 12) and SRC_SOUTH (row 9) with conflicting amounts ($1000.00 vs $1200.00)."
      },
      "conflict_details": {
        "colliding_source_id": "SRC_SOUTH",
        "colliding_source_row": 9,
        "divergent_fields": [
          {
            "field_name": "Amount",
            "value_source_1": 1000.00,
            "value_source_2": 1200.00
          }
        ]
      },
      "proposed_values": {},
      "approval_state": "PENDING_REVIEW",
      "approval_token": null
    }
  ],
  "pre_conditions": [],
  "post_conditions": [],
  "execution_instructions": [],
  "execution_result": null
}
```

---

### Example 6: Ambiguous Match Requiring Human Adjudication (`AMBIGUOUS_MATCH`)
```json
{
  "contract_version": "1.2-consolidation",
  "session_id": "4a7b9c1d-8e2f-4a3b-9c1d-8e2f4a3b9c1d",
  "lifecycle_state": "PROPOSED",
  "master_reference": {
    "file_name": "Master_Financials_Q3.xlsx",
    "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "target_sheet": "Consolidated_Data",
    "target_table_id": "Table_Transactions",
    "data_boundary": { "start_col": 1, "start_row": 1, "end_col": 6, "end_row": 120 },
    "next_available_insert_row": 121
  },
  "sources_manifest": [
    {
      "source_id": "SRC_WEST",
      "file_name": "West_Region_September.xlsx",
      "file_sha256": "8f434346648f6b96df89dda901c5176b10f600ae736f5c5231e1ec50051b49ca",
      "sheet_name": "Sheet1",
      "total_records": 1
    }
  ],
  "field_mappings": [],
  "record_dispositions": [
    {
      "disposition_id": "DISP_006",
      "source_provenance": {
        "source_id": "SRC_WEST",
        "source_file_sha256": "8f434346648f6b96df89dda901c5176b10f600ae736f5c5231e1ec50051b49ca",
        "sheet_name": "Sheet1",
        "row_index": 22,
        "raw_values": { "Client": "Acme Corp", "Date": "2024-09-15", "Amount": 5000.00 }
      },
      "disposition_type": "AMBIGUOUS_MATCH",
      "target_master_row": 74,
      "candidate_key_values": { "Client": "Acme Corp", "Date": "2024-09-15" },
      "duplicate_evidence": {
        "matched_master_row": 74,
        "matching_fields": ["Client", "Date"],
        "confidence_score": 0.65,
        "rationale": "Master row 74 has same Client and Date, but Master Amount is $4800.00. Unclear if this is an updated invoice or an independent second transaction."
      },
      "proposed_values": {},
      "approval_state": "PENDING_REVIEW",
      "approval_token": null
    }
  ],
  "pre_conditions": [],
  "post_conditions": [],
  "execution_instructions": [],
  "execution_result": null
}
```
