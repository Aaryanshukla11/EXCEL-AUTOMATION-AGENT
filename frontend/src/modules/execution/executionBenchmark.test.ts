import { describe, expect, it } from "vitest";
import type { ExecutionJob } from "./executionTypes";
import { createInitialPhases, filterAndSortJobs } from "./executionStateMachine";

describe("Execution Monitor Large-Scale Benchmark (F5)", () => {
  it("filters and sorts 1,000 execution jobs under 50 milliseconds", () => {
    const jobs: ExecutionJob[] = Array.from({ length: 1000 }).map((_, i) => ({
      job_id: `JOB-${i + 1}`,
      plan_id: `PLAN-${(i % 50) + 1}`,
      target_workbook: `model_sheet_${i % 20}.xlsx`,
      state: i % 3 === 0 ? "COMMITTED" : i % 3 === 1 ? "ROLLED_BACK" : "IDLE",
      current_phase: i % 3 === 0 ? "WAL_COMMITTED" : null,
      phases: createInitialPhases(),
      created_at: new Date(Date.now() - i * 100000).toISOString(),
      updated_at: new Date().toISOString(),
    }));

    const startTime = performance.now();
    const filtered = filterAndSortJobs(jobs, "model_sheet_4", "COMMITTED", "created_at", false);
    const duration = performance.now() - startTime;

    expect(filtered.length).toBeGreaterThan(0);
    expect(duration).toBeLessThan(50);
  });

  it("filters and sorts 5,000 execution jobs under 100 milliseconds", () => {
    const jobs: ExecutionJob[] = Array.from({ length: 5000 }).map((_, i) => ({
      job_id: `JOB-${i + 1}`,
      plan_id: `PLAN-${(i % 100) + 1}`,
      target_workbook: `enterprise_rollup_${i % 50}.xlsx`,
      state: i % 2 === 0 ? "COMMITTED" : "ROLLED_BACK",
      current_phase: "WAL_COMMITTED",
      phases: createInitialPhases(),
      created_at: new Date(Date.now() - i * 50000).toISOString(),
      updated_at: new Date().toISOString(),
    }));

    const startTime = performance.now();
    const filtered = filterAndSortJobs(jobs, "enterprise_rollup", "all", "job_id", true);
    const duration = performance.now() - startTime;

    expect(filtered).toHaveLength(5000);
    expect(duration).toBeLessThan(100);
  });
});
