import { Activity, CheckCircle2, RotateCcw, PlayCircle } from "lucide-react";
import type { ExecutionJob } from "./executionTypes";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/Card";

interface ExecutionKPIOverviewProps {
  jobs: readonly ExecutionJob[];
}

export function ExecutionKPIOverview({ jobs }: ExecutionKPIOverviewProps) {
  const totalCount = jobs.length;
  const committedCount = jobs.filter((j) => j.state === "COMMITTED").length;
  const rolledBackCount = jobs.filter((j) => j.state === "ROLLED_BACK").length;
  const activeCount = jobs.filter((j) => j.state === "EXECUTING" || j.state === "PREPARING").length;

  return (
    <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-xs font-medium text-muted-foreground">
            Total Pipelines
          </CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-foreground font-mono">{totalCount}</div>
          <p className="text-[11px] text-muted-foreground">WAL orchestration jobs</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-xs font-medium text-muted-foreground">
            Active Pipelines
          </CardTitle>
          <PlayCircle className="h-4 w-4 text-primary" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-primary font-mono">{activeCount}</div>
          <p className="text-[11px] text-muted-foreground">Executing atomic steps</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-xs font-medium text-muted-foreground">
            Committed (WAL)
          </CardTitle>
          <CheckCircle2 className="h-4 w-4 text-success" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-success font-mono">{committedCount}</div>
          <p className="text-[11px] text-muted-foreground">Hardware flushed & verified</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-xs font-medium text-muted-foreground">Rolled Back</CardTitle>
          <RotateCcw className="h-4 w-4 text-warning" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold text-warning font-mono">{rolledBackCount}</div>
          <p className="text-[11px] text-muted-foreground">Restored from .bak snapshot</p>
        </CardContent>
      </Card>
    </div>
  );
}
