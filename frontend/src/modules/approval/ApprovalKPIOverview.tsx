import { AlertOctagon, CheckCircle2, Clock, ShieldAlert } from "lucide-react";
import type { ApprovalRequest } from "./approvalTypes";
import { Card, CardContent } from "../../components/ui/Card";

interface ApprovalKPIOverviewProps {
  requests: readonly ApprovalRequest[];
}

export function ApprovalKPIOverview({ requests }: ApprovalKPIOverviewProps) {
  const pendingCount = requests.filter((r) => r.state === "PENDING_REVIEW").length;
  const criticalCount = requests.filter(
    (r) => r.risk.level === "critical" || r.risk.level === "high"
  ).length;
  const approvedCount = requests.filter((r) => r.state === "APPROVED").length;
  const rejectedCount = requests.filter(
    (r) => r.state === "REJECTED" || r.state === "NEEDS_REVISION"
  ).length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Pending Human Review
            </span>
            <span className="text-2xl font-bold font-mono text-warning">{pendingCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-warning/10 flex items-center justify-center text-warning">
            <Clock className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              High / Critical Risk Items
            </span>
            <span className="text-2xl font-bold font-mono text-destructive">{criticalCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-destructive/10 flex items-center justify-center text-destructive">
            <ShieldAlert className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Approved (Simulated)
            </span>
            <span className="text-2xl font-bold font-mono text-success">{approvedCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-success/10 flex items-center justify-center text-success">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <span className="text-xs text-muted-foreground block font-medium">
              Rejected / Revision Req.
            </span>
            <span className="text-2xl font-bold font-mono text-foreground">{rejectedCount}</span>
          </div>
          <div className="h-9 w-9 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
            <AlertOctagon className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
