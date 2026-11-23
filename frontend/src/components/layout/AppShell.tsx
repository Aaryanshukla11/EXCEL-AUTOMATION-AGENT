import * as React from "react";
import type { ClientConfig } from "../../config/clientConfig";
import { resolveNavigation } from "../../navigation/defaultNavigation";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import { Breadcrumbs } from "./Breadcrumbs";
import { Container } from "./Container";
import { cn } from "../../lib/utils";

export interface AppShellProps {
  config: ClientConfig;
  onToggleTheme?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function AppShell({ config, onToggleTheme, children, className }: AppShellProps) {
  const [isCollapsed, setIsCollapsed] = React.useState(config.layout.sidebarCollapsedDefault);
  const [isMobileOpen, setIsMobileOpen] = React.useState(false);

  const sections = React.useMemo(() => resolveNavigation(config), [config]);

  return (
    <div className={cn("min-h-screen bg-background text-foreground flex flex-col", className)}>
      {/* Top Application Header */}
      <Header
        config={config}
        onToggleTheme={onToggleTheme}
        onToggleMobileNav={() => setIsMobileOpen((prev) => !prev)}
      />

      {/* Main Body with Sidebar & Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Navigation Sidebar */}
        <Sidebar
          sections={sections}
          isCollapsed={isCollapsed}
          onToggleCollapse={() => setIsCollapsed((prev) => !prev)}
          isMobileOpen={isMobileOpen}
          onCloseMobile={() => setIsMobileOpen(false)}
        />

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto flex flex-col">
          {/* Breadcrumb sub-header */}
          <div className="border-b border-border bg-muted/20 px-6 py-2.5">
            <Breadcrumbs config={config} />
          </div>

          {/* Primary View Container */}
          <div className="flex-1 py-6">
            <Container size="xl">{children}</Container>
          </div>

          {/* Status Bar / Footer */}
          <footer className="border-t border-border bg-muted/10 px-6 py-3 text-xs text-muted-foreground flex flex-col sm:flex-row items-center justify-between space-y-1 sm:space-y-0">
            <div>
              <span>Deterministic Core: </span>
              <span className="font-semibold text-foreground">Verified</span>
              <span className="mx-2">•</span>
              <span>Architecture Release 1.0</span>
            </div>
            <div className="font-mono text-[11px]">Memory Soft Ceiling: 235 MiB | Cap: 250 MiB</div>
          </footer>
        </main>
      </div>
    </div>
  );
}
