import type {
  ExecutionJob,
  ExecutionPhaseDetail,
  ExecutionState,
  PhaseStatus,
  WALPhase,
} from "./executionTypes";

export const WAL_PHASE_DEFINITIONS: readonly {
  phase: WALPhase;
  phase_number: number;
  title: string;
  description: string;
}[] = [
  {
    phase: "PRE_STATE_SNAPSHOT",
    phase_number: 1,
    title: "Pre-State Snapshot (.bak)",
    description: "Creates physical byte-for-byte pre-state backup snapshot on disk.",
  },
  {
    phase: "WAL_INTENT_RECORDED",
    phase_number: 2,
    title: "WAL Intent Journaling",
    description: "Records atomic intent with HMAC-signed token into WAL log.",
  },
  {
    phase: "STAGED_MUTATION_FSYNC",
    phase_number: 3,
    title: "Staged Mutation & Fsync",
    description: "Writes modified workbook bytes to isolated scratch file and invokes fsync.",
  },
  {
    phase: "ATOMIC_REPLACE",
    phase_number: 4,
    title: "Atomic Replacement",
    description: "Executes atomic POSIX/Win32 MoveFileEx replace with REPLACE_EXISTING.",
  },
  {
    phase: "PARENT_DIR_SYNC",
    phase_number: 5,
    title: "Parent Directory Flush",
    description: "Flushes directory entry to physical media storage controller.",
  },
  {
    phase: "WAL_COMMITTED",
    phase_number: 6,
    title: "WAL Finalized & Committed",
    description: "Appends commit marker to WAL, releases advisory locks, logs audit event.",
  },
];

export function createInitialPhases(): ExecutionPhaseDetail[] {
  return WAL_PHASE_DEFINITIONS.map((def) => ({
    phase: def.phase,
    phase_number: def.phase_number,
    title: def.title,
    description: def.description,
    status: "pending",
  }));
}

/**
 * Checks whether an execution job can be aborted/rolled back.
 * A committed or already rolled back job can NEVER be rolled back.
 */
export function canTriggerRollback(job: ExecutionJob): boolean {
  return job.state === "PREPARING" || job.state === "EXECUTING";
}

/**
 * Updates a specific phase status within an execution job.
 * Enforces:
 * 1. Terminal states (COMMITTED, ROLLED_BACK) cannot transition.
 * 2. Sequential execution: cannot skip preceding phases.
 */
export function transitionPhase(
  job: ExecutionJob,
  targetPhase: WALPhase,
  status: PhaseStatus,
  error?: string
): ExecutionJob {
  if (job.state === "COMMITTED" || job.state === "ROLLED_BACK") {
    throw new Error(`Cannot transition phases on a terminal '${job.state}' execution job.`);
  }

  const targetIndex = job.phases.findIndex((p) => p.phase === targetPhase);
  if (targetIndex === -1) {
    throw new Error(`Unknown WAL phase '${targetPhase}'.`);
  }

  // Enforce sequential order: preceding phases must be completed
  if ((status === "running" || status === "completed") && targetIndex > 0) {
    const prevPhase = job.phases[targetIndex - 1]!;
    if (prevPhase.status !== "completed") {
      throw new Error(
        `Invalid WAL phase transition: cannot execute phase '${targetPhase}' before preceding phase '${prevPhase.phase}' is completed.`
      );
    }
  }

  const now = new Date().toISOString();
  const updatedPhases = job.phases.map((p) => {
    if (p.phase === targetPhase) {
      return {
        ...p,
        status,
        started_at: p.started_at || (status === "running" ? now : null),
        completed_at: status === "completed" || status === "failed" ? now : p.completed_at,
        error: error || p.error,
      };
    }
    return p;
  });

  let nextState: ExecutionState = job.state;
  if (status === "failed") {
    nextState = "FAILED";
  } else if (targetPhase === "WAL_COMMITTED" && status === "completed") {
    nextState = "COMMITTED";
  } else if (status === "running") {
    nextState = "EXECUTING";
  }

  return {
    ...job,
    state: nextState,
    current_phase: targetPhase,
    phases: updatedPhases,
    updated_at: now,
    completed_at: nextState === "COMMITTED" || nextState === "FAILED" ? now : job.completed_at,
  };
}

/**
 * Pure transition executing an emergency rollback on an active job.
 */
export function triggerRollback(job: ExecutionJob, reason: string): ExecutionJob {
  if (!canTriggerRollback(job)) {
    throw new Error(`Cannot rollback execution job in '${job.state}' state.`);
  }

  const now = new Date().toISOString();
  const updatedPhases = job.phases.map((p) => {
    if (p.status === "running") {
      return {
        ...p,
        status: "failed" as const,
        completed_at: now,
        error: "Emergency abort invoked.",
      };
    }
    if (p.status === "pending") {
      return { ...p, status: "rolled_back" as const };
    }
    return p;
  });

  return {
    ...job,
    state: "ROLLED_BACK",
    updated_at: now,
    completed_at: now,
    rollback_reason: reason,
    phases: updatedPhases,
    verification: {
      cells_written: 0,
      sheets_affected: 0,
      pre_run_sha256: "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
      post_run_sha256: "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
      backup_path: `C:/data/backups/${job.target_workbook}.bak`,
      integrity_status: "verified",
    },
  };
}

/**
 * In-memory filter and sort helper for execution jobs.
 */
export function filterAndSortJobs(
  jobs: readonly ExecutionJob[],
  search: string,
  stateFilter: ExecutionState | "all",
  sortBy: "created_at" | "job_id" = "created_at",
  sortAsc = false
): ExecutionJob[] {
  const query = search.trim().toLowerCase();
  const hasQuery = query.length > 0;

  return jobs
    .filter((j) => {
      if (stateFilter !== "all" && j.state !== stateFilter) return false;
      if (!hasQuery) return true;
      return (
        j.job_id.toLowerCase().includes(query) ||
        j.target_workbook.toLowerCase().includes(query) ||
        j.plan_id.toLowerCase().includes(query)
      );
    })
    .sort((a, b) => {
      let comp = 0;
      if (sortBy === "created_at") {
        comp = a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
      } else if (sortBy === "job_id") {
        comp = a.job_id.localeCompare(b.job_id);
      }
      return sortAsc ? comp : -comp;
    });
}
