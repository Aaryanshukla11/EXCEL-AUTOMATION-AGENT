import { Grid, Workflow, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { QualityFinding } from "../../contracts/quality";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";
import { CATEGORY_LABELS } from "./qualityUtils";

interface FindingDetailPanelProps {
  finding: QualityFinding | null;
  onClose: () => void;
}

export function FindingDetailPanel({ finding, onClose }: FindingDetailPanelProps) {
  const navigate = useNavigate();

  if (!finding) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Finding Inspector</CardTitle>
          <CardDescription>
            Select any inspection finding to view diagnostic details, coordinate bounds, and
            detection provenance.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const handleInspectInSpatialViewer = () => {
    const params = new URLSearchParams();
    if (finding.sheet_name) params.set("sheet", finding.sheet_name);
    if (finding.region_id) params.set("region", finding.region_id);
    navigate(`/spatial-viewer?${params.toString()}`);
  };

  const handleInspectInSchemaStudio = () => {
    const params = new URLSearchParams();
    if (finding.sheet_name) params.set("sheet", finding.sheet_name);
    if (finding.column_index !== null && finding.column_index !== undefined) {
      params.set("col", String(finding.column_index));
    }
    navigate(`/schema-studio?${params.toString()}`);
  };

  const severityBadgeVariant =
    finding.severity === "critical"
      ? "destructive"
      : finding.severity === "warning"
        ? "warning"
        : "secondary";

  return (
    <Card className="h-full overflow-y-auto" data-testid="finding-detail-panel">
      <CardHeader className="flex flex-row items-start justify-between pb-3">
        <div>
          <div className="flex items-center space-x-2">
            <Badge variant={severityBadgeVariant} className="text-[10px] uppercase font-mono">
              {finding.severity}
            </Badge>
            <Badge variant="outline" className="text-[10px]">
              {CATEGORY_LABELS[finding.category] || finding.category}
            </Badge>
          </div>
          <CardTitle className="text-base mt-1.5 font-mono">{finding.code}</CardTitle>
          <CardDescription className="text-xs">{finding.message}</CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close finding detail"
          className="h-7 w-7"
        >
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Coordinate & Provenance Metadata */}
        <div className="grid grid-cols-2 gap-2 bg-muted/40 p-2.5 rounded-md">
          <div>
            <span className="text-muted-foreground block text-[10px]">Worksheet:</span>
            <span className="font-semibold text-foreground font-mono">
              {finding.sheet_name || "Workbook Level"}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[10px]">Cell Coordinate:</span>
            <span className="font-semibold text-foreground font-mono">
              {finding.cell_ref || "Area Bounded"}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[10px]">Detection Source:</span>
            <span className="text-foreground font-mono truncate block text-[11px]">
              {finding.detection_source}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block text-[10px]">Detection Confidence:</span>
            <span className="font-mono text-foreground font-semibold">
              {finding.confidence !== null && finding.confidence !== undefined
                ? `${Math.round(finding.confidence * 100)}%`
                : "Deterministic"}
            </span>
          </div>
        </div>

        {/* Evidence Details */}
        {finding.evidence && (
          <div className="space-y-1">
            <span className="font-semibold text-foreground block text-xs">Structural Evidence</span>
            <div className="rounded border p-2.5 bg-card text-[11px] text-muted-foreground leading-relaxed">
              {finding.evidence}
            </div>
          </div>
        )}

        {/* Action Navigation Buttons */}
        <div className="space-y-2 pt-2 border-t border-border">
          <Button
            variant="outline"
            size="sm"
            onClick={handleInspectInSpatialViewer}
            className="w-full text-xs justify-center"
          >
            <Grid className="h-3.5 w-3.5 mr-1.5" />
            Inspect in Spatial Discovery Viewer
          </Button>

          {(finding.column_name || finding.column_index !== null) && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleInspectInSchemaStudio}
              className="w-full text-xs justify-center"
            >
              <Workflow className="h-3.5 w-3.5 mr-1.5" />
              Inspect Column in Schema Studio
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
