import * as React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

export interface LoadingStateProps extends React.HTMLAttributes<HTMLDivElement> {
  message?: string;
  size?: "sm" | "default" | "lg";
}

export function LoadingState({
  className,
  message = "Loading...",
  size = "default",
  ...props
}: LoadingStateProps) {
  const sizeStyles = {
    sm: "h-4 w-4",
    default: "h-8 w-8",
    lg: "h-12 w-12",
  };

  return (
    <div
      role="status"
      aria-busy="true"
      aria-live="polite"
      className={cn("flex flex-col items-center justify-center p-8 space-y-3", className)}
      {...props}
    >
      <Loader2 className={cn("animate-spin text-primary", sizeStyles[size])} aria-hidden="true" />
      {message && <p className="text-sm font-medium text-muted-foreground">{message}</p>}
    </div>
  );
}
