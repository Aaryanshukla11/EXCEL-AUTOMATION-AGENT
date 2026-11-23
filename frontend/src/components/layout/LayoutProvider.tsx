import * as React from "react";
import type { ClientConfig } from "../../config/clientConfig";
import { AppShell } from "./AppShell";
import { Container } from "./Container";
import { Header } from "./Header";
import { cn } from "../../lib/utils";

export type LayoutVariant = "default" | "minimal" | "portal";

export interface LayoutProviderProps {
  config: ClientConfig;
  variant?: LayoutVariant;
  children: React.ReactNode;
  onToggleTheme?: () => void;
  className?: string;
}

/**
 * Top-level Layout Provider (Tier 5 Client Customization).
 * Decouples navigation shell and page framing from core business components.
 */
export function LayoutProvider({
  config,
  variant,
  children,
  onToggleTheme,
  className,
}: LayoutProviderProps) {
  const activeVariant = variant || config.layout.variant || "default";

  if (activeVariant === "minimal") {
    return (
      <div className={cn("min-h-screen bg-background text-foreground", className)}>
        <Container size="md" className="py-8">
          {children}
        </Container>
      </div>
    );
  }

  if (activeVariant === "portal") {
    return (
      <div className={cn("min-h-screen bg-background text-foreground flex flex-col", className)}>
        <Header config={config} onToggleTheme={onToggleTheme} />
        <main className="flex-1 p-4">{children}</main>
      </div>
    );
  }

  // Default Standard Layout using AppShell with responsive sidebar & breadcrumbs
  return (
    <AppShell config={config} onToggleTheme={onToggleTheme} className={className}>
      {children}
    </AppShell>
  );
}
