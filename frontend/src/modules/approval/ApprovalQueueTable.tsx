import * as React from "react";
import { ChevronRight } from "lucide-react";
import type { ApprovalRequest } from "./approvalTypes";
import { Badge } from "../../components/ui/Badge";
import { cn } from "../../lib/utils";

interface ApprovalQueueTableProps {
  requests: readonly ApprovalRequest[];
  selectedRequestId: string | null;
  onSelectRequest: (requestId: string) => void;
}

export function ApprovalQueueTable({
  requests,
  selectedRequestId,
  onSelectRequest,
}: ApprovalQueueTableProps) {
  if (requests.length === 0) {
    return (
      <div className="rounded-lg border border-border p-12 text-center text-muted-foreground text-xs bg-card">
        No approval proposals match the current filter criteria.
      </div>
    );
  }

  // Keyboard navigation across table rows
  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === "ArrowDown" && index < requests.length - 1) {
      e.preventDefault();
      onSelectRequest(requests[index + 1]!.request_id);
    } else if (e.key === "ArrowUp" && index > 0) {
      e.preventDefault();
      onSelectRequest(requests[index - 1]!.request_id);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectRequest(requests[index]!.request_id);
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="grid grid-cols-12 bg-muted/50 px-4 py-2.5 text-xs font-semibold text-muted-foreground border-b border-border">
        <div className="col-span-3">Request ID & Version</div>
        <div className="col-span-4">Operation Proposal</div>
        <div className="col-span-3">Risk Assessment</div>
        <div className="col-span-2 text-right">Status</div>
      </div>

      <div className="divide-y divide-border">
        {requests.map((req, idx) => {
          const isSelected = selectedRequestId === req.request_id;

          const riskBadgeVariant =
            req.risk.level === "critical"
              ? "destructive"
              : req.risk.level === "high"
                ? "warning"
                : req.risk.level === "medium"
                  ? "secondary"
                  : "outline";

          const stateBadgeVariant =
            req.state === "APPROVED"
              ? "success"
              : req.state === "PENDING_REVIEW"
                ? "warning"
                : req.state === "REJECTED"
                  ? "destructive"
                  : "secondary";

          return (
            <div
              key={req.request_id}
              tabIndex={0}
              role="button"
              aria-selected={isSelected}
              data-testid={`approval-row-${req.request_id}`}
              onClick={() => onSelectRequest(req.request_id)}
              onKeyDown={(e) => handleKeyDown(e, idx)}
              className={cn(
                "grid grid-cols-12 items-center px-4 py-3 text-xs transition-colors hover:bg-muted/40 cursor-pointer focus:outline-none focus:bg-muted/50",
                isSelected && "bg-muted/60 font-medium border-l-4 border-l-primary"
              )}
            >
              {/* ID & Version */}
              <div className="col-span-3 space-y-1">
                <div className="flex items-center space-x-1.5">
                  <span className="font-mono font-semibold text-foreground">{req.request_id}</span>
                  <Badge variant="outline" className="font-mono text-[9px] py-0">
                    v{req.version}
                  </Badge>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  {new Date(req.created_at).toLocaleDateString()}
                </div>
              </div>

              {/* Proposal Title & Ops count */}
              <div className="col-span-4 space-y-0.5 pr-2">
                <div className="text-foreground truncate font-medium">{req.title}</div>
                <div className="text-[10px] text-muted-foreground flex items-center space-x-1">
                  <span>
                    {req.operations.length}{" "}
                    {req.operations.length === 1 ? "operation" : "operations"}
                  </span>
                  <span>•</span>
                  <span>{req.operations[0]?.sheet_name || "Sheet"}</span>
                </div>
              </div>

              {/* Risk */}
              <div className="col-span-3 space-y-0.5">
                <Badge variant={riskBadgeVariant} className="text-[10px] uppercase font-bold">
                  {req.risk.level}
                </Badge>
                <div className="text-[11px] text-muted-foreground truncate font-normal">
                  {req.risk.title}
                </div>
              </div>

              {/* Status & Action */}
              <div className="col-span-2 flex items-center justify-end space-x-2">
                <Badge variant={stateBadgeVariant} className="text-[10px] uppercase font-semibold">
                  {req.state}
                </Badge>
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
