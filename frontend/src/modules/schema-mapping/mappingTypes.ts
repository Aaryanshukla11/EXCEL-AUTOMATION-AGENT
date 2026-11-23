import type {
  DraftColumnMapping,
  MappingCandidate,
  TargetMasterColumn,
} from "../../contracts/mapping";
import type { ColumnMetadata } from "../../contracts/discovery";

export interface ColumnMappingPair {
  sourceColumn: ColumnMetadata;
  targetColumn?: TargetMasterColumn;
  draft?: DraftColumnMapping;
  candidates: MappingCandidate[];
  isConflict: boolean;
  conflictReason?: string;
}

export type MappingFilterStatus = "all" | "mapped" | "unmapped" | "candidates" | "conflicts";
