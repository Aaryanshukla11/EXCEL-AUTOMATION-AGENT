/**
 * Declarative Canonical Operation Contracts.
 * Directly mirrors schemas defined in excel_intel/core/types.py.
 */

export type CanonicalOpType =
  "APPEND_ROWS" | "INSERT_ROW" | "UPDATE_CELL" | "EXTEND_TABLE" | "PROPAGATE_FORMULA";

export interface SourceLineage {
  readonly source_workbook: string;
  readonly source_sheet: string;
  readonly source_row_indices: readonly number[];
}

export interface CanonicalOperation {
  readonly op_id: number;
  readonly op_type: CanonicalOpType;
  readonly sheet_name: string;
  readonly target_range: string;
  readonly payload: Record<string, unknown>;
  readonly lineage?: SourceLineage | null;
}

export interface OperationPlan {
  readonly plan_id: string; // UUID string
  readonly target_workbook: string;
  readonly operations: readonly CanonicalOperation[];
  readonly total_operations: number;
  readonly generated_at: string; // ISO 8601 timestamp
  readonly requires_hitl_approval: boolean;
}
