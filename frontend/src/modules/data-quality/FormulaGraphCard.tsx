import { Activity, AlertTriangle, CheckCircle2, Zap } from "lucide-react";
import type { FormulaGraphReport } from "../../contracts/formulas";
import { Badge } from "../../components/ui/Badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";

interface FormulaGraphCardProps {
  report?: FormulaGraphReport | null;
}

export function FormulaGraphCard({ report }: FormulaGraphCardProps) {
  if (!report) {
    return null;
  }

  const isCycleFree = report.cycle_status === "NO_CYCLES" && !report.has_cycles;
  const isUnverified = report.cycle_status === "POTENTIAL_CYCLES_UNVERIFIED";

  return (
    <Card data-testid="formula-graph-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Activity className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm font-semibold">
              Formula Dependency DAG & Cycle Sentinels
            </CardTitle>
          </div>
          {isCycleFree ? (
            <Badge variant="success" className="text-xs">
              <CheckCircle2 className="h-3 w-3 mr-1" /> Cycle-Free
            </Badge>
          ) : isUnverified ? (
            <Badge variant="warning" className="text-xs">
              <AlertTriangle className="h-3 w-3 mr-1" /> Potential Cycles Unverified
            </Badge>
          ) : (
            <Badge variant="destructive" className="text-xs">
              <AlertTriangle className="h-3 w-3 mr-1" /> Cycles Detected
            </Badge>
          )}
        </div>
        <CardDescription className="text-xs">
          Directed calculation graph constructed from M05 AST parser. Evaluates calculation
          topology, Tarjan SCC cycles, and resource guards.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-3 text-xs">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-muted/40 p-2.5 rounded-md font-mono">
          <div>
            <span className="text-[10px] text-muted-foreground block font-sans">
              Graph Nodes / Edges:
            </span>
            <span className="font-semibold text-foreground">
              {report.node_count} nodes / {report.edge_count} edges
            </span>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground block font-sans">
              Graph Completeness:
            </span>
            <span className="font-semibold text-foreground">
              {report.is_complete ? "Complete" : "Gaps Detected"}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground block font-sans">
              Volatile Cells:
            </span>
            <span className="font-semibold text-foreground">
              {report.volatile_cells.length} cells
            </span>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground block font-sans">
              Dynamic Spills:
            </span>
            <span className="font-semibold text-foreground">
              {report.has_dynamic_spills ? "Yes (Active)" : "None"}
            </span>
          </div>
        </div>

        {/* Volatile Cells list */}
        {report.volatile_cells.length > 0 && (
          <div className="flex items-center space-x-2 text-[11px] text-muted-foreground">
            <Zap className="h-3.5 w-3.5 text-warning flex-shrink-0" />
            <span>
              Volatile function calls:{" "}
              <span className="font-mono text-foreground font-semibold">
                {report.volatile_cells.join(", ")}
              </span>
            </span>
          </div>
        )}

        {/* Unsupported syntax */}
        {report.unsupported_cells.length > 0 && (
          <div className="flex items-center space-x-2 text-[11px] text-destructive">
            <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
            <span>
              Unsupported formula syntax at:{" "}
              <span className="font-mono font-semibold">{report.unsupported_cells.join(", ")}</span>
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
