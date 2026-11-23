import * as React from "react";
import { ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { Button } from "../../components/ui/Button";
import type { SheetSpatialSummary, SpatialTableRegion } from "../../contracts/spatial";
import { colIndexToLetter, boundingBoxToA1, normalizeBoundingBox } from "./spatialUtils";
import { getRegionVisualProperties } from "./spatialTypes";
import { cn } from "../../lib/utils";

interface SpatialGridMapProps {
  sheet: SheetSpatialSummary;
  selectedRegionId: string | null;
  onSelectRegion: (id: string | null) => void;
  className?: string;
}

const CELL_WIDTH = 56;
const CELL_HEIGHT = 26;
const ROW_HEADER_WIDTH = 44;
const COL_HEADER_HEIGHT = 24;

export function SpatialGridMap({
  sheet,
  selectedRegionId,
  onSelectRegion,
  className,
}: SpatialGridMapProps) {
  const [zoom, setZoom] = React.useState(1.0);
  const [hoveredRegion, setHoveredRegion] = React.useState<SpatialTableRegion | null>(null);
  const [tooltipPos, setTooltipPos] = React.useState<{ x: number; y: number } | null>(null);

  // Compute total grid span
  const sheetDims = sheet.dimensions ? normalizeBoundingBox(sheet.dimensions) : null;
  const maxRow = Math.max(
    sheetDims?.end_row || 30,
    ...sheet.regions.map((r) => normalizeBoundingBox(r.bounding_box).end_row),
    25
  );
  const maxCol = Math.max(
    sheetDims?.end_col || 10,
    ...sheet.regions.map((r) => normalizeBoundingBox(r.bounding_box).end_col),
    8
  );

  const displayRows = Math.min(maxRow + 5, 100); // Bounded display
  const displayCols = Math.min(maxCol + 3, 30);

  const totalWidth = ROW_HEADER_WIDTH + displayCols * CELL_WIDTH;
  const totalHeight = COL_HEADER_HEIGHT + displayRows * CELL_HEIGHT;

  const handleZoom = (delta: number) => {
    setZoom((prev) => Math.min(Math.max(0.5, prev + delta), 2.0));
  };

  return (
    <div
      className={cn(
        "flex flex-col rounded-lg border border-border bg-card overflow-hidden relative select-none",
        className
      )}
      data-testid="spatial-grid-map-container"
    >
      {/* Viewer Toolbar */}
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2 z-10">
        <div className="flex items-center space-x-2 text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">{sheet.sheet_name}</span>
          <span>•</span>
          <span>
            {displayRows} Rows × {displayCols} Columns ({sheet.regions.length} Regions)
          </span>
        </div>

        <div className="flex items-center space-x-1">
          <span className="text-xs text-muted-foreground font-mono mr-2">
            {Math.round(zoom * 100)}%
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => handleZoom(-0.15)}
            className="h-7 w-7"
            aria-label="Zoom out"
            title="Zoom out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => handleZoom(0.15)}
            className="h-7 w-7"
            aria-label="Zoom in"
            title="Zoom in"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setZoom(1.0)}
            className="h-7 w-7"
            aria-label="Reset zoom"
            title="Reset zoom"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Interactive Coordinate Canvas Area */}
      <div className="flex-1 overflow-auto bg-muted/10 relative p-4" style={{ maxHeight: "600px" }}>
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "top left",
            width: `${totalWidth}px`,
            height: `${totalHeight}px`,
          }}
          className="relative transition-transform duration-75"
        >
          <svg
            width={totalWidth}
            height={totalHeight}
            className="absolute inset-0"
            data-testid="spatial-grid-svg"
          >
            <defs>
              {/* Region pattern hatch definitions */}
              <pattern
                id="hatch-pattern"
                width="8"
                height="8"
                patternTransform="rotate(45 0 0)"
                patternUnits="userSpaceOnUse"
              >
                <line
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="8"
                  stroke="currentColor"
                  strokeWidth="1"
                  opacity="0.3"
                />
              </pattern>
            </defs>

            {/* Column Header Background */}
            <rect
              x={ROW_HEADER_WIDTH}
              y={0}
              width={totalWidth - ROW_HEADER_WIDTH}
              height={COL_HEADER_HEIGHT}
              fill="hsl(var(--muted))"
              opacity="0.8"
            />

            {/* Row Header Background */}
            <rect
              x={0}
              y={COL_HEADER_HEIGHT}
              width={ROW_HEADER_WIDTH}
              height={totalHeight - COL_HEADER_HEIGHT}
              fill="hsl(var(--muted))"
              opacity="0.8"
            />

            {/* Column Headers (A, B, C...) */}
            {Array.from({ length: displayCols }).map((_, c) => {
              const colIdx = c + 1;
              const x = ROW_HEADER_WIDTH + c * CELL_WIDTH;
              return (
                <g key={`col-${colIdx}`}>
                  <rect
                    x={x}
                    y={0}
                    width={CELL_WIDTH}
                    height={COL_HEADER_HEIGHT}
                    fill="transparent"
                    stroke="hsl(var(--border))"
                    strokeWidth="0.5"
                  />
                  <text
                    x={x + CELL_WIDTH / 2}
                    y={COL_HEADER_HEIGHT / 2 + 4}
                    textAnchor="middle"
                    className="text-[11px] font-mono fill-muted-foreground font-semibold"
                  >
                    {colIndexToLetter(colIdx)}
                  </text>
                </g>
              );
            })}

            {/* Row Headers (1, 2, 3...) */}
            {Array.from({ length: displayRows }).map((_, r) => {
              const rowIdx = r + 1;
              const y = COL_HEADER_HEIGHT + r * CELL_HEIGHT;
              return (
                <g key={`row-${rowIdx}`}>
                  <rect
                    x={0}
                    y={y}
                    width={ROW_HEADER_WIDTH}
                    height={CELL_HEIGHT}
                    fill="transparent"
                    stroke="hsl(var(--border))"
                    strokeWidth="0.5"
                  />
                  <text
                    x={ROW_HEADER_WIDTH / 2}
                    y={y + CELL_HEIGHT / 2 + 4}
                    textAnchor="middle"
                    className="text-[10px] font-mono fill-muted-foreground font-semibold"
                  >
                    {rowIdx}
                  </text>
                </g>
              );
            })}

            {/* Light Grid Lines */}
            {Array.from({ length: displayRows }).map((_, r) => {
              const y = COL_HEADER_HEIGHT + (r + 1) * CELL_HEIGHT;
              return (
                <line
                  key={`grid-row-${r}`}
                  x1={ROW_HEADER_WIDTH}
                  y1={y}
                  x2={totalWidth}
                  y2={y}
                  stroke="hsl(var(--border))"
                  strokeWidth="0.5"
                  strokeDasharray="2,2"
                  opacity="0.5"
                />
              );
            })}
            {Array.from({ length: displayCols }).map((_, c) => {
              const x = ROW_HEADER_WIDTH + (c + 1) * CELL_WIDTH;
              return (
                <line
                  key={`grid-col-${c}`}
                  x1={x}
                  y1={COL_HEADER_HEIGHT}
                  x2={x}
                  y2={totalHeight}
                  stroke="hsl(var(--border))"
                  strokeWidth="0.5"
                  strokeDasharray="2,2"
                  opacity="0.5"
                />
              );
            })}

            {/* Merged Cells */}
            {sheet.merge_cells.map((merge) => {
              const box = normalizeBoundingBox(merge.box);
              const x = ROW_HEADER_WIDTH + (box.start_col - 1) * CELL_WIDTH;
              const y = COL_HEADER_HEIGHT + (box.start_row - 1) * CELL_HEIGHT;
              const w = (box.end_col - box.start_col + 1) * CELL_WIDTH;
              const h = (box.end_row - box.start_row + 1) * CELL_HEIGHT;

              return (
                <rect
                  key={`merge-${merge.ref}`}
                  x={x + 1}
                  y={y + 1}
                  width={w - 2}
                  height={h - 2}
                  fill="rgba(100, 116, 139, 0.08)"
                  stroke="rgb(100, 116, 139)"
                  strokeWidth="1"
                  strokeDasharray="3,3"
                />
              );
            })}

            {/* Detected Spatial Regions */}
            {sheet.regions.map((region) => {
              const box = normalizeBoundingBox(region.bounding_box);
              const x = ROW_HEADER_WIDTH + (box.start_col - 1) * CELL_WIDTH;
              const y = COL_HEADER_HEIGHT + (box.start_row - 1) * CELL_HEIGHT;
              const w = (box.end_col - box.start_col + 1) * CELL_WIDTH;
              const h = (box.end_row - box.start_row + 1) * CELL_HEIGHT;

              const isSelected = selectedRegionId === region.region_id;
              const visual = getRegionVisualProperties(region);

              return (
                <g
                  key={region.region_id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectRegion(isSelected ? null : region.region_id);
                  }}
                  onMouseEnter={(e) => {
                    setHoveredRegion(region);
                    setTooltipPos({ x: e.clientX, y: e.clientY });
                  }}
                  onMouseLeave={() => setHoveredRegion(null)}
                  className="cursor-pointer transition-all"
                  data-testid={`region-shape-${region.region_id}`}
                >
                  {/* Region Bounding Box Rect */}
                  <rect
                    x={x + 1}
                    y={y + 1}
                    width={Math.max(w - 2, 4)}
                    height={Math.max(h - 2, 4)}
                    fill={visual.fillColor}
                    stroke={isSelected ? "rgb(234, 88, 12)" : visual.strokeColor}
                    strokeWidth={isSelected ? 3 : 2}
                    rx="2"
                  />

                  {/* Accessible Label Tag */}
                  <g transform={`translate(${x + 4}, ${y + 4})`}>
                    <rect
                      x={0}
                      y={0}
                      width={Math.min(w - 8, 140)}
                      height={18}
                      rx="3"
                      fill="rgba(255, 255, 255, 0.9)"
                      stroke={visual.strokeColor}
                      strokeWidth="0.5"
                    />
                    <text
                      x={6}
                      y={13}
                      fill={visual.textColor}
                      className="text-[9px] font-semibold truncate"
                    >
                      {visual.label}
                    </text>
                  </g>

                  {/* Semantic Zones Decomposed (Header Zone) */}
                  {region.zones.HEADER && (
                    <rect
                      x={x + 1}
                      y={y + 1}
                      width={w - 2}
                      height={
                        (normalizeBoundingBox(region.zones.HEADER.bounding_box).end_row -
                          normalizeBoundingBox(region.zones.HEADER.bounding_box).start_row +
                          1) *
                        CELL_HEIGHT
                      }
                      fill={visual.strokeColor}
                      opacity="0.18"
                    />
                  )}
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Floating Hover Tooltip */}
      {hoveredRegion && tooltipPos && (
        <div
          className="fixed z-50 rounded bg-foreground px-3 py-1.5 text-xs text-background shadow-lg pointer-events-none transform -translate-x-1/2 -translate-y-12"
          style={{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }}
        >
          <div className="font-semibold">
            {boundingBoxToA1(hoveredRegion.bounding_box)} —{" "}
            {hoveredRegion.declared_name || hoveredRegion.region_type}
          </div>
          <div className="text-[10px] text-muted opacity-80">
            {hoveredRegion.bounding_box.end_row - hoveredRegion.bounding_box.start_row + 1} Rows ×{" "}
            {hoveredRegion.bounding_box.end_col - hoveredRegion.bounding_box.start_col + 1} Columns
            ({Math.round(hoveredRegion.density * 100)}% density)
          </div>
        </div>
      )}
    </div>
  );
}
