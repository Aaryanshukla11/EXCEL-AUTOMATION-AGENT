import * as React from "react";
import { cn } from "../../lib/utils";

export interface DataTableSkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  rows?: number;
  columns?: number;
}

export function DataTableSkeleton({
  className,
  rows = 5,
  columns = 4,
  ...props
}: DataTableSkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Loading table data"
      aria-busy="true"
      className={cn("w-full overflow-hidden rounded-md border border-border", className)}
      {...props}
    >
      {/* Header skeleton */}
      <div className="flex border-b border-border bg-muted/50 p-3">
        {Array.from({ length: columns }).map((_, i) => (
          <div key={`header-${i}`} className="flex-1 px-2">
            <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
          </div>
        ))}
      </div>

      {/* Row skeletons */}
      <div className="divide-y divide-border bg-background">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={`row-${r}`} className="flex p-3">
            {Array.from({ length: columns }).map((_, c) => (
              <div key={`cell-${r}-${c}`} className="flex-1 px-2">
                <div
                  className="h-4 rounded bg-muted/60 animate-pulse"
                  style={{
                    width: `${Math.floor(50 + ((r * 13 + c * 29) % 45))}%`,
                  }}
                />
              </div>
            ))}
          </div>
        ))}
      </div>
      <span className="sr-only">Loading table data...</span>
    </div>
  );
}
