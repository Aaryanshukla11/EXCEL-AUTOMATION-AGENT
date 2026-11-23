import { AlertTriangle, CheckCircle2, FileSpreadsheet, Trash2, XCircle } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import type { StagedWorkbook } from "./workbookTypes";
import { formatBytes } from "./workbookUtils";

interface StagingQueueProps {
  items: readonly StagedWorkbook[];
  onRemove: (id: string) => void;
  onClear: () => void;
  onInspect: (id: string) => void;
}

export function StagingQueue({ items, onRemove, onClear, onInspect }: StagingQueueProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <h4 className="text-sm font-semibold text-foreground">Staging Queue</h4>
          <Badge variant="secondary">{items.length} Workbooks</Badge>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          className="text-xs h-7 text-destructive hover:text-destructive"
        >
          Clear Queue
        </Button>
      </div>

      <div className="divide-y divide-border rounded-md border border-border bg-card overflow-hidden">
        {items.map((item) => {
          const isError =
            item.validationStatus === "unsupported_format" ||
            item.validationStatus === "size_exceeded";
          const isDuplicate = item.validationStatus === "duplicate";
          const isValid = item.validationStatus === "valid";

          return (
            <div
              key={item.id}
              className="flex flex-col sm:flex-row sm:items-center justify-between p-3 gap-2"
              data-testid={`staged-item-${item.id}`}
            >
              <div className="flex items-start space-x-3">
                <FileSpreadsheet className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div className="flex flex-col">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium text-foreground truncate max-w-xs sm:max-w-md">
                      {item.name}
                    </span>
                    <Badge variant="outline" className="text-[10px] uppercase font-mono">
                      {item.format}
                    </Badge>
                  </div>
                  <div className="flex items-center space-x-2 text-xs text-muted-foreground mt-0.5">
                    <span>{formatBytes(item.sizeBytes)}</span>
                    <span>•</span>
                    <span>Modified: {new Date(item.lastModified).toLocaleDateString()}</span>
                  </div>
                  {item.validationErrors.length > 0 && (
                    <div className="text-xs text-destructive mt-1">
                      {item.validationErrors.join(" ")}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center space-x-2 self-end sm:self-center">
                {isValid && (
                  <Badge variant="success" className="text-xs">
                    <CheckCircle2 className="mr-1 h-3 w-3" /> Ready
                  </Badge>
                )}
                {isDuplicate && (
                  <Badge variant="warning" className="text-xs">
                    <AlertTriangle className="mr-1 h-3 w-3" /> Duplicate
                  </Badge>
                )}
                {isError && (
                  <Badge variant="destructive" className="text-xs">
                    <XCircle className="mr-1 h-3 w-3" /> Rejected
                  </Badge>
                )}

                {isValid && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onInspect(item.id)}
                    className="h-7 text-xs"
                  >
                    Inspect
                  </Button>
                )}

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemove(item.id)}
                  aria-label={`Remove ${item.name}`}
                  className="h-7 w-7 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
