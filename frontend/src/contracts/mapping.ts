/**
 * Schema Mapping Studio Contracts.
 * Supports universal source-to-target column alignment and draft tracking.
 */

export type MappingMatchType =
  "exact_header" | "normalized_header" | "semantic_category" | "fuzzy_match" | "custom";

export type MappingCardinality = "one_to_one" | "many_to_one" | "one_to_many";

export type MappingStatus = "unmapped" | "candidate" | "draft" | "conflict";

export interface MappingCandidate {
  readonly candidate_id: string;
  readonly source_column_index: number;
  readonly target_column_index: number;
  readonly match_type: MappingMatchType;
  readonly confidence_score: number; // 0.0 to 1.0 (from recommendation service/fixture)
  readonly evidence: string;
  readonly is_competing: boolean;
}

export interface DraftColumnMapping {
  readonly id: string;
  readonly source_column_index: number;
  readonly target_column_index: number;
  readonly cardinality: MappingCardinality;
  readonly status: "draft" | "candidate" | "custom";
  readonly confidence_score?: number;
  readonly evidence?: string;
  readonly is_conflict: boolean;
  readonly conflict_reason?: string;
  readonly notes?: string;
}

export interface TargetMasterColumn {
  readonly index: number;
  readonly name: string;
  readonly expected_type: string;
  readonly required: boolean;
  readonly description?: string;
}

export interface TargetMasterSchema {
  readonly schema_id: string;
  readonly schema_name: string;
  readonly version: string;
  readonly description?: string;
  readonly columns: readonly TargetMasterColumn[];
}

export interface SchemaMappingSession {
  readonly session_id: string;
  readonly source_workbook_id: string;
  readonly source_sheet_name: string;
  readonly source_region_id: string;
  readonly target_schema_id: string;
  readonly candidates: readonly MappingCandidate[];
  readonly draft_mappings: readonly DraftColumnMapping[];
  readonly is_mock_fixture: boolean;
}
