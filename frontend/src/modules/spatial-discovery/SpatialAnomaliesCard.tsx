import { AlertTriangle, AlertCircle, Info } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import type { StructuralAnomaly } from "../../contracts/spatial";

interface SpatialAnomaliesCardProps {
  anomalies: readonly StructuralAnomaly[];
}

export function SpatialAnomaliesCard({ anomalies }: SpatialAnomaliesCardProps) {
  if (anomalies.length === 0) {
    return null;
  }

  const getSeverityIcon = (severity: StructuralAnomaly["severity"]) => {
    switch (severity) {
      case "critical":
        return <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />;
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-warning flex-shrink-0" />;
      default:
        return <Info className="h-4 w-4 text-primary flex-shrink-0" />;
    }
  };

  return (
    <Card className="border-warning/40 bg-warning/5">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center space-x-1.5">
            <AlertTriangle className="h-4 w-4 text-warning" />
            <span>Structural Anomalies Detected ({anomalies.length})</span>
          </CardTitle>
          <Badge variant="warning" className="text-[10px]">
            Review Required
          </Badge>
        </div>
        <CardDescription className="text-xs">
          Heuristic inconsistencies or boundary collisions flagged by the spatial engine.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-xs">
        {anomalies.map((anom) => (
          <div key={anom.anomaly_id} className="rounded border bg-background p-2.5 space-y-1">
            <div className="flex justify-between items-center">
              <span className="font-mono font-semibold text-foreground flex items-center space-x-1">
                {getSeverityIcon(anom.severity)}
                <span>{anom.code}</span>
              </span>
              {anom.cell_ref && (
                <Badge variant="outline" className="font-mono text-[10px]">
                  {anom.cell_ref}
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground">{anom.message}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
