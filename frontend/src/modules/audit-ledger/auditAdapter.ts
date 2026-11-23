import type { AuditBlock, AuditChainVerificationResult } from "./auditTypes";
import { verifyAuditChain } from "./auditLedgerUtils";
import { apiClient } from "../../api/client";
import { MOCK_AUDIT_BLOCKS } from "../../mocks/fixtures";

export interface AuditAdapter {
  getAuditBlocks(): Promise<readonly AuditBlock[]>;
  verifyChain(): Promise<AuditChainVerificationResult>;
}

class MockAuditAdapter implements AuditAdapter {
  private blocks: AuditBlock[] = [...MOCK_AUDIT_BLOCKS];

  async getAuditBlocks(): Promise<readonly AuditBlock[]> {
    try {
      return await apiClient<AuditBlock[]>("/api/v1/audit/blocks");
    } catch {
      return this.blocks;
    }
  }

  async verifyChain(): Promise<AuditChainVerificationResult> {
    try {
      return await apiClient<AuditChainVerificationResult>("/api/v1/audit/verify-chain", {
        method: "POST",
      });
    } catch {
      return await verifyAuditChain(this.blocks);
    }
  }
}

export const auditAdapter: AuditAdapter = new MockAuditAdapter();
