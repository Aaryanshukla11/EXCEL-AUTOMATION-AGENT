import { ArrowRight, BookOpen, Layers } from "lucide-react";
import type { TargetMasterSchema } from "../../contracts/mapping";
import type { WorkbookSpatialDiscovery } from "../../contracts/spatial";
import { Badge } from "../../components/ui/Badge";

interface WorkbookSelectorProps {
  discovery: WorkbookSpatialDiscovery | null;
  activeSheetName: string;
  onSelectSheet: (sheetName: string) => void;
  targetSchemas: readonly TargetMasterSchema[];
  selectedTargetSchemaId: string;
  onSelectTargetSchema: (schemaId: string) => void;
}

export function WorkbookSelector({
  discovery,
  activeSheetName,
  onSelectSheet,
  targetSchemas,
  selectedTargetSchemaId,
  onSelectTargetSchema,
}: WorkbookSelectorProps) {
  const sheets = discovery?.sheets || [];

  return (
    <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 p-4 rounded-lg border border-border bg-card">
      {/* Source Selection Info */}
      <div className="flex-1 space-y-1">
        <div className="flex items-center space-x-2">
          <BookOpen className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Source Workbook
          </span>
          {discovery?.is_mock_fixture && (
            <Badge variant="warning" className="text-[10px]">
              [DEV FIXTURE]
            </Badge>
          )}
        </div>
        <div className="flex items-center space-x-3">
          <span className="text-sm font-medium text-foreground truncate max-w-xs font-mono">
            {discovery?.workbook_path.split("/").pop() || "No source loaded"}
          </span>
          <div className="flex items-center space-x-1.5">
            <span className="text-xs text-muted-foreground">Sheet:</span>
            <select
              aria-label="Select source worksheet"
              value={activeSheetName}
              onChange={(e) => onSelectSheet(e.target.value)}
              className="h-7 text-xs rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            >
              {sheets.map((s) => (
                <option key={s.sheet_name} value={s.sheet_name}>
                  {s.sheet_name} ({s.regions.length} regions)
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="hidden md:flex items-center text-muted-foreground">
        <ArrowRight className="h-5 w-5" />
      </div>

      {/* Target Schema Selection */}
      <div className="flex-1 space-y-1">
        <div className="flex items-center space-x-2">
          <Layers className="h-4 w-4 text-primary" />
          <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Target Master Schema
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <select
            aria-label="Select target schema"
            value={selectedTargetSchemaId}
            onChange={(e) => onSelectTargetSchema(e.target.value)}
            className="h-8 text-xs w-full max-w-sm rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring font-medium"
          >
            {targetSchemas.map((schema) => (
              <option key={schema.schema_id} value={schema.schema_id}>
                {schema.schema_name} (v{schema.version} — {schema.columns.length} columns)
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
