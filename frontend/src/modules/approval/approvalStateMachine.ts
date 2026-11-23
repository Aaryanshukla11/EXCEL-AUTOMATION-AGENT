import type {
  ApprovalAuditEvent,
  ApprovalDecision,
  ApprovalRequest,
  ApprovalState,
  OperationRiskCategory,
  ProposedOperationSummary,
  RiskAssessment,
  RiskLevel,
} from "./approvalTypes";

/**
 * Valid state transitions for the Human-in-the-Loop approval state machine.
 */
export const VALID_TRANSITIONS: Record<ApprovalState, readonly ApprovalState[]> = {
  DRAFT: ["PENDING_REVIEW", "CANCELLED"],
  PENDING_REVIEW: ["APPROVED", "REJECTED", "NEEDS_REVISION", "EXPIRED", "CANCELLED"],
  APPROVED: [], // Terminal for this request version
  REJECTED: [], // Terminal for this request version
  NEEDS_REVISION: ["DRAFT", "PENDING_REVIEW", "CANCELLED"], // Allows revised version submission
  EXPIRED: [], // Terminal
  CANCELLED: [], // Terminal
};

export function canTransition(fromState: ApprovalState, toState: ApprovalState): boolean {
  const allowed = VALID_TRANSITIONS[fromState];
  return !!allowed && allowed.includes(toState);
}

/**
 * Checks whether an incoming decision is targeting a stale version of the request.
 */
export function isDecisionStale(request: ApprovalRequest, targetVersion: number): boolean {
  return request.version !== targetVersion;
}

/**
 * Assesses operational risk generically and evidence-based.
 * Defaults unknown/unsupported operations to conservative critical review-required state.
 */
export function assessOperationRisk(operation: Partial<ProposedOperationSummary>): RiskAssessment {
  const opType = (operation.op_type || "").toUpperCase();

  switch (opType) {
    case "READ_ONLY":
    case "INSPECT":
    case "PREVIEW":
      return {
        category: "read_only",
        level: "low",
        score: 0.1,
        title: "Read-Only Inspection",
        explanation: "Operation performs passive inspection or sampling with no side-effects.",
        evidence: ["No cell mutation", "No table alteration"],
        requires_mandatory_review: false,
      };

    case "APPEND_ROWS":
    case "INSERT_ROW":
    case "STAGE_COPY":
      return {
        category: "non_destructive",
        level: "medium",
        score: 0.4,
        title: "Non-Destructive Transformation",
        explanation: "Appends new rows or records without modifying existing pre-populated cells.",
        evidence: [
          `Target: ${operation.sheet_name || "Unknown Sheet"} [${operation.target_range || "Range"}]`,
          "Preserves existing data rows",
        ],
        requires_mandatory_review: true,
      };

    case "AMBIGUOUS_MAPPING":
    case "FUZZY_MATCH":
      return {
        category: "ambiguous_mapping",
        level: "medium",
        score: 0.6,
        title: "Ambiguous Schema Association",
        explanation:
          "Proposed transformation relies on heuristic or fuzzy candidate matches below confidence threshold.",
        evidence: ["Confidence score below 0.85", "Manual human alignment recommended"],
        requires_mandatory_review: true,
      };

    case "UPDATE_CELL":
    case "OVERWRITE_CELL":
    case "POPULATED_OVERWRITE":
      return {
        category: "overwrite_replacement",
        level: "high",
        score: 0.75,
        title: "Populated Cell Overwrite",
        explanation: "Replaces existing values with newly calculated or transformed content.",
        evidence: [
          `Target: ${operation.sheet_name || "Sheet"} ${operation.target_range || "Cell"}`,
          "Prior value will be replaced",
        ],
        requires_mandatory_review: true,
      };

    case "DROP_COLUMN":
    case "DELETE_SHEET":
    case "TRUNCATE_TABLE":
    case "DESTRUCTIVE":
      return {
        category: "destructive",
        level: "critical",
        score: 0.95,
        title: "Destructive Mutation",
        explanation: "Permanently removes structural columns, tables, or worksheets.",
        evidence: [
          `Irreversible data loss risk on ${operation.sheet_name || "sheet"}`,
          "Strict administrative sign-off required",
        ],
        requires_mandatory_review: true,
      };

    case "EXTEND_TABLE":
    case "PROPAGATE_FORMULA":
    case "RENAME_SHEET":
    case "STRUCTURAL_CHANGE":
      return {
        category: "structural_change",
        level: "high",
        score: 0.7,
        title: "Structural Workbook Modification",
        explanation: "Modifies table boundaries, formula calculation ranges, or sheet topologies.",
        evidence: ["Formula dependency DAG recalculation required", "Table metadata will shift"],
        requires_mandatory_review: true,
      };

    default:
      // Conservative fallback for unknown operations
      return {
        category: "unresolved_unsupported",
        level: "critical",
        score: 1.0,
        title: "Unresolved / Unsupported Operation",
        explanation:
          "Unrecognized mutation type. Conservative security policy requires mandatory human intervention.",
        evidence: [
          `Unrecognized op_type: '${operation.op_type || "UNKNOWN"}'`,
          "Defaulting to critical review-required state",
        ],
        requires_mandatory_review: true,
      };
  }
}

