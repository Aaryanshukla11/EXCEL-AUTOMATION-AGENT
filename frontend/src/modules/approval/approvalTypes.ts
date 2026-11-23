import type {
  ApprovalRequest,
  ApprovalState,
  OperationRiskCategory,
  RiskLevel,
} from "../../contracts/approval";

export * from "../../contracts/approval";

export interface ApprovalFilterState {
  search: string;
  state: ApprovalState | "all";
  riskCategory: OperationRiskCategory | "all";
  riskLevel: RiskLevel | "all";
  sortBy: "created_at" | "risk_level" | "version" | "title";
  sortAsc: boolean;
}

export interface DecisionSubmitPayload {
  decision: "APPROVED" | "REJECTED" | "NEEDS_REVISION";
  reviewer_identity: string;
  rationale?: string;
  target_version: number;
}

export interface RevisionSubmitPayload {
  title?: string;
  operations: ApprovalRequest["operations"];
  revision_note: string;
  author: string;
}
