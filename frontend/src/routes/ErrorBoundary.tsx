import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "../components/ui/ErrorState";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Route-Level Error Boundary.
 * Catches unhandled render crashes and presents a resilient fallback with retry.
 */
export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("[Route ErrorBoundary Caught Exception]:", error, errorInfo);
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="p-8">
          <ErrorState
            title={this.props.fallbackTitle || "Application Navigation Error"}
            message="An unexpected error occurred while rendering this module."
            detail={this.state.error?.message || "Unknown error details"}
            onRetry={this.handleRetry}
          />
        </div>
      );
    }

    return this.props.children;
  }
}
