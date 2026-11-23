import { CheckCircle2, ShieldAlert } from "lucide-react";
import type { PostFlightVerification } from "../../contracts/execution";
import { Badge } from "../../components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/Card";

interface PostFlightVerificationCardProps {
  verification: PostFlightVerification | null | undefined;
}

export function PostFlightVerificationCard({ verification }: PostFlightVerificationCardProps) {
  if (!verification) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-xs uppercase tracking-wider text-muted-foreground">
            Post-Flight Verification
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Verification telemetry will be generated upon completion of the 6-phase WAL sequence.
          </p>
        </CardContent>
      </Card>
    );
  }

  const isVerified = verification.integrity_status === "verified";

  return (
    <Card data-testid="post-flight-verification-card">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-xs uppercase tracking-wider text-foreground font-semibold">
          Post-Flight Verification & Telemetry
        </CardTitle>
        <Badge variant={isVerified ? "success" : "destructive"}>
          {isVerified ? (
            <span className="flex items-center space-x-1">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              HASH VERIFIED
            </span>
          ) : (
            <span className="flex items-center space-x-1">
              <ShieldAlert className="h-3 w-3 mr-1" />
              INTEGRITY MISMATCH
            </span>
          )}
        </Badge>
      </CardHeader>

      <CardContent className="space-y-3 text-xs">
        <div className="grid grid-cols-2 gap-2 text-center">
          <div className="rounded border border-border p-2 bg-muted/20">
            <span className="text-[10px] text-muted-foreground uppercase block">Cells Written</span>
            <span className="text-base font-bold text-foreground font-mono">
              {verification.cells_written.toLocaleString()}
            </span>
          </div>
          <div className="rounded border border-border p-2 bg-muted/20">
            <span className="text-[10px] text-muted-foreground uppercase block">
              Sheets Affected
            </span>
            <span className="text-base font-bold text-foreground font-mono">
              {verification.sheets_affected}
            </span>
          </div>
        </div>

        <div className="space-y-1.5 font-mono text-[11px] bg-muted/30 p-2.5 rounded border border-border">
          <div className="text-muted-foreground truncate">
            <span className="font-semibold text-foreground">Pre-Run Hash: </span>
            {verification.pre_run_sha256}
          </div>
          <div className="text-muted-foreground truncate">
            <span className="font-semibold text-foreground">Post-Run Hash: </span>
            {verification.post_run_sha256}
          </div>
          <div className="text-muted-foreground truncate">
            <span className="font-semibold text-foreground">Snapshot: </span>
            {verification.backup_path}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
