import * as React from "react";
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  History,
  ShieldAlert,
  X,
} from "lucide-react";
import type { ApprovalRequest, DecisionSubmitPayload } from "./approvalTypes";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";
import { ProposedOperationsDiffCard } from "./ProposedOperationsDiffCard";
import { DecisionActionDialog } from "./DecisionActionDialog";

interface ApprovalDetailPanelProps {
  request: ApprovalRequest | null;
  onClose: () => void;
  onSubmitDecision: (payload: DecisionSubmitPayload) => Promise<void>;
}

export function ApprovalDetailPanel({
  request,
  onClose,
  onSubmitDecision,
}: ApprovalDetailPanelProps) {
  const [activeDialogAction, setActiveDialogAction] = React.useState<
    "APPROVED" | "REJECTED" | "NEEDS_REVISION" | null
  >(null);

  if (!request) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle className="text-sm">Approval Request Inspector</CardTitle>
          <CardDescription>
            Select any proposal in the queue to inspect risk classifications, before/after operation
            previews, and human review actions.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const isPending = request.state === "PENDING_REVIEW";

  const riskBadgeVariant =
    request.risk.level === "critical"
      ? "destructive"
      : request.risk.level === "high"
        ? "warning"
        : request.risk.level === "medium"
          ? "secondary"
          : "outline";

  const stateBadgeVariant =
    request.state === "APPROVED"
      ? "success"
      : request.state === "PENDING_REVIEW"
        ? "warning"
        : request.state === "REJECTED"
          ? "destructive"
          : "secondary";

  return (
    <>
      <Card className="h-full overflow-y-auto" data-testid="approval-detail-panel">
        <CardHeader className="flex flex-row items-start justify-between pb-3">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="font-mono text-xs">
                {request.request_id}
              </Badge>
              <Badge variant={stateBadgeVariant} className="text-xs uppercase font-semibold">
                {request.state}
              </Badge>
              <Badge variant="outline" className="font-mono text-[10px]">
                v{request.version}
              </Badge>
              {request.is_mock_fixture && (
                <Badge variant="warning" className="text-[10px]">
                  [DEV FIXTURE]
                </Badge>
              )}
            </div>
            <CardTitle className="text-base font-semibold text-foreground pt-1">
              {request.title}
            </CardTitle>
            <CardDescription className="text-xs">
              Created: {new Date(request.created_at).toLocaleString()}
              {request.target_workbook ? ` • Target: ${request.target_workbook}` : ""}
            </CardDescription>
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close detail panel"
            className="h-7 w-7"
          >
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>

        <CardContent className="space-y-5 text-xs">
          {/* Action Toolbar for Pending Requests */}
          {isPending ? (
            <div className="rounded-lg border border-warning/40 bg-warning/5 p-3 space-y-2">
              <div className="flex items-center space-x-2 text-warning font-semibold">
                <Clock className="h-4 w-4" />
                <span>Human Review Required Prior to Authorization</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Review the proposed operations and risk evidence below. An approval decision will
                record human authorization, but will not trigger execution.
              </p>
              <div className="flex items-center space-x-2 pt-1">
                <Button
                  size="sm"
                  onClick={() => setActiveDialogAction("APPROVED")}
                  className="h-7 text-xs bg-success hover:bg-success/90 text-white"
                >
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                  Approve Proposal
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveDialogAction("NEEDS_REVISION")}
                  className="h-7 text-xs"
                >
                  <AlertTriangle className="h-3.5 w-3.5 mr-1 text-warning" />
                  Request Revision
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setActiveDialogAction("REJECTED")}
                  className="h-7 text-xs"
                >
                  <AlertOctagon className="h-3.5 w-3.5 mr-1" />
                  Reject Proposal
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-md border p-3 bg-muted/30 space-y-1">
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-foreground">Decision Recorded:</span>
                <Badge variant={stateBadgeVariant} className="text-[11px]">
                  {request.decision?.decision || request.state}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                By: {request.decision?.reviewer_identity || "System"} • Decided:{" "}
                {request.decision?.decided_at
                  ? new Date(request.decision.decided_at).toLocaleString()
                  : "N/A"}
              </p>
              {request.decision?.rationale && (
                <p className="text-[11px] text-foreground font-mono bg-background p-2 rounded border border-border mt-1">
                  Rationale: &quot;{request.decision.rationale}&quot;
                </p>
              )}
            </div>
          )}

          {/* Risk Assessment Card */}
          <div className="rounded-lg border border-border p-3 bg-card space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <ShieldAlert className="h-4 w-4 text-primary" />
                <span className="font-semibold text-foreground text-xs uppercase tracking-wider">
                  Risk Classification
                </span>
              </div>
              <Badge variant={riskBadgeVariant} className="text-[11px] uppercase font-bold">
                {request.risk.level} Risk
              </Badge>
            </div>

            <div className="text-foreground font-medium text-xs">{request.risk.title}</div>
            <p className="text-muted-foreground text-[11px]">{request.risk.explanation}</p>

            {request.risk.evidence.length > 0 && (
              <div className="space-y-1 pt-1 border-t border-border">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                  Risk Evidence:
                </span>
                <ul className="list-disc list-inside space-y-0.5 text-[11px] text-muted-foreground">
                  {request.risk.evidence.map((ev, i) => (
                    <li key={i}>{ev}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Proposed Operations List */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground text-xs uppercase tracking-wider">
                Proposed Operations ({request.operations.length})
              </span>
              <span className="text-[10px] text-muted-foreground">
                Target: {request.operations[0]?.sheet_name || "Workbook"}
              </span>
            </div>

            <div className="space-y-2">
              {request.operations.map((op, idx) => (
                <ProposedOperationsDiffCard key={op.op_id} operation={op} index={idx} />
              ))}
            </div>
          </div>

          {/* Append-Only Decision History */}
          <div className="space-y-2 pt-2 border-t border-border">
            <div className="flex items-center space-x-2">
              <History className="h-4 w-4 text-muted-foreground" />
              <span className="font-semibold text-foreground text-xs uppercase tracking-wider">
                Decision Audit Trail
              </span>
            </div>

            <div className="space-y-2 pl-2 border-l-2 border-muted">
              {request.decision_history.map((evt) => (
                <div key={evt.event_id} className="text-[11px] space-y-0.5">
                  <div className="flex items-center space-x-1.5">
                    <span className="font-semibold text-foreground">{evt.event_type}</span>
                    <span className="text-muted-foreground text-[10px]">
                      • {new Date(evt.timestamp).toLocaleTimeString()}
                    </span>
                    <Badge variant="outline" className="text-[9px] py-0">
                      v{evt.version}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground">{evt.details}</p>
                  <span className="text-[10px] text-muted-foreground block">
                    Actor: {evt.actor}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Decision Modal */}
      {activeDialogAction && (
        <DecisionActionDialog
          request={request}
          action={activeDialogAction}
          isOpen={true}
          onClose={() => setActiveDialogAction(null)}
          onSubmit={onSubmitDecision}
        />
      )}
    </>
  );
}
