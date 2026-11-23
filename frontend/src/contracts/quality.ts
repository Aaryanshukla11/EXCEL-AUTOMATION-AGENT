/**
 * Data Quality & Audit Console Contracts.
 * Directly aggregates M01-M05 inspection, spatial anomalies, type profiles, and formula DAG findings.
 */

import type { AnomalySeverity, BoundingBox } from "./spatial";
import type { FormulaGraphReport } from "./formulas";

export type QualityFindingCategory =
  | "structural_anomaly"
  | "type_ambiguity"
  | "formula_cycle"
  | "unsupported_formula"
  | "unresolved_dependency"
  | "volatile_function"
  | "dynamic_spill";

export interface QualityFinding {
  readonly finding_id: string;
  readonly category: QualityFindingCategory;
  readonly severity: AnomalySeverity; // "info" | "warning" | "critical"
  readonly code: string;
  readonly message: string;
  readonly workbook_path?: string;
  readonly sheet_name?: string;
  readonly cell_ref?: string | null;
  readonly region_id?: string | null;
  readonly box?: BoundingBox | null;
  readonly column_index?: number | null;
  readonly column_name?: string | null;
  readonly confidence?: number | null;
  readonly detection_source: string;
  readonly evidence?: string | null;
  readonly details?: Record<string, unknown>;
}

export interface QualityAuditReport {
  readonly report_id: string;
  readonly workbook_path: string;
  readonly total_findings: number;
  readonly findings: readonly QualityFinding[];
  readonly formula_graph?: FormulaGraphReport | null;
  readonly is_mock_fixture: boolean;
}
