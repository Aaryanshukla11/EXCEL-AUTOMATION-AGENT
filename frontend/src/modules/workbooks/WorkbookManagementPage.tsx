import * as React from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { WorkbookDropzone } from "./WorkbookDropzone";
import { StagingQueue } from "./StagingQueue";
import { WorkbookInventory } from "./WorkbookInventory";
import { useStagingStore } from "./stagingStore";
import type { WorkbookInventoryItem } from "./workbookTypes";

const FIXTURE_INVENTORY_ITEMS: WorkbookInventoryItem[] = [
  {
    id: "sample_financial_model",
    name: "financial_model_q4.xlsx",
    format: "xlsx",
    sizeBytes: 1048576,
    sheetCount: 2,
    discoveryStatus: "completed",
    source: "backend_fixture",
    lastActivity: "2026-11-23T04:30:00Z",
  },
];

export function WorkbookManagementPage() {
  const navigate = useNavigate();
  const { stagedFiles, addFiles, removeWorkbook, clearQueue } = useStagingStore();

  const inventoryItems: WorkbookInventoryItem[] = React.useMemo(() => {
    const memoryItems: WorkbookInventoryItem[] = stagedFiles
      .filter((s) => s.validationStatus === "valid")
      .map((s) => ({
        id: s.id,
        name: s.name,
        format: s.format,
        sizeBytes: s.sizeBytes,
        sheetCount: 1, // Default pending full parsing
        discoveryStatus: s.discoveryStatus,
        source: "memory_staged",
        lastActivity: s.stagedAt,
      }));

    return [...FIXTURE_INVENTORY_ITEMS, ...memoryItems];
  }, [stagedFiles]);

  const handleInspectWorkbook = (id: string) => {
    navigate(`/spatial-viewer?workbook=${encodeURIComponent(id)}`);
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Context */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Workbook Management & Staging
        </h1>
        <p className="text-sm text-muted-foreground">
          Stage OpenXML workbooks in-memory and inspect discovery topology.
        </p>
      </div>

      {/* Scope Transparency Alert */}
      <Alert variant="info">
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>In-Memory Staging Mode Active</AlertTitle>
        <AlertDescription>
          Workbooks staged here are processed in browser memory. Live backend upload and server-side
          extraction will be connected when the backend ingestion service is packaged. Pre-computed
          fixture discovery data is clearly tagged as{" "}
          <span className="font-semibold">[FIXTURE]</span>.
        </AlertDescription>
      </Alert>

      {/* Upload Dropzone */}
      <WorkbookDropzone onFilesSelected={addFiles} />

      {/* Staging Queue */}
      <StagingQueue
        items={stagedFiles}
        onRemove={removeWorkbook}
        onClear={clearQueue}
        onInspect={handleInspectWorkbook}
      />

      {/* Workbook Inventory */}
      <WorkbookInventory items={inventoryItems} onSelectWorkbook={handleInspectWorkbook} />
    </div>
  );
}
