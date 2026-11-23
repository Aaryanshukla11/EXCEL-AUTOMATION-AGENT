/**
 * Milestone F4: Human-in-the-Loop (HITL) Approval & Risk Governance Contracts.
 * Strictly defines approval state machine, risk assessment, proposed operations,
 * human decisions, and audit trail events.
 *
 * NOTE: The browser is not a trusted authorization authority.
 * Approval decisions recorded here represent frontend workflow demonstrations.
 */

export type ApprovalState =
  "DRAFT" | "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "NEEDS_REVISION" | "EXPIRED" | "CANCELLED";

export type OperationRiskCategory =
  | "read_only"
  | "non_destructive"
  | "ambiguous_mapping"
  | "overwrite_replacement"
  | "destructive"
  | "structural_change"
  | "unresolved_unsupported";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskAssessment {
  readonly category: OperationRiskCategory;
  readonly level: RiskLevel;
  readonly score: number; // 0.0 to 1.0 (higher = riskier)
  readonly title: string;
  readonly explanation: string;
  readonly evidence: readonly string[];
  readonly requires_mandatory_review: boolean;
}

export interface ProposedOperationSummary {
  readonly op_id: number | string;
  readonly op_type: string;
  readonly sheet_name: string;
  readonly target_range: string;
  readonly description: string;
  readonly before_value?: string | null;
  readonly after_value?: string | null;
  readonly affected_rows_count?: number;
  readonly payload?: Record<string, unknown>;
}

export interface ApprovalDecision {
  readonly decision: "APPROVED" | "REJECTED" | "NEEDS_REVISION";
  readonly decided_at: string; // ISO 8601
  readonly reviewer_identity: string; // placeholder e.g. "Operator (Frontend Simulated)"
  readonly rationale?: string | null;
  readonly version_decided: number;
}

export type ApprovalAuditEventType =
  | "REQUEST_CREATED"
  | "SUBMITTED_FOR_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "REVISION_REQUESTED"
  | "CANCELLED"
  | "EXPIRED";

export interface ApprovalAuditEvent {
  readonly event_id: string;
  readonly event_type: ApprovalAuditEventType;
  readonly timestamp: string; // ISO 8601
  readonly actor: string;
  readonly details: string;
  readonly version: number;
}

export interface ApprovalRequest {
  readonly request_id: string;
  readonly title: string;
  readonly state: ApprovalState;
  readonly version: number;
  readonly risk: RiskAssessment;
  readonly operations: readonly ProposedOperationSummary[];
  readonly created_at: string; // ISO 8601
  readonly updated_at: string; // ISO 8601
  readonly decision?: ApprovalDecision | null;
  readonly decision_history: readonly ApprovalAuditEvent[];
  readonly source_references: readonly string[];
  readonly plan_id?: string | null;
  readonly target_workbook?: string | null;
  readonly is_mock_fixture?: boolean;
}
