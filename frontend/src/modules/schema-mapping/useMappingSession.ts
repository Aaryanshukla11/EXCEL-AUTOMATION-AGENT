import * as React from "react";
import type {
  DraftColumnMapping,
  MappingCandidate,
  TargetMasterColumn,
} from "../../contracts/mapping";
import { evaluateConflicts } from "./mappingUtils";

export function useMappingSession(
  initialCandidates: readonly MappingCandidate[],
  targetColumns: readonly TargetMasterColumn[]
) {
  const [drafts, setDrafts] = React.useState<DraftColumnMapping[]>([]);
  const [selectedSourceColIndex, setSelectedSourceColIndex] = React.useState<number | null>(null);

  // Apply candidate as draft
  const applyCandidate = React.useCallback(
    (candidate: MappingCandidate) => {
      setDrafts((prev) => {
        const filtered = prev.filter(
          (d) => d.source_column_index !== candidate.source_column_index
        );
        const newDraft: DraftColumnMapping = {
          id: `draft_${Date.now()}_${candidate.source_column_index}_${candidate.target_column_index}`,
          source_column_index: candidate.source_column_index,
          target_column_index: candidate.target_column_index,
          cardinality: "one_to_one",
          status: "candidate",
          confidence_score: candidate.confidence_score,
          evidence: candidate.evidence,
          is_conflict: false,
        };
        return evaluateConflicts([...filtered, newDraft], targetColumns);
      });
    },
    [targetColumns]
  );

  // Set or update manual draft
  const setDraft = React.useCallback(
    (sourceColIndex: number, targetColIndex: number) => {
      setDrafts((prev) => {
        const filtered = prev.filter((d) => d.source_column_index !== sourceColIndex);
        const newDraft: DraftColumnMapping = {
          id: `draft_${Date.now()}_${sourceColIndex}_${targetColIndex}`,
          source_column_index: sourceColIndex,
          target_column_index: targetColIndex,
          cardinality: "one_to_one",
          status: "custom",
          is_conflict: false,
        };
        return evaluateConflicts([...filtered, newDraft], targetColumns);
      });
    },
    [targetColumns]
  );

  // Remove draft
  const removeDraft = React.useCallback(
    (sourceColIndex: number) => {
      setDrafts((prev) => {
        const filtered = prev.filter((d) => d.source_column_index !== sourceColIndex);
        return evaluateConflicts(filtered, targetColumns);
      });
    },
    [targetColumns]
  );

  // Auto-apply all high-confidence non-competing candidates
  const autoApplyHighConfidence = React.useCallback(() => {
    setDrafts((prev) => {
      const updated = [...prev];
      for (const cand of initialCandidates) {
        if (
          cand.confidence_score >= 0.85 &&
          !cand.is_competing &&
          !updated.some((d) => d.source_column_index === cand.source_column_index)
        ) {
          updated.push({
            id: `draft_${Date.now()}_${cand.source_column_index}_${cand.target_column_index}`,
            source_column_index: cand.source_column_index,
            target_column_index: cand.target_column_index,
            cardinality: "one_to_one",
            status: "candidate",
            confidence_score: cand.confidence_score,
            evidence: cand.evidence,
            is_conflict: false,
          });
        }
      }
      return evaluateConflicts(updated, targetColumns);
    });
  }, [initialCandidates, targetColumns]);

  const clearAllDrafts = React.useCallback(() => {
    setDrafts([]);
  }, []);

  return {
    drafts,
    selectedSourceColIndex,
    setSelectedSourceColIndex,
    applyCandidate,
    setDraft,
    removeDraft,
    autoApplyHighConfidence,
    clearAllDrafts,
  };
}
