import { AlertTriangle, Play, ShieldAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/Card";
import { LoadingState } from "../../components/ui/LoadingState";
import { ErrorState } from "../../components/ui/ErrorState";
import { useExecutionMonitor } from "./useExecutionMonitor";
import { ExecutionKPIOverview } from "./ExecutionKPIOverview";
import { WALPipelineTimeline } from "./WALPipelineTimeline";
import { PostFlightVerificationCard } from "./PostFlightVerificationCard";
import { EmergencyAbortButton } from "./EmergencyAbortButton";
import { cn } from "../../lib/utils";

export function ExecutionMonitorPage() {
  const {
    jobs,
    filteredJobs,
    selectedJob,
    selectedJobId,
    setSelectedJobId,
    filters,
    setFilters,
    isLoading,
    isExecuting,
    error,
    reload,
    runSimulatedJob,
    triggerRollback,
  } = useExecutionMonitor();

  if (isLoading) {
    return <LoadingState message="Loading execution pipelines and WAL telemetry..." />;
  }

  if (error && jobs.length === 0) {
    return <ErrorState title="Failed to Load Execution Monitor" message={error} onRetry={reload} />;
  }

  const isRollbackDisabled =
    !selectedJob || (selectedJob.state !== "EXECUTING" && selectedJob.state !== "PREPARING");
  const isRunDisabled =
    !selectedJob ||
    selectedJob.state === "EXECUTING" ||
    selectedJob.state === "COMMITTED" ||
    isExecuting;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Execution & WAL Durability Monitor
            </h1>
            <Badge variant="outline" className="text-xs">
              Phase F5
            </Badge>
            <Badge variant="warning" className="text-xs">
              [SIMULATION ENGINE]
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Real-time observability into the 6-phase atomic Write-Ahead Logging (WAL) protocol with
            hardware-flushed replace semantics and emergency rollback triggers.
          </p>
        </div>

        {selectedJob && (
          <div className="flex items-center space-x-2">
            <EmergencyAbortButton
              jobId={selectedJob.job_id}
              disabled={isRollbackDisabled}
              onAbort={triggerRollback}
            />
            <Button
              size="sm"
              disabled={isRunDisabled}
              onClick={() => runSimulatedJob(selectedJob.job_id)}
              className="text-xs h-8 font-semibold shadow-sm"
              data-testid="run-pipeline-button"
            >
              <Play className="h-3.5 w-3.5 mr-1.5" />
              {isExecuting ? "Executing..." : "Run WAL Pipeline"}
            </Button>
          </div>
        )}
      </div>

      {/* Security Advisory Banner */}
      <Alert variant="warning">
        <ShieldAlert className="h-5 w-5 text-warning" />
        <AlertTitle>Simulated Execution & Durability Environment</AlertTitle>
        <AlertDescription>
          This console demonstrates the 6-phase atomic Write-Ahead Logging sequence and pre-state
          rollback triggers. Live physical workbook file mutation and direct filesystem replaces
          remain strictly deferred until backend service integration.
        </AlertDescription>
      </Alert>

      {/* KPI Overview */}
      <ExecutionKPIOverview jobs={jobs} />

      {/* Main Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Job Queue List */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Execution Jobs ({filteredJobs.length})
            </h3>
            <div className="flex items-center space-x-1.5">
              {(["all", "COMMITTED", "ROLLED_BACK", "IDLE"] as const).map((st) => (
                <button
                  key={st}
                  onClick={() => setFilters({ ...filters, state: st })}
                  className={cn(
                    "text-[10px] px-2 py-0.5 rounded font-medium transition-colors",
                    filters.state === st
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  )}
                >
                  {st === "all" ? "All" : st}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card divide-y divide-border overflow-hidden">
            {filteredJobs.map((j) => {
              const isSelected = selectedJobId === j.job_id;
              const stateBadgeVariant =
                j.state === "COMMITTED"
                  ? "success"
                  : j.state === "ROLLED_BACK"
                    ? "warning"
                    : j.state === "EXECUTING"
                      ? "default"
                      : "outline";

              return (
                <div
                  key={j.job_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedJobId(j.job_id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      setSelectedJobId(j.job_id);
                    }
                  }}
                  className={cn(
                    "p-3 text-xs transition-colors cursor-pointer hover:bg-muted/40 space-y-1 focus:outline-none focus:bg-muted/50",
                    isSelected && "bg-muted/60 border-l-4 border-l-primary"
                  )}
                  data-testid={`execution-job-${j.job_id}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-semibold text-foreground">{j.job_id}</span>
                    <Badge
                      variant={stateBadgeVariant}
                      className="text-[10px] uppercase font-semibold"
                    >
                      {j.state}
                    </Badge>
                  </div>
                  <div className="text-foreground truncate font-medium">{j.target_workbook}</div>
                  <div className="text-[10px] text-muted-foreground flex items-center justify-between pt-0.5">
                    <span>Plan: {j.plan_id}</span>
                    <span>{new Date(j.created_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Pipeline Visualizer & Post-Flight Telemetry */}
        <div className="lg:col-span-7 space-y-6">
          {selectedJob ? (
            <>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <div className="space-y-0.5">
                    <CardTitle className="text-sm font-semibold text-foreground">
                      Pipeline Inspector: {selectedJob.job_id}
                    </CardTitle>
                    <p className="text-xs text-muted-foreground">
                      Target: {selectedJob.target_workbook} • Plan: {selectedJob.plan_id}
                    </p>
                  </div>
                  <Badge variant={selectedJob.state === "COMMITTED" ? "success" : "default"}>
                    {selectedJob.state}
                  </Badge>
                </CardHeader>
                <CardContent className="pt-2">
                  {selectedJob.rollback_reason && (
                    <div className="mb-4 rounded border border-warning/40 bg-warning/10 p-3 text-xs text-warning flex items-start space-x-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-semibold block">Rollback Triggered</span>
                        <span>{selectedJob.rollback_reason}</span>
                      </div>
                    </div>
                  )}

                  <WALPipelineTimeline job={selectedJob} />
                </CardContent>
              </Card>

              <PostFlightVerificationCard verification={selectedJob.verification} />
            </>
          ) : (
            <Card>
              <CardContent className="p-12 text-center text-xs text-muted-foreground">
                Select an execution job from the queue to inspect its 6-phase WAL sequence.
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
