import type {
  ApprovalRequest,
  DecisionSubmitPayload,
  RevisionSubmitPayload,
} from "./approvalTypes";
import {
  approveRequest,
  rejectRequest,
  requestRevision,
  reviseRequest,
} from "./approvalStateMachine";
import { apiClient } from "../../api/client";
import { MOCK_APPROVAL_REQUESTS } from "../../mocks/fixtures";

export interface ApprovalAdapter {
  getRequests(): Promise<readonly ApprovalRequest[]>;
  getRequestById(requestId: string): Promise<ApprovalRequest | null>;
  submitDecision(payload: DecisionSubmitPayload & { requestId: string }): Promise<ApprovalRequest>;
  reviseRequest(payload: RevisionSubmitPayload & { requestId: string }): Promise<ApprovalRequest>;
}

/**
 * Mock Approval Adapter.
 * Clearly marked as a frontend-only simulation; does not claim server-side authorization.
 */
class MockApprovalAdapter implements ApprovalAdapter {
  private requests: ApprovalRequest[] = [...MOCK_APPROVAL_REQUESTS];

  async getRequests(): Promise<readonly ApprovalRequest[]> {
    try {
      const res = await apiClient<ApprovalRequest[]>("/api/v1/approvals");
      return res;
    } catch {
      // Fallback to memory fixtures
      return this.requests;
    }
  }

  async getRequestById(requestId: string): Promise<ApprovalRequest | null> {
    const found = this.requests.find((r) => r.request_id === requestId);
    return found || null;
  }

  async submitDecision(
    payload: DecisionSubmitPayload & { requestId: string }
  ): Promise<ApprovalRequest> {
    const target = this.requests.find((r) => r.request_id === payload.requestId);
    if (!target) {
      throw new Error(`Approval request with ID '${payload.requestId}' was not found.`);
    }

    let updated: ApprovalRequest;
    if (payload.decision === "APPROVED") {
      updated = approveRequest(target, {
        reviewer_identity: payload.reviewer_identity,
        rationale: payload.rationale,
        target_version: payload.target_version,
      });
    } else if (payload.decision === "REJECTED") {
      updated = rejectRequest(target, {
        reviewer_identity: payload.reviewer_identity,
        rationale: payload.rationale || "",
        target_version: payload.target_version,
      });
    } else {
      updated = requestRevision(target, {
        reviewer_identity: payload.reviewer_identity,
        rationale: payload.rationale || "",
        target_version: payload.target_version,
      });
    }

    this.requests = this.requests.map((r) => (r.request_id === updated.request_id ? updated : r));
    return updated;
  }

  async reviseRequest(
    payload: RevisionSubmitPayload & { requestId: string }
  ): Promise<ApprovalRequest> {
    const target = this.requests.find((r) => r.request_id === payload.requestId);
    if (!target) {
      throw new Error(`Approval request with ID '${payload.requestId}' was not found.`);
    }

    const updated = reviseRequest(target, {
      operations: payload.operations,
      author: payload.author,
      revision_note: payload.revision_note,
    });

    this.requests = this.requests.map((r) => (r.request_id === updated.request_id ? updated : r));
    return updated;
  }
}

export const approvalAdapter: ApprovalAdapter = new MockApprovalAdapter();
