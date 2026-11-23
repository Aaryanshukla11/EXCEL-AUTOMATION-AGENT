import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { Badge } from "../../components/ui/Badge";
import { LoadingState } from "../../components/ui/LoadingState";
import { ErrorState } from "../../components/ui/ErrorState";
import { QualityOverviewCards } from "./QualityOverviewCards";
import { FormulaGraphCard } from "./FormulaGraphCard";
import { FindingsFilterBar } from "./FindingsFilterBar";
import { FindingsTable } from "./FindingsTable";
import { FindingDetailPanel } from "./FindingDetailPanel";
import { filterAndSortFindings } from "./qualityUtils";
import type { QualityFilterState } from "./qualityTypes";
import { apiClient } from "../../api/client";
import type { QualityAuditReport, QualityFinding } from "../../contracts/quality";
import { MOCK_QUALITY_AUDIT_REPORT } from "../../mocks/fixtures";

export function DataQualityPage() {
  const [searchParams] = useSearchParams();
  const initialSheet = searchParams.get("sheet") || "all";
  const initialFindingId = searchParams.get("findingId");

  const [report, setReport] = React.useState<QualityAuditReport | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [selectedFindingId, setSelectedFindingId] = React.useState<string | null>(initialFindingId);

  const [filters, setFilters] = React.useState<QualityFilterState>({
    search: "",
    category: "all",
    severity: "all",
    sheetName: initialSheet,
    sortBy: "severity",
    sortAsc: false,
  });

  const fetchFindings = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient<QualityAuditReport>("/api/v1/quality/findings").catch(
        () => MOCK_QUALITY_AUDIT_REPORT
      );
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quality findings");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchFindings();
  }, [fetchFindings]);

  const findings: readonly QualityFinding[] = React.useMemo(() => {
    return report?.findings || [];
  }, [report]);

  const availableSheets: readonly string[] = React.useMemo(() => {
    const sheetSet = new Set<string>();
    for (const f of findings) {
      if (f.sheet_name) sheetSet.add(f.sheet_name);
    }
    return Array.from(sheetSet);
  }, [findings]);

  const filteredFindings = React.useMemo(() => {
    return filterAndSortFindings(findings, filters);
  }, [findings, filters]);

  const selectedFinding = React.useMemo(() => {
    if (!selectedFindingId) return null;
    return findings.find((f) => f.finding_id === selectedFindingId) || null;
  }, [findings, selectedFindingId]);

  const handleFilterChange = (updated: Partial<QualityFilterState>) => {
    setFilters((prev) => ({ ...prev, ...updated }));
  };

  if (isLoading) {
    return <LoadingState message="Loading Data Quality & Audit Console..." />;
  }

  if (error || !report) {
    return (
      <ErrorState
        title="Quality Audit Load Failed"
        message={error || "Could not load workbook quality audit report."}
        onRetry={fetchFindings}
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
              Data Quality & Audit Console
            </h1>
            <Badge variant="outline" className="font-mono text-xs">
              Phase F3
            </Badge>
            {report.is_mock_fixture && (
              <Badge variant="warning" className="text-xs">
                [DEV FIXTURE]
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1 font-mono">
            Workbook: {report.workbook_path}
          </p>
        </div>
      </div>

      {/* Overview Metric Cards */}
      <QualityOverviewCards findings={findings} />

      {/* Formula Dependency DAG Summary */}
      <FormulaGraphCard report={report.formula_graph} />

      {/* Filter Toolbar */}
      <FindingsFilterBar
        filters={filters}
        onFilterChange={handleFilterChange}
        availableSheets={availableSheets}
      />

      {/* Findings Workspace (Split view) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-8">
          <FindingsTable
            findings={filteredFindings}
            selectedFindingId={selectedFindingId}
            onSelectFinding={setSelectedFindingId}
          />
        </div>

        <div className="lg:col-span-4 sticky top-6">
          <FindingDetailPanel
            finding={selectedFinding}
            onClose={() => setSelectedFindingId(null)}
          />
        </div>
      </div>
    </div>
  );
}
