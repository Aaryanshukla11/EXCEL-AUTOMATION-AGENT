import type {
  DraftColumnMapping,
  MappingCandidate,
  TargetMasterColumn,
} from "../../contracts/mapping";
import type { ColumnMetadata } from "../../contracts/discovery";
import type { ColumnMappingPair } from "./mappingTypes";

/**
 * Calculates conflict status across draft mappings.
 * For one_to_one cardinality, multiple source columns mapped to the same target column trigger a conflict.
 */
export function evaluateConflicts(
  drafts: readonly DraftColumnMapping[],
  targetColumns: readonly TargetMasterColumn[]
): DraftColumnMapping[] {
  // Count assignments per target column
  const targetUsage = new Map<number, number>();
  for (const d of drafts) {
    if (d.cardinality === "one_to_one") {
      targetUsage.set(d.target_column_index, (targetUsage.get(d.target_column_index) || 0) + 1);
    }
  }

  const targetMap = new Map<number, TargetMasterColumn>();
  for (const t of targetColumns) {
    targetMap.set(t.index, t);
  }

  return drafts.map((d) => {
    const usage = targetUsage.get(d.target_column_index) || 0;
    const targetCol = targetMap.get(d.target_column_index);
    const targetName = targetCol ? targetCol.name : `Column #${d.target_column_index}`;

    if (d.cardinality === "one_to_one" && usage > 1) {
      return {
        ...d,
        is_conflict: true,
        conflict_reason: `One-to-one constraint violation: Multiple source fields are mapped to target '${targetName}'.`,
      };
    }
    return {
      ...d,
      is_conflict: false,
      conflict_reason: undefined,
    };
  });
}

/**
 * Synthesizes source columns, target columns, candidates, and drafts into structured pairs.
 * Utilizes pre-indexed HashMaps for O(N + M) performance on large datasets.
 */
export function buildMappingPairs(
  sourceColumns: readonly ColumnMetadata[],
  targetColumns: readonly TargetMasterColumn[],
  candidates: readonly MappingCandidate[],
  drafts: readonly DraftColumnMapping[]
): ColumnMappingPair[] {
  const candidatesBySource = new Map<number, MappingCandidate[]>();
  for (const c of candidates) {
    const list = candidatesBySource.get(c.source_column_index);
    if (!list) {
      candidatesBySource.set(c.source_column_index, [c]);
    } else {
      list.push(c);
    }
  }

  const draftsBySource = new Map<number, DraftColumnMapping>();
  for (const d of drafts) {
    draftsBySource.set(d.source_column_index, d);
  }

  const targetByIndex = new Map<number, TargetMasterColumn>();
  for (const t of targetColumns) {
    targetByIndex.set(t.index, t);
  }

  return sourceColumns.map((sourceCol) => {
    const colCandidates = candidatesBySource.get(sourceCol.index) || [];
    const draft = draftsBySource.get(sourceCol.index);
    const targetCol = draft ? targetByIndex.get(draft.target_column_index) : undefined;

    return {
      sourceColumn: sourceCol,
      targetColumn: targetCol,
      draft,
      candidates: colCandidates,
      isConflict: draft ? draft.is_conflict : false,
      conflictReason: draft?.conflict_reason,
    };
  });
}
