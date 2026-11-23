import { describe, expect, it } from "vitest";
import {
  assessOperationRisk,
  canTransition,
  isDecisionStale,
  submitForReview,
  approveRequest,
  rejectRequest,
  requestRevision,
  reviseRequest,
} from "./approvalStateMachine";
import type { ApprovalRequest } from "./approvalTypes";

describe("HITL Approval State Machine & Risk Governance (F4)", () => {
  const mockBaseRequest: ApprovalRequest = {
    request_id: "TEST-001",
    title: "Test Operation Proposal",
    state: "DRAFT",
    version: 1,
    risk: {
      category: "non_destructive",
      level: "medium",
      score: 0.4,
      title: "Non-Destructive",
      explanation: "Test",
      evidence: ["Sample evidence"],
      requires_mandatory_review: true,
    },
    operations: [
      {
        op_id: "op_01",
        op_type: "APPEND_ROWS",
        sheet_name: "Revenue",
        target_range: "B6:B10",
        description: "Append rows test",
      },
    ],
    created_at: "2026-11-23T00:00:00Z",
    updated_at: "2026-11-23T00:00:00Z",
    decision: null,
    decision_history: [],
    source_references: ["test.xlsx"],
  };

  describe("State Transition Validation", () => {
    it("allows valid transitions from DRAFT to PENDING_REVIEW and CANCELLED", () => {
      expect(canTransition("DRAFT", "PENDING_REVIEW")).toBe(true);
      expect(canTransition("DRAFT", "CANCELLED")).toBe(true);
      expect(canTransition("DRAFT", "APPROVED")).toBe(false);
      expect(canTransition("DRAFT", "REJECTED")).toBe(false);
    });

    it("allows valid transitions from PENDING_REVIEW to APPROVED, REJECTED, NEEDS_REVISION", () => {
      expect(canTransition("PENDING_REVIEW", "APPROVED")).toBe(true);
      expect(canTransition("PENDING_REVIEW", "REJECTED")).toBe(true);
      expect(canTransition("PENDING_REVIEW", "NEEDS_REVISION")).toBe(true);
      expect(canTransition("PENDING_REVIEW", "EXPIRED")).toBe(true);
      expect(canTransition("PENDING_REVIEW", "CANCELLED")).toBe(true);
      expect(canTransition("PENDING_REVIEW", "DRAFT")).toBe(false);
    });

    it("treats APPROVED, REJECTED, and CANCELLED as terminal for that request version", () => {
      expect(canTransition("APPROVED", "PENDING_REVIEW")).toBe(false);
      expect(canTransition("APPROVED", "REJECTED")).toBe(false);
      expect(canTransition("REJECTED", "APPROVED")).toBe(false);
      expect(canTransition("CANCELLED", "PENDING_REVIEW")).toBe(false);
    });
  });

  describe("Approval & Rejection Workflow", () => {
    it("submits DRAFT request for review and appends audit event", () => {
      const pending = submitForReview(mockBaseRequest, "Test Orchestrator");
      expect(pending.state).toBe("PENDING_REVIEW");
      expect(pending.decision_history).toHaveLength(1);
      expect(pending.decision_history[0]!.event_type).toBe("SUBMITTED_FOR_REVIEW");
      expect(pending.decision_history[0]!.actor).toBe("Test Orchestrator");
    });

    it("approves request and records decision details", () => {
      const pending = submitForReview(mockBaseRequest);
      const approved = approveRequest(pending, {
        reviewer_identity: "Test Reviewer",
        rationale: "Approved after manual check",
        target_version: 1,
      });

      expect(approved.state).toBe("APPROVED");
      expect(approved.decision?.decision).toBe("APPROVED");
      expect(approved.decision?.reviewer_identity).toBe("Test Reviewer");
      expect(approved.decision?.rationale).toBe("Approved after manual check");
      expect(approved.decision_history).toHaveLength(2);
      expect(approved.decision_history[1]!.event_type).toBe("APPROVED");
    });

    it("rejects request with mandatory rationale and enforces minimum length", () => {
      const pending = submitForReview(mockBaseRequest);

      // Fails on empty or too short rationale
      expect(() =>
        rejectRequest(pending, {
          reviewer_identity: "Test Reviewer",
          rationale: "Bad", // < 5 chars
          target_version: 1,
        })
      ).toThrow(/Mandatory rejection rationale/);

      const rejected = rejectRequest(pending, {
        reviewer_identity: "Test Reviewer",
        rationale: "Schema violates client column layout rules",
        target_version: 1,
      });

      expect(rejected.state).toBe("REJECTED");
      expect(rejected.decision?.decision).toBe("REJECTED");
      expect(rejected.decision?.rationale).toBe("Schema violates client column layout rules");
    });

    it("requests revision with mandatory rationale", () => {
      const pending = submitForReview(mockBaseRequest);

      expect(() =>
        requestRevision(pending, {
          reviewer_identity: "Test Reviewer",
          rationale: "",
          target_version: 1,
        })
      ).toThrow(/Mandatory revision rationale/);

      const revised = requestRevision(pending, {
        reviewer_identity: "Test Reviewer",
        rationale: "Please split into 2 smaller batches",
        target_version: 1,
      });

      expect(revised.state).toBe("NEEDS_REVISION");
      expect(revised.decision?.decision).toBe("NEEDS_REVISION");
    });
  });

  describe("Version Increments & Stale Decision Protection", () => {
    it("increments version and clears stale decision when revised", () => {
      const pending = submitForReview(mockBaseRequest);
      const revisionRequested = requestRevision(pending, {
        reviewer_identity: "Reviewer A",
        rationale: "Requires updated range coordinates",
        target_version: 1,
      });

      const updatedReq = reviseRequest(revisionRequested, {
        operations: [
          {
            op_id: "op_01_v2",
            op_type: "APPEND_ROWS",
            sheet_name: "Revenue",
            target_range: "B6:B15",
            description: "Updated range",
          },
        ],
        author: "Remediation Agent",
        revision_note: "Adjusted range to B6:B15",
      });

      expect(updatedReq.version).toBe(2);
      expect(updatedReq.state).toBe("PENDING_REVIEW");
      expect(updatedReq.decision).toBeNull(); // Stale decision cleared
      expect(isDecisionStale(updatedReq, 1)).toBe(true);
      expect(isDecisionStale(updatedReq, 2)).toBe(false);

      // Attempting to apply decision targeting version 1 must be rejected
      expect(() =>
        approveRequest(updatedReq, {
          reviewer_identity: "Reviewer B",
          target_version: 1,
        })
      ).toThrow(/Stale decision rejected/);

      // Applying decision targeting version 2 succeeds
      const approvedV2 = approveRequest(updatedReq, {
        reviewer_identity: "Reviewer B",
        target_version: 2,
      });
      expect(approvedV2.state).toBe("APPROVED");
      expect(approvedV2.version).toBe(2);
    });
  });

  describe("Risk Classification & Conservative Fallback", () => {
    it("classifies read-only operations as low risk", () => {
      const risk = assessOperationRisk({ op_type: "READ_ONLY" });
      expect(risk.category).toBe("read_only");
      expect(risk.level).toBe("low");
      expect(risk.requires_mandatory_review).toBe(false);
    });

    it("classifies populated cell overwrites as high risk", () => {
      const risk = assessOperationRisk({ op_type: "UPDATE_CELL" });
      expect(risk.category).toBe("overwrite_replacement");
      expect(risk.level).toBe("high");
      expect(risk.requires_mandatory_review).toBe(true);
    });

    it("classifies destructive column drops as critical risk", () => {
      const risk = assessOperationRisk({ op_type: "DROP_COLUMN" });
      expect(risk.category).toBe("destructive");
      expect(risk.level).toBe("critical");
      expect(risk.requires_mandatory_review).toBe(true);
    });

    it("defaults unknown or unrecognized operations conservatively to critical review-required", () => {
      const risk = assessOperationRisk({ op_type: "CUSTOM_UNKNOWN_OP" });
      expect(risk.category).toBe("unresolved_unsupported");
      expect(risk.level).toBe("critical");
      expect(risk.requires_mandatory_review).toBe(true);
      expect(risk.explanation).toMatch(/Conservative security policy/);
    });
  });
});
