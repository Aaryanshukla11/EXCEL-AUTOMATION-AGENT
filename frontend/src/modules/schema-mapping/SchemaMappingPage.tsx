import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { LoadingState } from "../../components/ui/LoadingState";
import { ErrorState } from "../../components/ui/ErrorState";
import { WorkbookSelector } from "./WorkbookSelector";
import { MappingWorkspace } from "./MappingWorkspace";
import { MappingDetailPanel } from "./MappingDetailPanel";
import { useMappingSession } from "./useMappingSession";
import { apiClient } from "../../api/client";
import type { TargetMasterSchema, MappingCandidate } from "../../contracts/mapping";
import type { WorkbookSpatialDiscovery, SheetSpatialSummary } from "../../contracts/spatial";
import type { ColumnMetadata } from "../../contracts/discovery";
import {
  MOCK_WORKBOOK_DISCOVERY,
  MOCK_TARGET_MASTER_SCHEMAS,
  MOCK_MAPPING_CANDIDATES,
} from "../../mocks/fixtures";

export function SchemaMappingPage() {
  const [searchParams] = useSearchParams();
  const initialSheetParam = searchParams.get("sheet");
  const initialColParam = searchParams.get("col");

  const [discovery, setDiscovery] = React.useState<WorkbookSpatialDiscovery | null>(null);
  const [targetSchemas, setTargetSchemas] = React.useState<readonly TargetMasterSchema[]>([]);
  const [candidates, setCandidates] = React.useState<readonly MappingCandidate[]>([]);
  const [selectedTargetSchemaId, setSelectedTargetSchemaId] = React.useState<string>("");
  const [activeSheetName, setActiveSheetName] = React.useState<string>("");
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Fetch initial data
  const fetchData = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [discData, targetData, candData] = await Promise.all([
        apiClient<WorkbookSpatialDiscovery>("/api/v1/spatial/discovery").catch(
          () => MOCK_WORKBOOK_DISCOVERY
        ),
        apiClient<TargetMasterSchema[]>("/api/v1/schema-mapping/targets").catch(
          () => MOCK_TARGET_MASTER_SCHEMAS
        ),
        apiClient<MappingCandidate[]>("/api/v1/schema-mapping/candidates").catch(
          () => MOCK_MAPPING_CANDIDATES
        ),
      ]);

      setDiscovery(discData);
      setTargetSchemas(targetData);
      setCandidates(candData);

      if (targetData.length > 0) {
        setSelectedTargetSchemaId(targetData[0]!.schema_id);
      }
      if (discData.sheets.length > 0) {
        const foundSheet = initialSheetParam
          ? discData.sheets.find((s) => s.sheet_name === initialSheetParam)
          : null;
        setActiveSheetName(foundSheet ? foundSheet.sheet_name : discData.sheets[0]!.sheet_name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load mapping schema session");
    } finally {
      setIsLoading(false);
    }
  }, [initialSheetParam]);

  React.useEffect(() => {
    fetchData();
  }, [fetchData]);

  const activeSheet: SheetSpatialSummary | undefined = React.useMemo(() => {
    return discovery?.sheets.find((s) => s.sheet_name === activeSheetName);
  }, [discovery, activeSheetName]);

  const activeRegion = React.useMemo(() => {
    if (!activeSheet || activeSheet.regions.length === 0) return null;
    return activeSheet.regions[0];
  }, [activeSheet]);

  const sourceColumns: readonly ColumnMetadata[] = React.useMemo(() => {
    if (!activeRegion || !activeRegion.columns) return [];
    return activeRegion.columns;
  }, [activeRegion]);

  const selectedTargetSchema = React.useMemo(() => {
    return targetSchemas.find((s) => s.schema_id === selectedTargetSchemaId) || targetSchemas[0];
  }, [targetSchemas, selectedTargetSchemaId]);

  const targetColumns = React.useMemo(() => {
    return selectedTargetSchema?.columns || [];
  }, [selectedTargetSchema]);

  const {
    drafts,
    selectedSourceColIndex,
    setSelectedSourceColIndex,
    applyCandidate,
    setDraft,
    removeDraft,
    autoApplyHighConfidence,
    clearAllDrafts,
  } = useMappingSession(candidates, targetColumns);

  // Set initial selected column from URL search param if present
  React.useEffect(() => {
    if (initialColParam) {
      const parsed = parseInt(initialColParam, 10);
      if (!isNaN(parsed)) {
        setSelectedSourceColIndex(parsed);
      }
    }
  }, [initialColParam, setSelectedSourceColIndex]);

  const selectedSourceColumn = React.useMemo(() => {
    if (selectedSourceColIndex === null) return null;
    return sourceColumns.find((c) => c.index === selectedSourceColIndex) || null;
  }, [sourceColumns, selectedSourceColIndex]);

  const selectedColCandidates = React.useMemo(() => {
    if (selectedSourceColIndex === null) return [];
    return candidates.filter((c) => c.source_column_index === selectedSourceColIndex);
  }, [candidates, selectedSourceColIndex]);

  const selectedDraft = React.useMemo(() => {
    if (selectedSourceColIndex === null) return undefined;
    return drafts.find((d) => d.source_column_index === selectedSourceColIndex);
  }, [drafts, selectedSourceColIndex]);

  if (isLoading) {
    return <LoadingState message="Loading Schema Mapping Studio..." />;
  }

  if (error || !discovery) {
    return (
      <ErrorState
        title="Schema Mapping Initialization Failed"
        message={error || "Could not load schema mapping data."}
        onRetry={fetchData}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Title & Headline */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Schema Mapping Studio
            </h1>
            <Badge variant="outline" className="font-mono text-xs">
              Phase F3
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Align discovered worksheet columns with canonical target schemas, inspect candidate
            evidence, and draft field associations.
          </p>
        </div>
      </div>

      {/* Human Approval Boundary Disclaimer (F3 vs F4) */}
      <Alert variant="info">
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>Draft Mapping Mode Active</AlertTitle>
        <AlertDescription>
          Field associations configured here are non-binding drafts. Final human review, signature
          authorization, and commit execution are restricted to the F4 Human-in-the-Loop console.
        </AlertDescription>
      </Alert>

      {/* Workbook & Target Selector */}
      <WorkbookSelector
        discovery={discovery}
        activeSheetName={activeSheetName}
        onSelectSheet={setActiveSheetName}
        targetSchemas={targetSchemas}
        selectedTargetSchemaId={selectedTargetSchemaId}
        onSelectTargetSchema={setSelectedTargetSchemaId}
      />

      {/* Split Mapping Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8">
          <MappingWorkspace
            sourceColumns={sourceColumns}
            targetColumns={targetColumns}
            candidates={candidates}
            drafts={drafts}
            selectedSourceColIndex={selectedSourceColIndex}
            onSelectSourceColumn={setSelectedSourceColIndex}
            onAutoApply={autoApplyHighConfidence}
            onClearDrafts={clearAllDrafts}
          />
        </div>

        <div className="lg:col-span-4 sticky top-6">
          <MappingDetailPanel
            sheetName={activeSheetName}
            sourceColumn={selectedSourceColumn}
            targetColumns={targetColumns}
            candidates={selectedColCandidates}
            draft={selectedDraft}
            onApplyCandidate={applyCandidate}
            onSetDraft={setDraft}
            onRemoveDraft={removeDraft}
            onClose={() => setSelectedSourceColIndex(null)}
          />
        </div>
      </div>
    </div>
  );
}
