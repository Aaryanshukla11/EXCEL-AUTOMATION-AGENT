import * as React from "react";

export interface RouteDefinition {
  readonly path: string;
  readonly element: React.ReactNode;
  readonly title: string;
  readonly breadcrumb: string;
  readonly moduleKey?: string;
}

/**
 * Module Route Registry.
 * Allows downstream feature modules (F2–F5) to register their routes dynamically
 * without modifying the core shell.
 */
class RouteRegistry {
  private routes: Map<string, RouteDefinition> = new Map();

  register(route: RouteDefinition): void {
    this.routes.set(route.path, route);
  }

  getRoutes(): readonly RouteDefinition[] {
    return Array.from(this.routes.values());
  }

  getRoute(path: string): RouteDefinition | undefined {
    return this.routes.get(path);
  }
}

export const routeRegistry = new RouteRegistry();
