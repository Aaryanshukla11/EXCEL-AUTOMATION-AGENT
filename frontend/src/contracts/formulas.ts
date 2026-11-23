/**
 * M05 Formula AST and Dependency DAG Contracts.
 * Directly mirrors schemas defined in excel_intel/formulas/models.py and graph.py.
 */

export type FormulaParseStatus = "PARSED_COMPLETE" | "UNSUPPORTED_SYNTAX" | "PARSE_ERROR";

export type CycleStatus = "NO_CYCLES" | "CYCLES_DETECTED" | "POTENTIAL_CYCLES_UNVERIFIED";

export type ASTNodeType =
  | "LITERAL"
  | "CELL_REFERENCE"
  | "RANGE_REFERENCE"
  | "STRUCTURED_REFERENCE"
  | "FUNCTION_CALL"
  | "UNARY_OP"
  | "BINARY_OP"
  | "POSTFIX_OP"
  | "ARRAY_LITERAL"
  | "UNSUPPORTED"
  | "UNPARSED";

export interface FormulaDependencyEdge {
  readonly source: string; // Precedent cell reference (e.g. 'Sheet1!A1')
  readonly target: string; // Dependent cell reference (e.g. 'Sheet1!B2')
  readonly is_volatile: boolean;
}

export interface FormulaCycleReport {
  readonly has_cycles: boolean;
  readonly cycle_paths: readonly (readonly string[])[];
  readonly total_cycles: number;
}

export interface FormulaGraphReport {
  readonly node_count: number;
  readonly edge_count: number;
  readonly has_cycles: boolean;
  readonly cycle_status: CycleStatus;
  readonly is_complete: boolean;
  readonly circular_paths: readonly (readonly string[])[];
  readonly volatile_cells: readonly string[];
  readonly unparsed_cells: readonly string[];
  readonly unsupported_cells: readonly string[];
  readonly unresolved_dependencies: readonly string[];
  readonly incompleteness_reasons: readonly string[];
  readonly has_dynamic_spills: boolean;
}
