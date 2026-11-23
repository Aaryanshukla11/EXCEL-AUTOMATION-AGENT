import { AlertOctagon, AlertTriangle, ChevronRight, Info } from "lucide-react";
import type { QualityFinding } from "../../contracts/quality";
import { Badge } from "../../components/ui/Badge";
import { CATEGORY_LABELS } from "./qualityUtils";
import { cn } from "../../lib/utils";

interface FindingsTableProps {
  findings: readonly QualityFinding[];
  selectedFindingId: string | null;
  onSelectFinding: (findingId: string) => void;
}

export function FindingsTable({
  findings,
  selectedFindingId,
  onSelectFinding,
}: FindingsTableProps) {
  if (findings.length === 0) {
    return (
      <div className="rounded-lg border border-border p-12 text-center text-muted-foreground text-xs bg-card">
        No inspection findings match the current filter criteria.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="grid grid-cols-12 bg-muted/50 px-4 py-2.5 text-xs font-semibold text-muted-foreground border-b border-border">
        <div className="col-span-2">Severity & Code</div>
        <div className="col-span-3">Category</div>
        <div className="col-span-5">Message & Coordinate</div>
        <div className="col-span-2 text-right">Worksheet</div>
      </div>

      <div className="divide-y divide-border">
        {findings.map((f) => {
          const isSelected = selectedFindingId === f.finding_id;

          const severityIcon =
            f.severity === "critical" ? (
              <AlertOctagon className="h-3.5 w-3.5 text-destructive mr-1" />
            ) : f.severity === "warning" ? (
              <AlertTriangle className="h-3.5 w-3.5 text-warning mr-1" />
            ) : (
              <Info className="h-3.5 w-3.5 text-primary mr-1" />
            );

          return (
            <div
              key={f.finding_id}
              onClick={() => onSelectFinding(f.finding_id)}
              className={cn(
                "grid grid-cols-12 px-4 py-3 items-center text-xs cursor-pointer transition-colors",
                isSelected
                  ? "bg-primary/10 border-l-4 border-primary"
                  : "hover:bg-muted/30 border-l-4 border-transparent"
              )}
              data-testid={`finding-row-${f.finding_id}`}
            >
              {/* Severity & Code */}
              <div className="col-span-2 flex items-center space-x-1 truncate font-mono">
                {severityIcon}
                <span className="font-semibold text-foreground truncate">{f.code}</span>
              </div>

              {/* Category */}
              <div className="col-span-3 truncate">
                <Badge variant="outline" className="text-[10px] font-normal truncate">
                  {CATEGORY_LABELS[f.category] || f.category}
                </Badge>
              </div>

              {/* Message & Coordinate */}
              <div className="col-span-5 truncate pr-2">
                <span className="text-foreground truncate block font-medium">{f.message}</span>
                {f.cell_ref && (
                  <span className="font-mono text-[10px] text-primary">Cell: {f.cell_ref}</span>
                )}
                {f.column_name && (
                  <span className="font-mono text-[10px] text-muted-foreground ml-2">
                    Col: {f.column_name}
                  </span>
                )}
              </div>

              {/* Worksheet & Arrow */}
              <div className="col-span-2 flex items-center justify-end space-x-1.5 text-right font-mono text-[11px] text-muted-foreground">
                <span className="truncate">{f.sheet_name || "—"}</span>
                <ChevronRight className="h-3.5 w-3.5 opacity-50 flex-shrink-0" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
