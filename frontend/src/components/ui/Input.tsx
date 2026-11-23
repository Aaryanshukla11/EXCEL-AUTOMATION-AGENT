import * as React from "react";
import { cn } from "../../lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", error = false, helperText, id, ...props }, ref) => {
    const helperId = id && helperText ? `${id}-helper` : undefined;

    return (
      <div className="w-full">
        <input
          type={type}
          id={id}
          ref={ref}
          aria-invalid={error ? "true" : "false"}
          aria-describedby={helperId}
          className={cn(
            "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors",
            "file:border-0 file:bg-transparent file:text-sm file:font-medium",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
            error && "border-destructive focus-visible:ring-destructive",
            className
          )}
          {...props}
        />
        {helperText && (
          <p
            id={helperId}
            className={cn("mt-1 text-xs", error ? "text-destructive" : "text-muted-foreground")}
          >
            {helperText}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";
