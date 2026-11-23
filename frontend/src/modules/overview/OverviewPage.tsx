import { useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Database,
  FileSpreadsheet,
  Layers,
  ShieldAlert,
  Sliders,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { type ClientConfig } from "../../config/clientConfig";
import { getTerminology } from "../../config/theme";

interface OverviewPageProps {
  config: ClientConfig;
}

export function OverviewPage({ config }: OverviewPageProps) {
  const navigate = useNavigate();

  const workbookTerm = getTerminology(config, "workbook");
  const defectTerm = getTerminology(config, "defect");
  const approvalTerm = getTerminology(config, "approval");
  const walTerm = getTerminology(config, "wal");

  return (
    <div className="space-y-6">
      {/* Platform Status Banner */}
      <div className="flex flex-col space-y-2 md:flex-row md:items-center md:justify-between md:space-y-0">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {config.branding.appTitle}
          </h1>
          <p className="text-sm text-muted-foreground">
            Enterprise Spreadsheet Ingestion, Quality Audit & Deterministic Execution Shell
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant="success">F0–F4 Accepted</Badge>
          <Badge variant="default">F5 Active</Badge>
          <Badge variant="outline">Org: {config.branding.organizationName}</Badge>
        </div>
      </div>

      {/* Scope Confirmation Notice */}
      <Alert variant="info">
        <AlertTitle>Milestone F1 Shell Active</AlertTitle>
        <AlertDescription>
          Dynamic configuration engine, responsive application shell, and centralized route
          management are active. Feature modules (Staging, Grid Viewer, Quality Audit, Approval
          Console, WAL Execution Monitor, Audit Ledger) are active and integrated.
        </AlertDescription>
      </Alert>

      {/* Quick Launch Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{workbookTerm} Staging</CardTitle>
            <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground mb-3">
              Ingest `.xlsx`, `.xlsm`, `.xlsb` files with client SHA-256 preflight checks.
            </div>
            <div className="flex items-center justify-between">
              <Badge variant="outline">F2 Milestone</Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/staging")}
                className="h-7 px-2 text-xs"
              >
                Inspect <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{defectTerm} Audit</CardTitle>
            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground mb-3">
              Surfaces the 5 defect categories: `#REF!`, formula cycles, and jagged rows.
            </div>
            <div className="flex items-center justify-between">
              <Badge variant="outline">F3 Milestone</Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/quality-audit")}
                className="h-7 px-2 text-xs"
              >
                Inspect <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{approvalTerm} Console</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground mb-3">
              Mandatory Human-in-the-Loop gates before physical workbook mutation.
            </div>
            <div className="flex items-center justify-between">
              <Badge variant="outline">F3 Milestone</Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/approval-console")}
                className="h-7 px-2 text-xs"
              >
                Inspect <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="hover:border-primary/50 transition-colors">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{walTerm} Monitor</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground mb-3">
              Real-time 6-phase WAL execution sequence with atomic rollback trigger.
            </div>
            <div className="flex items-center justify-between">
              <Badge variant="outline">F5 Milestone</Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/execution-monitor")}
                className="h-7 px-2 text-xs"
              >
                Inspect <ArrowRight className="ml-1 h-3 w-3" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Telemetry & Configuration Status */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Database className="h-5 w-5 text-primary" />
              <span>Process Quota & Telemetry Baseline</span>
            </CardTitle>
            <CardDescription>
              Hard resource constraints per Release 1.0 Architecture Specification
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-muted-foreground">Resident Memory Soft Ceiling:</span>
              <span className="font-mono font-medium">235 MiB (Spill Trigger)</span>
            </div>
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-muted-foreground">Hard Memory Ceiling:</span>
              <span className="font-mono font-medium">250 MiB (Process Abort)</span>
            </div>
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-muted-foreground">Cell Grid Hard Cap:</span>
              <span className="font-mono font-medium">10,000 Cells (Sample Limit)</span>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Deterministic Core CI Baseline:</span>
              <span className="font-mono font-medium text-success">
                422 Verified Offline Tests (362 Py + 60 Rs)
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center space-x-2">
              <Sliders className="h-5 w-5 text-primary" />
              <span>Active Client Configuration</span>
            </CardTitle>
            <CardDescription>
              Runtime settings loaded from Client Configuration Engine
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-muted-foreground">Config Version:</span>
              <Badge variant="outline">{config.configVersion}</Badge>
            </div>
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-muted-foreground">Theme Scheme:</span>
              <span className="capitalize font-medium">{config.theme.colorScheme}</span>
            </div>
            <div className="flex justify-between items-center text-sm border-b pb-2">
              <span className="text-muted-foreground">Primary Color:</span>
              <div className="flex items-center space-x-2">
                <span
                  className="h-4 w-4 rounded-full border inline-block"
                  style={{
                    backgroundColor: `hsl(${config.theme.primaryHue}, ${config.theme.primarySaturation}%, ${config.theme.primaryLightness}%)`,
                  }}
                />
                <span className="font-mono text-xs">
                  HSL({config.theme.primaryHue}, {config.theme.primarySaturation}%,{" "}
                  {config.theme.primaryLightness}%)
                </span>
              </div>
            </div>
            <div className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Layout Density:</span>
              <span className="capitalize font-medium">{config.layout.density}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature Slices Roadmap */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Layers className="h-5 w-5 text-primary" />
            <span>Frontend Delivery Roadmap Alignment</span>
          </CardTitle>
          <CardDescription>
            Release 1.0 implementation phases across 12-week schedule
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-xs">
            <div className="rounded border p-3 bg-muted/20">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-foreground">Phase F0</span>
                <Badge variant="success">Completed</Badge>
              </div>
              <p className="text-muted-foreground">
                Foundation Tooling, Headless Design System & Contract Mock Harness
              </p>
            </div>

            <div className="rounded border p-3 border-primary/50 bg-primary/5">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-foreground">Phase F1</span>
                <Badge variant="default">Current</Badge>
              </div>
              <p className="text-muted-foreground">
                Application Shell, Navigation & Client Configuration Engine
              </p>
            </div>

            <div className="rounded border p-3 bg-muted/20">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-foreground">Phase F2</span>
                <Badge variant="outline">Next</Badge>
              </div>
              <p className="text-muted-foreground">
                Workbook Management & Spatial Discovery Grid Viewer (100k Cells)
              </p>
            </div>

            <div className="rounded border p-3 bg-muted/20">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-foreground">Phase F3</span>
                <Badge variant="outline">Pending</Badge>
              </div>
              <p className="text-muted-foreground">
                5 Defect Categories Quality Audit & HITL Approval Console
              </p>
            </div>

            <div className="rounded border p-3 bg-muted/20">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-foreground">Phase F4</span>
                <Badge variant="outline">Pending</Badge>
              </div>
              <p className="text-muted-foreground">
                Field Mapping Matrix, Formula Dependency DAG & Cryptographic Proofs
              </p>
            </div>

            <div className="rounded border p-3 bg-muted/20">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-foreground">Phase F5</span>
                <Badge variant="outline">Pending</Badge>
              </div>
              <p className="text-muted-foreground">
                Execution Monitor, WAL Durability & Live Backend Service Packaging
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
