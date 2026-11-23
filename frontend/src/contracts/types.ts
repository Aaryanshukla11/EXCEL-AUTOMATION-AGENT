/**
 * M05 Semantic Type Inference Contracts.
 * Directly mirrors schemas defined in excel_intel/types/models.py.
 */

import type { ColumnType } from "./discovery";

export type InferenceState = "INFERRED" | "UNKNOWN" | "AMBIGUOUS" | "INSUFFICIENT_DATA";

export type ValueCategory =
  | "INTEGER"
  | "DECIMAL"
  | "CURRENCY"
  | "PERCENTAGE"
  | "DATE"
  | "BOOLEAN"
  | "STRING"
  | "FORMULA"
  | "NULL"
  | "ERROR";

export interface SamplingDiagnostics {
  readonly total_rows: number;
  readonly total_cols: number;
  readonly sampled_rows: number;
  readonly sampled_cols: number;
  readonly sampled_cells: number;
  readonly is_truncated: boolean;
  readonly truncation_details?: string | null;
  readonly merged_cell_count: number;
}

export interface ColumnTypeProfile {
  readonly col_index: number;
  readonly state: InferenceState;
  readonly candidate_type?: ColumnType | null;
  readonly total_cells: number;
  readonly populated_cells: number;
  readonly null_cells: number;
  readonly nullability_ratio: number;
  readonly inferred_type: ColumnType;
  readonly heuristic_support_score: number;
  readonly is_ambiguous: boolean;
  readonly ambiguity_reason?: string | null;
  readonly requires_human_review: boolean;
}

export interface RegionTypeReport {
  readonly region_id: string;
  readonly sheet_name: string;
  readonly body_row_start: number;
  readonly body_row_end: number;
  readonly body_col_start: number;
  readonly body_col_end: number;
  readonly columns: Record<number, ColumnTypeProfile>;
  readonly has_ambiguous_columns: boolean;
  readonly sampling: SamplingDiagnostics;
  readonly is_tentative: boolean;
}
