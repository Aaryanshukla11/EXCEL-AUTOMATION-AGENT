import type {
  ApprovalRequest,
  DecisionSubmitPayload,
  RevisionSubmitPayload,
} from "./approvalTypes";
import { apiClient, ApiError } from "../../api/client";

export interface ApprovalAdapter {
  getRequests(): Promise<readonly ApprovalRequest[]>;
  getRequestById(requestId: string): Promise<ApprovalRequest | null>;
  submitDecision(payload: DecisionSubmitPayload & { requestId: string }): Promise<ApprovalRequest>;
  reviseRequest(payload: RevisionSubmitPayload & { requestId: string; target_version?: number }): Promise<ApprovalRequest>;
  cancelRequest(payload: { requestId: string; target_version: number; rationale?: string }): Promise<ApprovalRequest>;
  submitForReview(payload: { requestId: string; target_version: number }): Promise<ApprovalRequest>;
}

/**
 * Production HTTP Approval Adapter.
 * Integrates directly with the authenticated B6 FastAPI backend endpoints (/api/v1/approvals).
 * Propagates real HTTP status errors (401, 403, 404, 409, 410) without mock fallbacks.
 */
export class HttpApprovalAdapter implements ApprovalAdapter {
  async getRequests(): Promise<readonly ApprovalRequest[]> {
    return await apiClient<ApprovalRequest[]>("/api/v1/approvals");
  }

  async getRequestById(requestId: string): Promise<ApprovalRequest | null> {
    try {
      return await apiClient<ApprovalRequest>(`/api/v1/approvals/${encodeURIComponent(requestId)}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return null;
      }
      throw err;
    }
  }

  async submitDecision(
    payload: DecisionSubmitPayload & { requestId: string }
  ): Promise<ApprovalRequest> {
    return await apiClient<ApprovalRequest>(
      `/api/v1/approvals/${encodeURIComponent(payload.requestId)}/decision`,
      {
        method: "POST",
        body: JSON.stringify({
          decision: payload.decision,
          target_version: payload.target_version,
          rationale: payload.rationale || undefined,
        }),
      }
    );
  }

  async reviseRequest(
    payload: RevisionSubmitPayload & { requestId: string; target_version?: number }
  ): Promise<ApprovalRequest> {
    return await apiClient<ApprovalRequest>(
      `/api/v1/approvals/${encodeURIComponent(payload.requestId)}/resubmit`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_version: payload.target_version ?? 1,
          revised_operations: payload.operations,
          revision_note: payload.revision_note,
        }),
      }
    );
  }

  async cancelRequest(
    payload: { requestId: string; target_version: number; rationale?: string }
  ): Promise<ApprovalRequest> {
    return await apiClient<ApprovalRequest>(
      `/api/v1/approvals/${encodeURIComponent(payload.requestId)}/cancel`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_version: payload.target_version,
          rationale: payload.rationale,
        }),
      }
    );
  }

  async submitForReview(
    payload: { requestId: string; target_version: number }
  ): Promise<ApprovalRequest> {
    return await apiClient<ApprovalRequest>(
      `/api/v1/approvals/${encodeURIComponent(payload.requestId)}/submit`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_version: payload.target_version,
        }),
      }
    );
  }
}

export const approvalAdapter: ApprovalAdapter = new HttpApprovalAdapter();

