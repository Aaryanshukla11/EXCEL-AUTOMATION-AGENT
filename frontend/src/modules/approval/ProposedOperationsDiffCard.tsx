import { ArrowRight, Code } from "lucide-react";
import type { ProposedOperationSummary } from "./approvalTypes";
import { Badge } from "../../components/ui/Badge";

interface ProposedOperationsDiffCardProps {
  operation: ProposedOperationSummary;
  index: number;
}

export function ProposedOperationsDiffCard({ operation, index }: ProposedOperationsDiffCardProps) {
  const hasDiff = operation.before_value !== undefined || operation.after_value !== undefined;

  return (
    <div className="rounded-md border border-border p-3 bg-muted/20 text-xs space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Badge variant="outline" className="font-mono text-[10px]">
            #{index + 1}
          </Badge>
          <Badge variant="secondary" className="font-mono text-[10px]">
            {operation.op_type}
          </Badge>
          <span className="font-medium text-foreground">
            {operation.sheet_name} • {operation.target_range}
          </span>
        </div>
        {operation.affected_rows_count !== undefined && (
          <span className="text-[10px] text-muted-foreground font-mono">
            {operation.affected_rows_count} {operation.affected_rows_count === 1 ? "row" : "rows"}{" "}
            affected
          </span>
        )}
      </div>

      <p className="text-muted-foreground text-[11px]">{operation.description}</p>

      {/* Before / After Diff comparison */}
      {hasDiff && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1 font-mono text-[11px]">
          <div className="rounded bg-destructive/10 border border-destructive/20 p-2">
            <span className="text-[10px] uppercase font-bold text-destructive block mb-0.5">
              Before / Existing Value
            </span>
            <div className="text-foreground break-all">
              {operation.before_value !== null && operation.before_value !== undefined ? (
                <span>{operation.before_value}</span>
              ) : (
                <span className="text-muted-foreground italic">(Blank / Unpopulated)</span>
              )}
            </div>
          </div>

          <div className="rounded bg-success/10 border border-success/20 p-2">
            <span className="text-[10px] uppercase font-bold text-success block mb-0.5 flex items-center">
              Proposed Transformation <ArrowRight className="h-3 w-3 ml-1" />
            </span>
            <div className="text-foreground break-all">
              {operation.after_value !== null && operation.after_value !== undefined ? (
                <span>{operation.after_value}</span>
              ) : (
                <span className="text-muted-foreground italic">(Null / Deleted)</span>
              )}
            </div>
          </div>
        </div>
      )}

      {operation.payload && Object.keys(operation.payload).length > 0 && !hasDiff && (
        <div className="rounded bg-muted/50 p-2 text-[10px] font-mono text-muted-foreground flex items-center space-x-1.5">
          <Code className="h-3 w-3 shrink-0" />
          <span className="truncate">Payload: {JSON.stringify(operation.payload)}</span>
        </div>
      )}
    </div>
  );
}
