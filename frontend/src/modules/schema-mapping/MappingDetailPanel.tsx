import { AlertTriangle, FileSearch, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type {
  DraftColumnMapping,
  MappingCandidate,
  TargetMasterColumn,
} from "../../contracts/mapping";
import type { ColumnMetadata } from "../../contracts/discovery";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";
import { CandidateCard } from "./CandidateCard";

interface MappingDetailPanelProps {
  sheetName: string;
  sourceColumn: ColumnMetadata | null;
  targetColumns: readonly TargetMasterColumn[];
  candidates: readonly MappingCandidate[];
  draft?: DraftColumnMapping;
  onApplyCandidate: (candidate: MappingCandidate) => void;
  onSetDraft: (sourceColIndex: number, targetColIndex: number) => void;
  onRemoveDraft: (sourceColIndex: number) => void;
  onClose: () => void;
}

export function MappingDetailPanel({
  sheetName,
  sourceColumn,
  targetColumns,
  candidates,
  draft,
  onApplyCandidate,
  onSetDraft,
  onRemoveDraft,
  onClose,
}: MappingDetailPanelProps) {
  const navigate = useNavigate();

  if (!sourceColumn) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Mapping Inspector</CardTitle>
          <CardDescription>
            Select any source column to inspect candidates, draft assignments, and structural
            evidence.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const mappedTarget = draft
    ? targetColumns.find((t) => t.index === draft.target_column_index)
    : undefined;

  const handleInspectQuality = () => {
    navigate(`/quality-audit?sheet=${encodeURIComponent(sheetName)}&col=${sourceColumn.index}`);
  };

  return (
    <Card className="h-full overflow-y-auto" data-testid="mapping-detail-panel">
      <CardHeader className="flex flex-row items-start justify-between pb-3">
        <div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="font-mono text-xs">
              Col #{sourceColumn.index}
            </Badge>
            <Badge variant="secondary" className="font-mono text-xs uppercase">
              {sourceColumn.inferred_type}
            </Badge>
          </div>
          <CardTitle className="text-base mt-1">{sourceColumn.header_name}</CardTitle>
          <CardDescription className="text-xs">
            {sourceColumn.nullable ? "Nullable" : "Non-Nullable"}
            {sourceColumn.formula_pattern ? ` • Formula: ${sourceColumn.formula_pattern}` : ""}
          </CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close detail panel"
          className="h-7 w-7"
        >
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Active Draft Status */}
        <div className="rounded-md border p-3 bg-card space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-foreground text-xs">Active Assignment</span>
            {draft ? (
              <Badge variant={draft.is_conflict ? "destructive" : "success"} className="text-xs">
                {draft.is_conflict ? "Conflict" : "Drafted"}
              </Badge>
            ) : (
              <Badge variant="outline" className="text-xs text-muted-foreground">
                Unmapped
              </Badge>
            )}
          </div>

          {draft ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between bg-muted/40 p-2 rounded">
                <div>
                  <span className="text-[10px] text-muted-foreground block">Target Column:</span>
                  <span className="font-semibold text-foreground text-xs">
                    {mappedTarget ? mappedTarget.name : `Target Col #${draft.target_column_index}`}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRemoveDraft(sourceColumn.index)}
                  className="h-6 text-xs text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-3 w-3 mr-1" />
                  Remove
                </Button>
              </div>

              {draft.is_conflict && draft.conflict_reason && (
                <div className="flex items-start space-x-1.5 p-2 rounded bg-destructive/10 text-destructive text-[11px]">
                  <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                  <span>{draft.conflict_reason}</span>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-muted-foreground text-[11px]">
                No draft assignment yet. Select a recommended candidate below or manually choose a
                target column.
              </p>
              <div className="flex items-center space-x-2">
                <select
                  aria-label="Assign target column manually"
                  className="h-7 text-xs w-full rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                  onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    if (!isNaN(val)) {
                      onSetDraft(sourceColumn.index, val);
                    }
                  }}
                  defaultValue=""
                >
                  <option value="" disabled>
                    Select manual target column...
                  </option>
                  {targetColumns.map((tc) => (
                    <option key={tc.index} value={tc.index}>
                      {tc.name} ({tc.expected_type})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Cross-Module Navigation: Inspect Data Quality */}
        <Button
          variant="outline"
          size="sm"
          onClick={handleInspectQuality}
          className="w-full text-xs justify-center"
        >
          <FileSearch className="h-3.5 w-3.5 mr-1.5" />
          Inspect Column in Data Quality Console
        </Button>

        {/* Recommendations & Explainability */}
        <div className="space-y-2">
          <span className="font-semibold text-foreground block text-xs">
            Mapping Recommendations ({candidates.length})
          </span>

          {candidates.length > 0 ? (
            <div className="space-y-2">
              {candidates.map((cand) => {
                const targetCol = targetColumns.find((t) => t.index === cand.target_column_index);
                const isApplied = draft?.target_column_index === cand.target_column_index;

                return (
                  <CandidateCard
                    key={cand.candidate_id}
                    candidate={cand}
                    targetColumn={targetCol}
                    isApplied={isApplied}
                    onApply={onApplyCandidate}
                  />
                );
              })}
            </div>
          ) : (
            <div className="rounded border border-dashed p-3 text-center text-muted-foreground text-[11px]">
              No automated candidates detected. Evidence is missing or insufficient for algorithmic
              proposal.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
