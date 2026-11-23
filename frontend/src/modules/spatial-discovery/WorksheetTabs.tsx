import { FileSpreadsheet } from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import type { SheetSpatialSummary } from "../../contracts/spatial";
import { cn } from "../../lib/utils";

interface WorksheetTabsProps {
  sheets: readonly SheetSpatialSummary[];
  activeSheetName: string;
  onSelectSheet: (name: string) => void;
  className?: string;
}

export function WorksheetTabs({
  sheets,
  activeSheetName,
  onSelectSheet,
  className,
}: WorksheetTabsProps) {
  return (
    <div
      className={cn(
        "flex items-center space-x-2 border-b border-border bg-muted/20 px-4 py-2 overflow-x-auto",
        className
      )}
    >
      <span className="text-xs font-semibold text-muted-foreground mr-2 flex items-center">
        <FileSpreadsheet className="h-3.5 w-3.5 mr-1" /> Sheets:
      </span>
      {sheets.map((sheet) => {
        const isActive = sheet.sheet_name === activeSheetName;

        return (
          <button
            key={sheet.sheet_name}
            onClick={() => onSelectSheet(sheet.sheet_name)}
            className={cn(
              "flex items-center space-x-1.5 rounded-md px-3 py-1 text-xs font-medium transition-colors border",
              isActive
                ? "bg-background text-foreground border-border shadow-sm font-semibold"
                : "bg-transparent text-muted-foreground hover:bg-muted/50 border-transparent"
            )}
          >
            <span>{sheet.sheet_name}</span>
            <Badge
              variant={isActive ? "default" : "outline"}
              className="text-[9px] px-1 py-0 font-normal"
            >
              {sheet.regions.length} regions
            </Badge>
          </button>
        );
      })}
    </div>
  );
}
