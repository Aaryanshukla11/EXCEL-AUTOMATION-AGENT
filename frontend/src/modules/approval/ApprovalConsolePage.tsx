import { ShieldAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { LoadingState } from "../../components/ui/LoadingState";
import { ErrorState } from "../../components/ui/ErrorState";
import { ApprovalKPIOverview } from "./ApprovalKPIOverview";
import { ApprovalFilterBar } from "./ApprovalFilterBar";
import { ApprovalQueueTable } from "./ApprovalQueueTable";
import { ApprovalDetailPanel } from "./ApprovalDetailPanel";
import { useApprovalQueue } from "./useApprovalQueue";

export function ApprovalConsolePage() {
  const {
    requests,
    filteredRequests,
    selectedRequest,
    selectedRequestId,
    setSelectedRequestId,
    filters,
    setFilters,
    isLoading,
    error,
    reload,
    handleDecision,
  } = useApprovalQueue();

  if (isLoading) {
    return <LoadingState message="Loading approval requests and risk assessments..." />;
  }

  if (error && requests.length === 0) {
    return <ErrorState title="Failed to Load Approval Console" message={error} onRetry={reload} />;
  }

  const pendingCount = requests.filter((r) => r.state === "PENDING_REVIEW").length;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Human-in-the-Loop Approval Console
            </h1>
            <Badge variant="outline" className="text-xs">
              Phase F4
            </Badge>
            <Badge variant="warning" className="text-xs">
              [DEV FIXTURE]
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Inspect declarative operation proposals, analyze risk classifications and evidence, and
            record human review decisions prior to execution.
          </p>
        </div>
      </div>

      {/* Security Notice: Browser is not a trusted authorization authority */}
      <Alert variant="warning">
        <ShieldAlert className="h-5 w-5 text-warning" />
        <AlertTitle>Simulated Approval & Risk Governance Environment</AlertTitle>
        <AlertDescription>
          All review decisions and authorization states recorded here are frontend workflow
          demonstrations. They are not cryptographically signed, server-side authorized, or durable
          audit ledgers. Approval does not trigger execution (Execution and WAL mutations are
          strictly managed in Milestone F5).
        </AlertDescription>
      </Alert>

      {/* KPI Overview Cards */}
      <ApprovalKPIOverview requests={requests} />

      {/* Filter and Search Bar */}
      <ApprovalFilterBar
        filters={filters}
        onFilterChange={(updated) => setFilters((prev) => ({ ...prev, ...updated }))}
        pendingCount={pendingCount}
        totalCount={requests.length}
      />

      {/* Main Workspace Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Queue Table */}
        <div className="lg:col-span-7 xl:col-span-7">
          <ApprovalQueueTable
            requests={filteredRequests}
            selectedRequestId={selectedRequestId}
            onSelectRequest={setSelectedRequestId}
          />
        </div>

        {/* Right: Detail Panel */}
        <div className="lg:col-span-5 xl:col-span-5 sticky top-4">
          <ApprovalDetailPanel
            request={selectedRequest}
            onClose={() => setSelectedRequestId(null)}
            onSubmitDecision={handleDecision}
          />
        </div>
      </div>
    </div>
  );
}
