/**
 * M04 Spatial Detection & Inspection Contracts.
 * Directly mirrors schemas defined in excel_intel/spatial/models.py and excel_intel/inspection/models.py.
 */

import type { BoundingBox, ColumnMetadata } from "./discovery";

export type { BoundingBox };

export type SpatialRegionType =
  "declared_table" | "inferred_table" | "key_value_grid" | "sparse_island" | "irregular_composite";

export type SemanticZoneType =
  "TITLE" | "HEADER" | "BODY" | "SUMMARY" | "TOTALS" | "FOOTNOTES" | "UNKNOWN";

export type SpatialEvidenceType =
  | "DECLARED_OPENXML"
  | "VERTICAL_CORRIDOR_ISOLATION"
  | "HORIZONTAL_CORRIDOR_ISOLATION"
  | "DENSE_CELL_CLUSTER"
  | "M03_HYPOTHESIS_CORROBORATION"
  | "SINGLE_ROW_HEADER"
  | "HIERARCHICAL_STACKED_HEADER"
  | "MERGED_HEADER_OVERLAY"
  | "ZONE_TITLE_DETECTED"
  | "ZONE_HEADER_DETECTED"
  | "ZONE_BODY_DETECTED"
  | "ZONE_SUMMARY_DETECTED"
  | "BOUNDARY_SAFE_CLEARANCE";

export type AnomalySeverity = "info" | "warning" | "critical";

export interface StructuralAnomaly {
  readonly anomaly_id: string;
  readonly severity: AnomalySeverity;
  readonly code: string;
  readonly message: string;
  readonly cell_ref?: string | null;
  readonly box?: BoundingBox | null;
  readonly evidence?: string | null;
}

export interface SpatialEvidence {
  readonly evidence_type: SpatialEvidenceType;
  readonly description: string;
  readonly heuristic_score: number;
  readonly provenance: string;
  readonly coordinates?: BoundingBox | null;
}

export interface SemanticZone {
  readonly zone_type: SemanticZoneType;
  readonly bounding_box: BoundingBox;
  readonly row_count: number;
  readonly cell_count: number;
  readonly populated_cell_count: number;
  readonly heuristic_confidence: number;
  readonly evidence: readonly SpatialEvidence[];
  readonly details?: string | null;
}

export interface MarginClearance {
  readonly spare_rows_below: number;
  readonly has_zero_space_collision: boolean;
  readonly has_trailing_formulas: boolean;
  readonly adjacent_formulas: readonly string[];
  readonly safe_for_append: boolean;
  readonly collision_reason?: string | null;
}

export interface DeclaredMergeCell {
  readonly ref: string;
  readonly box: BoundingBox;
  readonly top_left_cell: string;
}

export interface SpatialTableRegion {
  readonly region_id: string;
  readonly sheet_name: string;
  readonly bounding_box: BoundingBox;
  readonly region_type: SpatialRegionType;
  readonly is_declared: boolean;
  readonly declared_name?: string | null;
  readonly heuristic_confidence: number;
  readonly evidence: readonly SpatialEvidence[];
  readonly cell_count: number;
  readonly populated_cell_count: number;
  readonly density: number;
  readonly header_row?: number | null;
  readonly columns?: readonly ColumnMetadata[] | null;
  readonly zones: Partial<Record<SemanticZoneType, SemanticZone>>;
  readonly zone_list: readonly SemanticZone[];
  readonly margin?: MarginClearance | null;
  readonly merge_cells?: readonly DeclaredMergeCell[];
  readonly anomalies?: readonly StructuralAnomaly[];
}

export interface SheetSpatialSummary {
  readonly sheet_name: string;
  readonly sheet_index: number;
  readonly visibility: "visible" | "hidden" | "veryHidden";
  readonly dimensions?: BoundingBox | null;
  readonly total_cells_visited?: number;
  readonly populated_cell_count?: number;
  readonly regions: readonly SpatialTableRegion[];
  readonly anomalies: readonly StructuralAnomaly[];
  readonly merge_cells: readonly DeclaredMergeCell[];
}

export interface WorkbookSpatialDiscovery {
  readonly workbook_path: string;
  readonly package_type: "xlsx" | "xlsm";
  readonly sha256?: string;
  readonly file_size_bytes?: number;
  readonly is_1904: boolean;
  readonly has_macros: boolean;
  readonly inspection_timestamp: string;
  readonly sheets: readonly SheetSpatialSummary[];
  readonly workbook_anomalies: readonly StructuralAnomaly[];
  readonly is_mock_fixture?: boolean;
}

export type SpatialRegion = SpatialTableRegion;
