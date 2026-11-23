import { describe, expect, it } from "vitest";
import type { ApprovalRequest } from "./approvalTypes";
import { filterAndSortApprovalRequests } from "./approvalStateMachine";

describe("Approval Console Large-Scale Benchmark (F4)", () => {
  it("filters and sorts 500 approval requests under 20 milliseconds", () => {
    const requests: ApprovalRequest[] = Array.from({ length: 500 }).map((_, i) => ({
      request_id: `REQ-${i + 1}`,
      title: `Operation proposal #${i + 1}`,
      state:
        i % 4 === 0
          ? "PENDING_REVIEW"
          : i % 4 === 1
            ? "APPROVED"
            : i % 4 === 2
              ? "REJECTED"
              : "DRAFT",
      version: (i % 3) + 1,
      risk: {
        category:
          i % 3 === 0 ? "non_destructive" : i % 3 === 1 ? "overwrite_replacement" : "destructive",
        level: i % 3 === 0 ? "medium" : i % 3 === 1 ? "high" : "critical",
        score: 0.5,
        title: "Test Risk",
        explanation: "Benchmark explanation",
        evidence: [],
        requires_mandatory_review: true,
      },
      operations: [],
      created_at: new Date(Date.now() - i * 100000).toISOString(),
      updated_at: new Date().toISOString(),
      decision_history: [],
      source_references: [],
    }));

    const startTime = performance.now();
    const filtered = filterAndSortApprovalRequests(
      requests,
      "proposal #1",
      "all",
      "all",
      "all",
      "created_at",
      false
    );
    const duration = performance.now() - startTime;

    expect(filtered.length).toBeGreaterThan(0);
    expect(duration).toBeLessThan(20);
  });

  it("filters and sorts 1,000 approval requests under 50 milliseconds", () => {
    const requests: ApprovalRequest[] = Array.from({ length: 1000 }).map((_, i) => ({
      request_id: `REQ-${i + 1}`,
      title: `Batch proposal #${i + 1}`,
      state: i % 2 === 0 ? "PENDING_REVIEW" : "APPROVED",
      version: 1,
      risk: {
        category: "overwrite_replacement",
        level: "high",
        score: 0.75,
        title: "High Risk Overwrite",
        explanation: "Overwrite risk",
        evidence: [],
        requires_mandatory_review: true,
      },
      operations: [],
      created_at: new Date(Date.now() - i * 50000).toISOString(),
      updated_at: new Date().toISOString(),
      decision_history: [],
      source_references: [],
    }));

    const startTime = performance.now();
    const filtered = filterAndSortApprovalRequests(
      requests,
      "",
      "PENDING_REVIEW",
      "all",
      "high",
      "created_at",
      false
    );
    const duration = performance.now() - startTime;

    expect(filtered).toHaveLength(500);
    expect(duration).toBeLessThan(50);
  });

  it("filters and sorts 5,000 approval requests under 100 milliseconds", () => {
    const requests: ApprovalRequest[] = Array.from({ length: 5000 }).map((_, i) => ({
      request_id: `REQ-${i + 1}`,
      title: `Bulk request #${i + 1}`,
      state: "PENDING_REVIEW",
      version: (i % 5) + 1,
      risk: {
        category: "destructive",
        level: "critical",
        score: 0.95,
        title: "Critical Mutation",
        explanation: "Destructive risk",
        evidence: [],
        requires_mandatory_review: true,
      },
      operations: [],
      created_at: new Date(Date.now() - i * 10000).toISOString(),
      updated_at: new Date().toISOString(),
      decision_history: [],
      source_references: [],
    }));

    const startTime = performance.now();
    const filtered = filterAndSortApprovalRequests(
      requests,
      "Bulk request",
      "PENDING_REVIEW",
      "destructive",
      "critical",
      "version",
      true
    );
    const duration = performance.now() - startTime;

    expect(filtered).toHaveLength(5000);
    expect(duration).toBeLessThan(100);
  });
});
