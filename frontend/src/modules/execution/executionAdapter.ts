import type { ExecutionJob } from "./executionTypes";
import { transitionPhase, triggerRollback } from "./executionStateMachine";
import { apiClient } from "../../api/client";
import { MOCK_EXECUTION_JOBS } from "../../mocks/fixtures";

export interface ExecutionAdapter {
  getJobs(): Promise<readonly ExecutionJob[]>;
  getJobById(jobId: string): Promise<ExecutionJob | null>;
  triggerRollback(jobId: string, reason: string): Promise<ExecutionJob>;
  runSimulatedJob(
    jobId: string,
    onStep?: (updatedJob: ExecutionJob) => void
  ): Promise<ExecutionJob>;
}

class MockExecutionAdapter implements ExecutionAdapter {
  private jobs: ExecutionJob[] = [...MOCK_EXECUTION_JOBS];

  async getJobs(): Promise<readonly ExecutionJob[]> {
    try {
      return await apiClient<ExecutionJob[]>("/api/v1/execution/jobs");
    } catch {
      return this.jobs;
    }
  }

  async getJobById(jobId: string): Promise<ExecutionJob | null> {
    const found = this.jobs.find((j) => j.job_id === jobId);
    return found || null;
  }

  async triggerRollback(jobId: string, reason: string): Promise<ExecutionJob> {
    const target = this.jobs.find((j) => j.job_id === jobId);
    if (!target) {
      throw new Error(`Job '${jobId}' not found.`);
    }

    const updated = triggerRollback(target, reason);
    this.jobs = this.jobs.map((j) => (j.job_id === updated.job_id ? updated : j));
    return updated;
  }

  async runSimulatedJob(
    jobId: string,
    onStep?: (updatedJob: ExecutionJob) => void
  ): Promise<ExecutionJob> {
    let job = this.jobs.find((j) => j.job_id === jobId);
    if (!job) {
      throw new Error(`Job '${jobId}' not found.`);
    }

    // Set preparing
    job = { ...job, state: "EXECUTING" };
    onStep?.(job);

    for (const phaseDef of job.phases) {
      // Step running
      job = transitionPhase(job, phaseDef.phase, "running");
      onStep?.(job);

      // Brief delay for simulation
      await new Promise((resolve) => setTimeout(resolve, 80));

      // Step completed
      job = transitionPhase(job, phaseDef.phase, "completed");
      onStep?.(job);
    }

    // Attach post-flight verification
    job = {
      ...job,
      state: "COMMITTED",
      current_phase: "WAL_COMMITTED",
      verification: {
        cells_written: 1240,
        sheets_affected: 2,
        pre_run_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        post_run_sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        backup_path: `C:/data/backups/${job.target_workbook}.bak`,
        integrity_status: "verified",
      },
    };

    this.jobs = this.jobs.map((j) => (j.job_id === job!.job_id ? job! : j));
    onStep?.(job);
    return job;
  }
}

export const executionAdapter: ExecutionAdapter = new MockExecutionAdapter();
