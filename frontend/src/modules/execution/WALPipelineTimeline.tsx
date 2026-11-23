import {
  CheckCircle2,
  Clock,
  Database,
  FileCheck,
  HardDrive,
  RefreshCw,
  XCircle,
} from "lucide-react";
import type { ExecutionJob, ExecutionPhaseDetail, PhaseStatus } from "./executionTypes";
import { Badge } from "../../components/ui/Badge";
import { cn } from "../../lib/utils";

interface WALPipelineTimelineProps {
  job: ExecutionJob;
}

export function WALPipelineTimeline({ job }: WALPipelineTimelineProps) {
  const getPhaseIcon = (phaseNumber: number, status: PhaseStatus) => {
    if (status === "completed") {
      return <CheckCircle2 className="h-5 w-5 text-success" />;
    }
    if (status === "running") {
      return <RefreshCw className="h-5 w-5 text-primary animate-spin" />;
    }
    if (status === "failed") {
      return <XCircle className="h-5 w-5 text-destructive" />;
    }
    if (status === "rolled_back") {
      return <XCircle className="h-5 w-5 text-warning" />;
    }

    switch (phaseNumber) {
      case 1:
        return <HardDrive className="h-5 w-5 text-muted-foreground" />;
      case 2:
        return <Database className="h-5 w-5 text-muted-foreground" />;
      case 3:
        return <HardDrive className="h-5 w-5 text-muted-foreground" />;
      case 4:
        return <RefreshCw className="h-5 w-5 text-muted-foreground" />;
      case 5:
        return <HardDrive className="h-5 w-5 text-muted-foreground" />;
      case 6:
        return <FileCheck className="h-5 w-5 text-muted-foreground" />;
      default:
        return <Clock className="h-5 w-5 text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: PhaseStatus) => {
    switch (status) {
      case "completed":
        return (
          <Badge variant="success" className="text-[10px]">
            COMPLETED
          </Badge>
        );
      case "running":
        return (
          <Badge variant="default" className="text-[10px]">
            IN PROGRESS
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="destructive" className="text-[10px]">
            FAILED
          </Badge>
        );
      case "rolled_back":
        return (
          <Badge variant="warning" className="text-[10px]">
            ROLLED BACK
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-[10px]">
            PENDING
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-3" data-testid="wal-pipeline-timeline">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-foreground uppercase tracking-wider">
          6-Phase Atomic WAL Sequence
        </h3>
        <span className="text-[11px] font-mono text-muted-foreground">
          Target: {job.target_workbook}
        </span>
      </div>

      <div className="space-y-3 relative before:absolute before:inset-0 before:left-5 before:w-0.5 before:bg-border before:-z-10">
        {job.phases.map((phase: ExecutionPhaseDetail) => {
          const isCurrent = job.current_phase === phase.phase;
          return (
            <div
              key={phase.phase}
              className={cn(
                "rounded-lg border p-3 bg-card transition-all flex items-start space-x-3.5",
                isCurrent && "border-primary/60 shadow-sm",
                phase.status === "completed" && "border-success/30",
                phase.status === "failed" && "border-destructive/40 bg-destructive/5"
              )}
            >
              <div className="pt-0.5">{getPhaseIcon(phase.phase_number, phase.status)}</div>

              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-semibold text-xs text-foreground">
                      Phase {phase.phase_number}: {phase.title}
                    </span>
                    {getStatusBadge(phase.status)}
                  </div>
                  {phase.duration_ms != null && (
                    <span className="text-[10px] font-mono text-muted-foreground">
                      {phase.duration_ms} ms
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-muted-foreground">{phase.description}</p>

                {phase.error && (
                  <p className="text-[11px] text-destructive font-mono bg-destructive/10 p-1.5 rounded">
                    Error: {phase.error}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