/**
 * Transitions request to PENDING_REVIEW from DRAFT.
 */
export function submitForReview(
  request: ApprovalRequest,
  actor = "System Orchestrator"
): ApprovalRequest {
  if (!canTransition(request.state, "PENDING_REVIEW")) {
    throw new Error(`Cannot submit request in state '${request.state}' for review.`);
  }

  const now = new Date().toISOString();
  const event: ApprovalAuditEvent = {
    event_id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    event_type: "SUBMITTED_FOR_REVIEW",
    timestamp: now,
    actor,
    details: `Request submitted for human review (Version ${request.version}).`,
    version: request.version,
  };

  return {
    ...request,
    state: "PENDING_REVIEW",
    updated_at: now,
    decision_history: [...request.decision_history, event],
  };
}

/**
 * Records an approval decision.
 */
export function approveRequest(
  request: ApprovalRequest,
  payload: {
    reviewer_identity: string;
    rationale?: string;
    target_version: number;
  }
): ApprovalRequest {
  if (isDecisionStale(request, payload.target_version)) {
    throw new Error(
      `Stale decision rejected: Target version ${payload.target_version} does not match current version ${request.version}.`
    );
  }

  if (!canTransition(request.state, "APPROVED")) {
    throw new Error(`Cannot approve request in state '${request.state}'.`);
  }

  const now = new Date().toISOString();
  const decision: ApprovalDecision = {
    decision: "APPROVED",
    decided_at: now,
    reviewer_identity: payload.reviewer_identity.trim() || "Operator (Frontend Simulated)",
    rationale: payload.rationale?.trim() || "Approved by operator.",
    version_decided: request.version,
  };

  const event: ApprovalAuditEvent = {
    event_id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    event_type: "APPROVED",
    timestamp: now,
    actor: decision.reviewer_identity,
    details: `Operation approved for version ${request.version}. Note: Approval does not trigger execution.`,
    version: request.version,
  };

  return {
    ...request,
    state: "APPROVED",
    decision,
    updated_at: now,
    decision_history: [...request.decision_history, event],
  };
}

/**
 * Records a rejection decision. Mandatory rationale required.
 */
export function rejectRequest(
  request: ApprovalRequest,
  payload: {
    reviewer_identity: string;
    rationale: string;
    target_version: number;
  }
): ApprovalRequest {
  if (isDecisionStale(request, payload.target_version)) {
    throw new Error(
      `Stale decision rejected: Target version ${payload.target_version} does not match current version ${request.version}.`
    );
  }

  if (!payload.rationale || payload.rationale.trim().length < 5) {
    throw new Error("Mandatory rejection rationale of at least 5 characters is required.");
  }

  if (!canTransition(request.state, "REJECTED")) {
    throw new Error(`Cannot reject request in state '${request.state}'.`);
  }

  const now = new Date().toISOString();
  const decision: ApprovalDecision = {
    decision: "REJECTED",
    decided_at: now,
    reviewer_identity: payload.reviewer_identity.trim() || "Operator (Frontend Simulated)",
    rationale: payload.rationale.trim(),
    version_decided: request.version,
  };

  const event: ApprovalAuditEvent = {
    event_id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    event_type: "REJECTED",
    timestamp: now,
    actor: decision.reviewer_identity,
    details: `Request rejected: ${decision.rationale}`,
    version: request.version,
  };

  return {
    ...request,
    state: "REJECTED",
    decision,
    updated_at: now,
    decision_history: [...request.decision_history, event],
  };
}

/**
 * Records a revision requested decision. Mandatory rationale required.
 */
