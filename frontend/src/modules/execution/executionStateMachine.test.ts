import { describe, expect, it } from "vitest";
import {
  canTriggerRollback,
  createInitialPhases,
  filterAndSortJobs,
  transitionPhase,
  triggerRollback,
} from "./executionStateMachine";
import type { ExecutionJob } from "./executionTypes";

describe("Execution & WAL State Machine (F5)", () => {
  const sampleJob: ExecutionJob = {
    job_id: "JOB-TEST-1",
    plan_id: "PLAN-1",
    target_workbook: "model.xlsx",
    state: "PREPARING",
    current_phase: null,
    phases: createInitialPhases(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  it("initializes exactly 6 WAL phases in pending status", () => {
    const phases = createInitialPhases();
    expect(phases).toHaveLength(6);
    expect(phases[0]!.phase).toBe("PRE_STATE_SNAPSHOT");
    expect(phases[5]!.phase).toBe("WAL_COMMITTED");
    expect(phases.every((p) => p.status === "pending")).toBe(true);
  });

  it("transitions phase status and updates job state to EXECUTING", () => {
    const updated = transitionPhase(sampleJob, "PRE_STATE_SNAPSHOT", "running");
    expect(updated.state).toBe("EXECUTING");
    expect(updated.current_phase).toBe("PRE_STATE_SNAPSHOT");
    expect(updated.phases[0]!.status).toBe("running");
  });

  it("enforces sequential WAL execution and rejects phase skipping", () => {
    // Attempting to jump directly to ATOMIC_REPLACE (phase 4) while phase 1 is pending
    expect(() => transitionPhase(sampleJob, "ATOMIC_REPLACE", "running")).toThrowError(
      /cannot execute phase 'ATOMIC_REPLACE' before preceding phase/
    );
  });

  it("completing all phases sequentially sets job state to COMMITTED", () => {
    let job = sampleJob;
    const phaseOrder = [
      "PRE_STATE_SNAPSHOT",
      "WAL_INTENT_RECORDED",
      "STAGED_MUTATION_FSYNC",
      "ATOMIC_REPLACE",
      "PARENT_DIR_SYNC",
      "WAL_COMMITTED",
    ] as const;

    for (const phase of phaseOrder) {
      job = transitionPhase(job, phase, "running");
      job = transitionPhase(job, phase, "completed");
    }

    expect(job.state).toBe("COMMITTED");
    expect(job.phases[5]!.status).toBe("completed");
  });

  it("rejects phase transitions on terminal COMMITTED or ROLLED_BACK jobs", () => {
    const committedJob: ExecutionJob = {
      ...sampleJob,
      state: "COMMITTED",
    };
    expect(() => transitionPhase(committedJob, "PRE_STATE_SNAPSHOT", "running")).toThrowError(
      /Cannot transition phases on a terminal 'COMMITTED'/
    );

    const rolledBackJob: ExecutionJob = {
      ...sampleJob,
      state: "ROLLED_BACK",
    };
    expect(() => transitionPhase(rolledBackJob, "PRE_STATE_SNAPSHOT", "running")).toThrowError(
      /Cannot transition phases on a terminal 'ROLLED_BACK'/
    );
  });

  it("triggers emergency rollback and marks pending phases as rolled_back", () => {
    const executingJob: ExecutionJob = {
      ...sampleJob,
      state: "EXECUTING",
      phases: sampleJob.phases.map((p, i) =>
        i === 0
          ? { ...p, status: "completed" as const }
          : i === 1
            ? { ...p, status: "running" as const }
            : p
      ),
    };

    expect(canTriggerRollback(executingJob)).toBe(true);

    const rolledBack = triggerRollback(executingJob, "I/O lock failure");
    expect(rolledBack.state).toBe("ROLLED_BACK");
    expect(rolledBack.rollback_reason).toBe("I/O lock failure");
    expect(rolledBack.phases[1]!.status).toBe("failed");
    expect(rolledBack.phases[2]!.status).toBe("rolled_back");
    expect(rolledBack.verification?.integrity_status).toBe("verified");
  });

  it("rejects rollback trigger on already COMMITTED jobs", () => {
    const committedJob: ExecutionJob = {
      ...sampleJob,
      state: "COMMITTED",
    };

    expect(canTriggerRollback(committedJob)).toBe(false);
    expect(() => triggerRollback(committedJob, "Too late")).toThrowError(
      /Cannot rollback execution job in 'COMMITTED' state/
    );
  });

  it("filters and sorts execution jobs", () => {
    const jobs: ExecutionJob[] = [
      { ...sampleJob, job_id: "JOB-A", state: "COMMITTED", created_at: "2026-11-23T10:00:00Z" },
      { ...sampleJob, job_id: "JOB-B", state: "ROLLED_BACK", created_at: "2026-11-23T11:00:00Z" },
      { ...sampleJob, job_id: "JOB-C", state: "IDLE", created_at: "2026-11-23T09:00:00Z" },
    ];

    const filtered = filterAndSortJobs(jobs, "JOB-A", "all");
    expect(filtered).toHaveLength(1);
    expect(filtered[0]!.job_id).toBe("JOB-A");

    const stateFiltered = filterAndSortJobs(jobs, "", "ROLLED_BACK");
    expect(stateFiltered).toHaveLength(1);
    expect(stateFiltered[0]!.job_id).toBe("JOB-B");
  });
});
