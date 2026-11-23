import React, { Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./ErrorBoundary";
import { NotFoundPage } from "./NotFoundPage";
import { OverviewPage } from "../modules/overview/OverviewPage";
import { WorkbookManagementPage } from "../modules/workbooks/WorkbookManagementPage";
import { SpatialViewerPage } from "../modules/spatial-discovery/SpatialViewerPage";
import { SchemaMappingPage } from "../modules/schema-mapping/SchemaMappingPage";
import { DataQualityPage } from "../modules/data-quality/DataQualityPage";
import { ApprovalConsolePage } from "../modules/approval/ApprovalConsolePage";
import { ExecutionMonitorPage } from "../modules/execution/ExecutionMonitorPage";
import { AuditLedgerPage } from "../modules/audit-ledger/AuditLedgerPage";
import { SettingsPage } from "../modules/settings/SettingsPage";
import { LoadingState } from "../components/ui/LoadingState";
import { routeRegistry } from "./routeRegistry";
import type { ClientConfig } from "../config/clientConfig";

interface AppRoutesProps {
  config: ClientConfig;
  onUpdateConfig?: (updated: ClientConfig) => void;
}

export function AppRoutes({ config, onUpdateConfig }: AppRoutesProps) {
  // Register default routes into registry once
  React.useEffect(() => {
    routeRegistry.register({
      path: "/overview",
      element: <OverviewPage config={config} />,
      title: "Overview",
      breadcrumb: "Overview",
    });

    routeRegistry.register({
      path: "/staging",
      element: <WorkbookManagementPage />,
      title: "Staging",
      breadcrumb: "Staging",
    });

    routeRegistry.register({
      path: "/spatial-viewer",
      element: <SpatialViewerPage />,
      title: "Spatial Viewer",
      breadcrumb: "Spatial Viewer",
    });

    routeRegistry.register({
      path: "/schema-studio",
      element: <SchemaMappingPage />,
      title: "Schema Studio",
      breadcrumb: "Schema Studio",
    });

    routeRegistry.register({
      path: "/quality-audit",
      element: <DataQualityPage />,
      title: "Quality Audit",
      breadcrumb: "Quality Audit",
    });

    routeRegistry.register({
      path: "/approval-console",
      element: <ApprovalConsolePage />,
      title: "Approval Console",
      breadcrumb: "Approval Console",
    });

    routeRegistry.register({
      path: "/execution-monitor",
      element: <ExecutionMonitorPage />,
      title: "Execution Monitor",
      breadcrumb: "Execution Monitor",
    });

    routeRegistry.register({
      path: "/audit-ledger",
      element: <AuditLedgerPage />,
      title: "Audit Ledger",
      breadcrumb: "Audit Ledger",
    });

    routeRegistry.register({
      path: "/settings",
      element: <SettingsPage config={config} onUpdateConfig={onUpdateConfig || (() => {})} />,
      title: "Settings",
      breadcrumb: "Settings",
    });
  }, [config, onUpdateConfig]);

  return (
    <ErrorBoundary>
      <Suspense fallback={<LoadingState message="Loading module view..." />}>
        <Routes>
          {/* Default redirect to configured landing route */}
          <Route path="/" element={<Navigate to={config.defaultRoute || "/overview"} replace />} />

          {/* Active F1–F5 Feature Routes */}
          <Route path="/overview" element={<OverviewPage config={config} />} />
          <Route path="/staging" element={<WorkbookManagementPage />} />
          <Route path="/spatial-viewer" element={<SpatialViewerPage />} />
          <Route path="/schema-studio" element={<SchemaMappingPage />} />
          <Route path="/quality-audit" element={<DataQualityPage />} />
          <Route path="/approval-console" element={<ApprovalConsolePage />} />
          <Route path="/execution-monitor" element={<ExecutionMonitorPage />} />
          <Route path="/audit-ledger" element={<AuditLedgerPage />} />
          <Route
            path="/settings"
            element={<SettingsPage config={config} onUpdateConfig={onUpdateConfig || (() => {})} />}
          />

          {/* Catch-all Not Found Route */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  );
}
