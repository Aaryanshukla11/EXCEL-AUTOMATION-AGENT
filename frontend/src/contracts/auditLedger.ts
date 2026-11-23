/**
 * Milestone F5: Cryptographic Audit Ledger Contracts.
 * Defines immutable audit blocks, SHA-256 hash-chain structures,
 * and chain verification telemetry.
 */

export type AuditBlockStatus = "COMMITTED" | "ROLLED_BACK" | "FAILED";

export interface AuditBlock {
  readonly block_id: number;
  readonly timestamp: string; // ISO 8601
  readonly block_hash: string; // SHA-256 (64 hex characters)
  readonly previous_hash: string; // SHA-256 (64 hex characters)
  readonly actor: string;
  readonly operation_type: string;
  readonly target_workbook: string;
  readonly target_sheet: string;
  readonly target_range: string;
  readonly payload_summary: string;
  readonly status: AuditBlockStatus;
  readonly execution_job_id?: string | null;
}

export interface AuditChainVerificationResult {
  readonly is_valid: boolean;
  readonly total_blocks: number;
  readonly verified_blocks: number;
  readonly broken_link_index?: number | null;
  readonly error_message?: string | null;
  readonly checked_at: string; // ISO 8601
}
