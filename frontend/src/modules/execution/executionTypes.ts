import type {
  ExecutionJob,
  ExecutionPhaseDetail,
  ExecutionState,
  PhaseStatus,
  WALPhase,
} from "../../contracts/execution";

export interface ExecutionFilterState {
  search: string;
  state: ExecutionState | "all";
  sortBy: "created_at" | "job_id";
  sortAsc: boolean;
}

export type { ExecutionJob, ExecutionPhaseDetail, ExecutionState, PhaseStatus, WALPhase };