export function requestRevision(
  request: ApprovalRequest,
  payload: {
    reviewer_identity: string;
    rationale: string;
    target_version: number;
  }
): ApprovalRequest {
  if (isDecisionStale(request, payload.target_version)) {
    throw new Error(
      `Stale decision rejected: Target version ${payload.target_version} does not match current version ${request.version}.`
    );
  }

  if (!payload.rationale || payload.rationale.trim().length < 5) {
    throw new Error("Mandatory revision rationale of at least 5 characters is required.");
  }

  if (!canTransition(request.state, "NEEDS_REVISION")) {
    throw new Error(`Cannot request revision for request in state '${request.state}'.`);
  }

  const now = new Date().toISOString();
  const decision: ApprovalDecision = {
    decision: "NEEDS_REVISION",
    decided_at: now,
    reviewer_identity: payload.reviewer_identity.trim() || "Operator (Frontend Simulated)",
    rationale: payload.rationale.trim(),
    version_decided: request.version,
  };

  const event: ApprovalAuditEvent = {
    event_id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    event_type: "REVISION_REQUESTED",
    timestamp: now,
    actor: decision.reviewer_identity,
    details: `Revision requested: ${decision.rationale}`,
    version: request.version,
  };

  return {
    ...request,
    state: "NEEDS_REVISION",
    decision,
    updated_at: now,
    decision_history: [...request.decision_history, event],
  };
}

/**
 * Submits a revised version of the request, incrementing the version and clearing stale decision.
 */
export function reviseRequest(
  request: ApprovalRequest,
  payload: {
    operations: readonly ProposedOperationSummary[];
    author: string;
    revision_note?: string;
  }
): ApprovalRequest {
  if (request.state !== "NEEDS_REVISION" && request.state !== "DRAFT") {
    throw new Error(`Cannot revise request in state '${request.state}'.`);
  }

  const newVersion = request.version + 1;
  const now = new Date().toISOString();

  // Re-assess composite risk
  const highestRisk = payload.operations.reduce<RiskAssessment>(
    (acc, op) => {
      const opRisk = assessOperationRisk(op);
      return opRisk.score > acc.score ? opRisk : acc;
    },
    {
      category: "read_only",
      level: "low",
      score: 0.0,
      title: "Base Risk",
      explanation: "No operations",
      evidence: [],
      requires_mandatory_review: false,
    }
  );

  const event: ApprovalAuditEvent = {
    event_id: `evt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    event_type: "SUBMITTED_FOR_REVIEW",
    timestamp: now,
    actor: payload.author,
    details: `Revised to Version ${newVersion}: ${payload.revision_note || "Updated proposed operations."}`,
    version: newVersion,
  };

  return {
    ...request,
    version: newVersion,
    state: "PENDING_REVIEW",
    risk: highestRisk,
    operations: payload.operations,
    decision: null, // Clear stale decision for new version
    updated_at: now,
    decision_history: [...request.decision_history, event],
  };
}

/**
 * Filter and sort approval requests in memory.
 */
export function filterAndSortApprovalRequests(
  requests: readonly ApprovalRequest[],
  search: string,
  stateFilter: ApprovalState | "all",
  riskCategoryFilter: OperationRiskCategory | "all",
  riskLevelFilter: RiskLevel | "all",
  sortBy: "created_at" | "risk_level" | "version" | "title" = "created_at",
  sortAsc = false
): ApprovalRequest[] {
  const query = search.trim().toLowerCase();
  const hasQuery = query.length > 0;

  const RISK_WEIGHTS: Record<RiskLevel, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
  };

  return requests
    .filter((req) => {
      if (stateFilter !== "all" && req.state !== stateFilter) return false;
      if (riskCategoryFilter !== "all" && req.risk.category !== riskCategoryFilter) return false;
      if (riskLevelFilter !== "all" && req.risk.level !== riskLevelFilter) return false;

      if (!hasQuery) return true;

      return (
        req.request_id.toLowerCase().includes(query) ||
        req.title.toLowerCase().includes(query) ||
        req.risk.title.toLowerCase().includes(query) ||
        req.operations.some((op) => op.sheet_name.toLowerCase().includes(query))
      );
    })
    .sort((a, b) => {
      let comp = 0;
      if (sortBy === "created_at") {
        comp = a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
      } else if (sortBy === "risk_level") {
        const wA = RISK_WEIGHTS[a.risk.level] || 0;
        const wB = RISK_WEIGHTS[b.risk.level] || 0;
        comp = wA - wB;
      } else if (sortBy === "version") {
        comp = a.version - b.version;
      } else if (sortBy === "title") {
        comp = a.title < b.title ? -1 : a.title > b.title ? 1 : 0;
      }

      return sortAsc ? comp : -comp;
    });
}
