import { CheckCircle2, ShieldAlert, X } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";
import type { SpatialTableRegion } from "../../contracts/spatial";
import { boundingBoxToA1, colIndexToLetter, normalizeBoundingBox } from "./spatialUtils";
import { getRegionVisualProperties } from "./spatialTypes";

interface RegionDetailsPanelProps {
  region: SpatialTableRegion | null;
  onClose: () => void;
}

export function RegionDetailsPanel({ region, onClose }: RegionDetailsPanelProps) {
  if (!region) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Region Inspector</CardTitle>
          <CardDescription>
            Select any region on the grid map to inspect structural metadata.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const visual = getRegionVisualProperties(region);
  const box = normalizeBoundingBox(region.bounding_box);
  const rowCount = box.end_row - box.start_row + 1;
  const colCount = box.end_col - box.start_col + 1;

  return (
    <Card className="h-full overflow-y-auto" data-testid="region-details-panel">
      <CardHeader className="flex flex-row items-start justify-between pb-3">
        <div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="font-mono text-xs uppercase">
              {region.region_type}
            </Badge>
            {region.is_declared && <Badge variant="success">OpenXML Declared</Badge>}
          </div>
          <CardTitle className="text-base mt-1.5">{visual.label}</CardTitle>
          <CardDescription className="font-mono text-xs text-primary font-medium">
            Range: {boundingBoxToA1(region.bounding_box)}
          </CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close region inspector"
          className="h-7 w-7"
        >
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>

      <CardContent className="space-y-4 text-xs">
        {/* Dimensions & Density */}
        <div className="grid grid-cols-2 gap-2 bg-muted/40 p-2.5 rounded-md">
          <div>
            <span className="text-muted-foreground block">Dimensions:</span>
            <span className="font-semibold font-mono text-foreground">
              {rowCount}R × {colCount}C ({region.cell_count} cells)
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">Populated / Density:</span>
            <span className="font-semibold font-mono text-foreground">
              {region.populated_cell_count} ({Math.round(region.density * 100)}%)
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">Rows Span:</span>
            <span className="font-mono text-foreground">
              {region.bounding_box.start_row} to {region.bounding_box.end_row}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground block">Columns Span:</span>
            <span className="font-mono text-foreground">
              {colIndexToLetter(region.bounding_box.start_col)} to{" "}
              {colIndexToLetter(region.bounding_box.end_col)}
            </span>
          </div>
        </div>

        {/* Heuristic Confidence */}
        <div className="flex justify-between items-center border-b pb-2">
          <span className="text-muted-foreground">Heuristic Structural Score:</span>
          <span className="font-mono font-semibold text-foreground">
            {(region.heuristic_confidence * 100).toFixed(1)}%
          </span>
        </div>

        {/* Margin Clearance (ADR-005) */}
        {region.margin && (
          <div className="rounded border p-2.5 space-y-1.5 bg-muted/20">
            <div className="flex justify-between items-center">
              <span className="font-semibold text-foreground">Boundary Clearance</span>
              {region.margin.safe_for_append ? (
                <Badge variant="success" className="text-[10px]">
                  <CheckCircle2 className="mr-1 h-3 w-3" /> Safe for Append
                </Badge>
              ) : (
                <Badge variant="destructive" className="text-[10px]">
                  <ShieldAlert className="mr-1 h-3 w-3" /> Collision Risk
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground text-[11px]">
              {region.margin.spare_rows_below} spare blank rows below table before next occupied
              cell.
            </p>
          </div>
        )}

        {/* Detected Columns */}
        {region.columns && region.columns.length > 0 && (
          <div className="space-y-1.5">
            <span className="font-semibold text-foreground block">
              Resolved Columns ({region.columns.length})
            </span>
            <div className="divide-y divide-border rounded border border-border overflow-hidden">
              {region.columns.map((col) => (
                <div key={col.index} className="flex justify-between items-center p-2 bg-card">
                  <div className="flex items-center space-x-1.5 truncate">
                    <span className="font-mono text-muted-foreground">
                      {colIndexToLetter(col.index)}:
                    </span>
                    <span className="font-medium text-foreground truncate">{col.header_name}</span>
                  </div>
                  <Badge variant="outline" className="font-mono text-[9px] uppercase">
                    {col.inferred_type}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Structural Evidence Chain */}
        {region.evidence.length > 0 && (
          <div className="space-y-1.5">
            <span className="font-semibold text-foreground block">
              Structural Evidence Chain ({region.evidence.length})
            </span>
            <div className="space-y-1">
              {region.evidence.map((ev, i) => (
                <div key={i} className="rounded border p-2 bg-card text-[11px]">
                  <div className="flex justify-between items-center mb-0.5">
                    <span className="font-mono font-semibold text-primary">{ev.evidence_type}</span>
                    <span className="font-mono text-muted-foreground">{ev.heuristic_score}</span>
                  </div>
                  <p className="text-muted-foreground">{ev.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
