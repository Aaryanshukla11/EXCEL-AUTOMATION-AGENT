import * as React from "react";
import { FileUp, UploadCloud } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { cn } from "../../lib/utils";

interface WorkbookDropzoneProps {
  onFilesSelected: (files: FileList | File[]) => void;
  className?: string;
}

export function WorkbookDropzone({ onFilesSelected, className }: WorkbookDropzoneProps) {
  const [isDragOver, setIsDragOver] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onFilesSelected(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onFilesSelected(e.target.files);
      // Reset input value so same file can be re-selected if removed
      e.target.value = "";
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors",
        isDragOver ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-muted/30",
        className
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12"
        className="hidden"
        onChange={handleFileInputChange}
        data-testid="workbook-file-input"
      />

      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary mb-3">
        <UploadCloud className="h-6 w-6" aria-hidden="true" />
      </div>

      <h3 className="text-base font-semibold text-foreground">
        Select or drag Excel workbooks here
      </h3>
      <p className="mt-1 text-xs text-muted-foreground max-w-sm">
        Supports multiple files simultaneously. Files are processed entirely in-memory.
      </p>

      <div className="flex items-center space-x-2 mt-3">
        <Badge variant="outline">.xlsx (OpenXML)</Badge>
        <Badge variant="outline">.xlsm (Macros)</Badge>
        <span className="text-[11px] text-muted-foreground">Max 250 MiB/file</span>
      </div>

      <Button
        variant="default"
        size="sm"
        onClick={() => fileInputRef.current?.click()}
        className="mt-4"
      >
        <FileUp className="mr-2 h-4 w-4" />
        Browse Workbooks
      </Button>
    </div>
  );
}
