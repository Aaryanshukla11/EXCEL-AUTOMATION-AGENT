import * as React from "react";
import { AlertOctagon, X } from "lucide-react";
import { Button } from "../../components/ui/Button";

interface EmergencyAbortButtonProps {
  jobId: string;
  disabled: boolean;
  onAbort: (jobId: string, reason: string) => Promise<void>;
}

export function EmergencyAbortButton({ jobId, disabled, onAbort }: EmergencyAbortButtonProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [reason, setReason] = React.useState(
    "Operator emergency intervention: Manual abort triggered."
  );
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleConfirm = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onAbort(jobId, reason);
      setIsOpen(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Button
        variant="destructive"
        size="sm"
        disabled={disabled}
        onClick={() => setIsOpen(true)}
        className="text-xs h-8 font-semibold shadow-sm"
        data-testid="emergency-abort-button"
      >
        <AlertOctagon className="h-4 w-4 mr-1.5" />
        Emergency Abort / Rollback
      </Button>

      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="abort-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        >
          <div className="w-full max-w-md rounded-lg border border-destructive/40 bg-card p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center space-x-2 text-destructive">
                <AlertOctagon className="h-5 w-5" />
                <h2 id="abort-dialog-title" className="text-base font-semibold">
                  Confirm Emergency Rollback
                </h2>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsOpen(false)}
                className="h-7 w-7"
                aria-label="Close dialog"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <p className="text-xs text-muted-foreground">
              Aborting execution will immediately halt active mutations and restore the target
              workbook to its physical byte-for-byte{" "}
              <code className="font-mono text-foreground">.bak</code> pre-state snapshot.
            </p>

            <form onSubmit={handleConfirm} className="space-y-3">
              <div>
                <label
                  htmlFor="abort-reason"
                  className="block text-xs font-semibold text-foreground mb-1"
                >
                  Abort Rationale (Logged to Audit Trail)
                </label>
                <textarea
                  id="abort-reason"
                  rows={2}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full rounded border border-input bg-background p-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setIsOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" variant="destructive" size="sm" disabled={isSubmitting}>
                  {isSubmitting ? "Rolling Back..." : "Confirm Rollback"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
