import { CheckCircle2, Sparkles } from "lucide-react";
import type { MappingCandidate, TargetMasterColumn } from "../../contracts/mapping";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

interface CandidateCardProps {
  candidate: MappingCandidate;
  targetColumn?: TargetMasterColumn;
  isApplied: boolean;
  onApply: (candidate: MappingCandidate) => void;
}

export function CandidateCard({ candidate, targetColumn, isApplied, onApply }: CandidateCardProps) {
  const matchLabel =
    candidate.match_type === "exact_header"
      ? "Exact Match"
      : candidate.match_type === "normalized_header"
        ? "Normalized Header"
        : candidate.match_type === "semantic_category"
          ? "Semantic Category"
          : "Fuzzy Match";

  return (
    <div className="rounded border border-border p-2 bg-muted/20 text-xs space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-1.5">
          <Sparkles className="h-3 w-3 text-primary" />
          <span className="font-semibold text-foreground">
            {targetColumn ? targetColumn.name : `Target Col #${candidate.target_column_index}`}
          </span>
          <Badge variant="outline" className="text-[9px]">
            {matchLabel}
          </Badge>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="font-mono text-[10px] font-semibold text-primary">
            {Math.round(candidate.confidence_score * 100)}%
          </span>
          {isApplied ? (
            <Badge variant="success" className="text-[9px] py-0">
              <CheckCircle2 className="h-2.5 w-2.5 mr-0.5" /> Drafted
            </Badge>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onApply(candidate)}
              className="h-5 text-[10px] px-1.5"
            >
              Use Recommendation
            </Button>
          )}
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">{candidate.evidence}</p>
      {candidate.is_competing && (
        <span className="text-[10px] text-warning block font-medium">
          Note: Competing mapping candidate exists for this column.
        </span>
      )}
    </div>
  );
}
