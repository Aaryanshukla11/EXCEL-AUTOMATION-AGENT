import * as React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { Button } from "./Button";
import { cn } from "../../lib/utils";

export interface ErrorStateProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message: string;
  detail?: string;
  onRetry?: () => void;
}

export function ErrorState({
  className,
  title = "Something went wrong",
  message,
  detail,
  onRetry,
  ...props
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center",
        className
      )}
      {...props}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive mb-3">
        <AlertCircle className="h-5 w-5" aria-hidden="true" />
      </div>
      <h3 className="text-base font-semibold text-destructive">{title}</h3>
      <p className="mt-1 text-sm text-foreground max-w-md">{message}</p>
      {detail && (
        <pre className="mt-2 text-xs font-mono bg-muted p-2 rounded text-muted-foreground max-w-md overflow-x-auto">
          {detail}
        </pre>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="mt-4">
          <RotateCcw className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
          Retry
        </Button>
      )}
    </div>
  );
}
