/**
 * M01 Core Discovery Contracts.
 * Directly mirrors schemas defined in excel_intel/core/types.py.
 */

export interface CellCoordinate {
  readonly row: number;
  readonly col: number;
}

export interface BoundingBox {
  readonly start_row: number;
  readonly start_col: number;
  readonly end_row: number;
  readonly end_col: number;
  readonly min_row?: number;
  readonly min_col?: number;
  readonly max_row?: number;
  readonly max_col?: number;
}

export type ColumnType = "INTEGER" | "DECIMAL" | "STRING" | "DATE" | "BOOLEAN" | "FORMULA";

export interface ColumnMetadata {
  readonly index: number;
  readonly header_name: string;
  readonly inferred_type: ColumnType;
  readonly type_confidence: number;
  readonly nullable: boolean;
  readonly formula_pattern?: string | null;
}

export interface TableMetadata {
  readonly sheet_name: string;
  readonly bounding_box: BoundingBox;
  readonly header_row: number;
  readonly columns: readonly ColumnMetadata[];
  readonly is_list_object: boolean;
  readonly list_object_name?: string | null;
}

export interface FormulaGraphMetadata {
  readonly node_count: number;
  readonly edge_count: number;
  readonly has_cycles: boolean;
  readonly volatile_cells: readonly string[];
}

export interface DiscoveryManifest {
  readonly manifest_id: string; // UUID string
  readonly workbook_path: string;
  readonly sha256: string;
  readonly file_size_bytes: number;
  readonly tables: readonly TableMetadata[];
  readonly formula_graph: FormulaGraphMetadata;
}
