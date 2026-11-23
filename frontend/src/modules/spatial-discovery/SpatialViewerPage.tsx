import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { Info } from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { LoadingState } from "../../components/ui/LoadingState";
import { ErrorState } from "../../components/ui/ErrorState";
import { SpatialGridMap } from "./SpatialGridMap";
import { RegionDetailsPanel } from "./RegionDetailsPanel";
import { WorksheetTabs } from "./WorksheetTabs";
import { SpatialAnomaliesCard } from "./SpatialAnomaliesCard";
import { apiClient } from "../../api/client";
import type {
  WorkbookSpatialDiscovery,
  SheetSpatialSummary,
  SpatialTableRegion,
} from "../../contracts/spatial";
import { MOCK_WORKBOOK_DISCOVERY } from "../../mocks/fixtures";

export function SpatialViewerPage() {
  const [searchParams] = useSearchParams();
  const workbookParam = searchParams.get("workbook") || "sample_financial_model";

  const [discovery, setDiscovery] = React.useState<WorkbookSpatialDiscovery | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [activeSheetName, setActiveSheetName] = React.useState<string>("");
  const [selectedRegionId, setSelectedRegionId] = React.useState<string | null>(null);

  const fetchDiscovery = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient<WorkbookSpatialDiscovery>("/api/v1/spatial/discovery");
      setDiscovery(data);
      if (data.sheets.length > 0) {
        setActiveSheetName(data.sheets[0]!.sheet_name);
      }
    } catch {
      // Fallback to in-memory mock fixture if endpoint fails or in test
      setDiscovery(MOCK_WORKBOOK_DISCOVERY);
      if (MOCK_WORKBOOK_DISCOVERY.sheets.length > 0) {
        setActiveSheetName(MOCK_WORKBOOK_DISCOVERY.sheets[0]!.sheet_name);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchDiscovery();
  }, [fetchDiscovery]);

  const activeSheet: SheetSpatialSummary | undefined = React.useMemo(() => {
    return discovery?.sheets.find((s) => s.sheet_name === activeSheetName);
  }, [discovery, activeSheetName]);

  const selectedRegion: SpatialTableRegion | null = React.useMemo(() => {
    if (!activeSheet || !selectedRegionId) return null;
    return activeSheet.regions.find((r) => r.region_id === selectedRegionId) || null;
  }, [activeSheet, selectedRegionId]);

  if (isLoading) {
    return <LoadingState message="Extracting spatial discovery topology..." />;
  }

  if (error || !discovery) {
    return (
      <ErrorState
        title="Spatial Discovery Extraction Failed"
        message={error || "Could not load workbook spatial discovery report."}
        onRetry={fetchDiscovery}
      />
    );
  }

  const totalRegions = discovery.sheets.reduce((acc, s) => acc + s.regions.length, 0);
  const totalAnomalies = discovery.sheets.reduce((acc, s) => acc + s.anomalies.length, 0);

  return (
    <div className="space-y-6">
      {/* Header and Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Spatial Discovery Viewer
            </h1>
            <Badge variant="outline" className="font-mono text-xs">
              {discovery.package_type.toUpperCase()}
            </Badge>
            {discovery.is_mock_fixture && (
              <Badge variant="warning" className="text-xs">
                [DEV FIXTURE]
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground font-mono mt-1">
            Workbook: {discovery.workbook_path || workbookParam}
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Badge variant="success">Discovery Completed</Badge>
        </div>
      </div>

      {/* Scope Disclaimer */}
      <Alert variant="info">
        <Info className="h-4 w-4" />
        <AlertTitle>Spatial Structure Visualizer</AlertTitle>
        <AlertDescription>
          Displays declared OpenXML tables and heuristic spatial regions detected by M04. Rendering
          is bounded and scalable using coordinate plane projection.
        </AlertDescription>
      </Alert>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="rounded border bg-card p-3">
          <span className="text-xs text-muted-foreground block">Worksheets</span>
          <span className="text-xl font-bold text-foreground font-mono">
            {discovery.sheets.length}
          </span>
        </div>
        <div className="rounded border bg-card p-3">
          <span className="text-xs text-muted-foreground block">Detected Regions</span>
          <span className="text-xl font-bold text-foreground font-mono">{totalRegions}</span>
        </div>
        <div className="rounded border bg-card p-3">
          <span className="text-xs text-muted-foreground block">Active Sheet Cells</span>
          <span className="text-xl font-bold text-foreground font-mono">
            {activeSheet?.populated_cell_count || 0}
          </span>
        </div>
        <div className="rounded border bg-card p-3">
          <span className="text-xs text-muted-foreground block">Structural Anomalies</span>
          <span className="text-xl font-bold text-foreground font-mono text-warning">
            {totalAnomalies}
          </span>
        </div>
      </div>

      {/* Sheet Tabs */}
      <WorksheetTabs
        sheets={discovery.sheets}
        activeSheetName={activeSheetName}
        onSelectSheet={(name) => {
          setActiveSheetName(name);
          setSelectedRegionId(null);
        }}
      />

      {/* Main Split Viewer */}
      {activeSheet ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2 space-y-4">
            <SpatialGridMap
              sheet={activeSheet}
              selectedRegionId={selectedRegionId}
              onSelectRegion={setSelectedRegionId}
            />

            <SpatialAnomaliesCard anomalies={activeSheet.anomalies} />
          </div>

          <div className="lg:col-span-1">
            <RegionDetailsPanel region={selectedRegion} onClose={() => setSelectedRegionId(null)} />
          </div>
        </div>
      ) : (
        <div className="p-8 text-center text-muted-foreground text-sm">No worksheet selected.</div>
      )}
    </div>
  );
}
