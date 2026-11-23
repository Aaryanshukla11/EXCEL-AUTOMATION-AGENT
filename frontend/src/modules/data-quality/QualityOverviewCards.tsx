import { AlertOctagon, AlertTriangle, FileQuestion, Info } from "lucide-react";
import type { QualityFinding } from "../../contracts/quality";
import { Card, CardContent } from "../../components/ui/Card";

interface QualityOverviewCardsProps {
  findings: readonly QualityFinding[];
}

export function QualityOverviewCards({ findings }: QualityOverviewCardsProps) {
  const criticalCount = findings.filter((f) => f.severity === "critical").length;
  const warningCount = findings.filter((f) => f.severity === "warning").length;
  const typeIssuesCount = findings.filter((f) => f.category === "type_ambiguity").length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Findings */}
      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Total Inspection Findings
            </span>
            <span className="text-2xl font-bold font-mono text-foreground">{findings.length}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            <Info className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      {/* Critical Findings */}
      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Critical Defects
            </span>
            <span className="text-2xl font-bold font-mono text-destructive">{criticalCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-destructive/10 flex items-center justify-center text-destructive">
            <AlertOctagon className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      {/* Warnings & Anomalies */}
      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Warnings & Anomalies
            </span>
            <span className="text-2xl font-bold font-mono text-warning">{warningCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-warning/10 flex items-center justify-center text-warning">
            <AlertTriangle className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      {/* Type Ambiguities */}
      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Type Ambiguities
            </span>
            <span className="text-2xl font-bold font-mono text-foreground">{typeIssuesCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
            <FileQuestion className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
