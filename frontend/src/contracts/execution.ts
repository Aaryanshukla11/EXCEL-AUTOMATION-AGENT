/**
 * Milestone F5: Execution & WAL Durability Monitor Contracts.
 * Defines the 6-phase atomic Write-Ahead Logging (WAL) state machine,
 * rollback triggers, and post-flight verification telemetry.
 */

export type WALPhase =
  | "PRE_STATE_SNAPSHOT"
  | "WAL_INTENT_RECORDED"
  | "STAGED_MUTATION_FSYNC"
  | "ATOMIC_REPLACE"
  | "PARENT_DIR_SYNC"
  | "WAL_COMMITTED";

export type ExecutionState =
  "IDLE" | "PREPARING" | "EXECUTING" | "COMMITTED" | "ROLLING_BACK" | "ROLLED_BACK" | "FAILED";

export type PhaseStatus = "pending" | "running" | "completed" | "failed" | "rolled_back";

export interface ExecutionPhaseDetail {
  readonly phase: WALPhase;
  readonly phase_number: number; // 1 to 6
  readonly title: string;
  readonly description: string;
  readonly status: PhaseStatus;
  readonly started_at?: string | null;
  readonly completed_at?: string | null;
  readonly duration_ms?: number | null;
  readonly error?: string | null;
}

export interface PostFlightVerification {
  readonly cells_written: number;
  readonly sheets_affected: number;
  readonly pre_run_sha256: string;
  readonly post_run_sha256: string;
  readonly backup_path: string;
  readonly integrity_status: "verified" | "unverified" | "mismatch";
}

export interface ExecutionJob {
  readonly job_id: string;
  readonly plan_id: string;
  readonly target_workbook: string;
  readonly state: ExecutionState;
  readonly current_phase: WALPhase | null;
  readonly phases: readonly ExecutionPhaseDetail[];
  readonly created_at: string;
  readonly updated_at: string;
  readonly completed_at?: string | null;
  readonly rollback_reason?: string | null;
  readonly verification?: PostFlightVerification | null;
  readonly is_mock_simulation?: boolean;
}
