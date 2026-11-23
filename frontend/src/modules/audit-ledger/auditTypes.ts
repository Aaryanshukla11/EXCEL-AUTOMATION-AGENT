import type {
  AuditBlock,
  AuditBlockStatus,
  AuditChainVerificationResult,
} from "../../contracts/auditLedger";

export interface AuditFilterState {
  search: string;
  status: AuditBlockStatus | "all";
  actor: string;
  operationType: string;
  sortBy: "block_id" | "timestamp";
  sortAsc: boolean;
}

export type { AuditBlock, AuditBlockStatus, AuditChainVerificationResult };
