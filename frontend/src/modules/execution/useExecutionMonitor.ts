import * as React from "react";
import type { ExecutionFilterState, ExecutionJob } from "./executionTypes";
import { filterAndSortJobs } from "./executionStateMachine";
import { executionAdapter } from "./executionAdapter";

export function useExecutionMonitor(initialJobs?: readonly ExecutionJob[]) {
  const [jobs, setJobs] = React.useState<readonly ExecutionJob[]>(initialJobs || []);
  const [selectedJobId, setSelectedJobId] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(!initialJobs);
  const [error, setError] = React.useState<string | null>(null);
  const [isExecuting, setIsExecuting] = React.useState(false);

  const [filters, setFilters] = React.useState<ExecutionFilterState>({
    search: "",
    state: "all",
    sortBy: "created_at",
    sortAsc: false,
  });

  const loadJobs = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await executionAdapter.getJobs();
      setJobs(data);
      setSelectedJobId((prev) => (prev ? prev : data.length > 0 ? data[0]!.job_id : null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load execution jobs.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!initialJobs) {
      void loadJobs();
    } else {
      setSelectedJobId((prev) =>
        prev ? prev : initialJobs.length > 0 ? initialJobs[0]!.job_id : null
      );
    }
  }, [initialJobs, loadJobs]);

  const filteredJobs = React.useMemo(() => {
    return filterAndSortJobs(jobs, filters.search, filters.state, filters.sortBy, filters.sortAsc);
  }, [jobs, filters]);

  const selectedJob = React.useMemo(() => {
    return jobs.find((j) => j.job_id === selectedJobId) || null;
  }, [jobs, selectedJobId]);

  const handleRunSimulatedJob = React.useCallback(async (jobId: string) => {
    setIsExecuting(true);
    try {
      await executionAdapter.runSimulatedJob(jobId, (updated) => {
        setJobs((prev) => prev.map((j) => (j.job_id === updated.job_id ? updated : j)));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed.");
    } finally {
      setIsExecuting(false);
    }
  }, []);

  const handleRollback = React.useCallback(async (jobId: string, reason: string) => {
    try {
      const updated = await executionAdapter.triggerRollback(jobId, reason);
      setJobs((prev) => prev.map((j) => (j.job_id === updated.job_id ? updated : j)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rollback trigger failed.");
    }
  }, []);

  return {
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
    reload: loadJobs,
    runSimulatedJob: handleRunSimulatedJob,
    triggerRollback: handleRollback,
  };
}
