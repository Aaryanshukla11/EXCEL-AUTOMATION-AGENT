import React from "react";

export interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
}

/**
 * Enterprise Protected Route Placeholder.
 *
 * Implements the architecture pattern for session guards and role checks
 * without fabricating backend authentication APIs.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  // In F1, session is open/local; future enterprise auth plugs into this guard.
  return <>{children}</>;
}
