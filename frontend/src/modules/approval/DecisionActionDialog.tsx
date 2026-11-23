import * as React from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, X } from "lucide-react";
import type { ApprovalRequest, DecisionSubmitPayload } from "./approvalTypes";
import { Button } from "../../components/ui/Button";

interface DecisionActionDialogProps {
  request: ApprovalRequest;
  action: "APPROVED" | "REJECTED" | "NEEDS_REVISION";
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: DecisionSubmitPayload) => Promise<void>;
}

export function DecisionActionDialog({
  request,
  action,
  isOpen,
  onClose,
  onSubmit,
}: DecisionActionDialogProps) {
  const [rationale, setRationale] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [validationError, setValidationError] = React.useState<string | null>(null);

  if (!isOpen) return null;

  const isMandatoryRationale = action === "REJECTED" || action === "NEEDS_REVISION";

  const actionTitle =
    action === "APPROVED"
      ? "Confirm Operation Approval"
      : action === "REJECTED"
        ? "Confirm Operation Rejection"
        : "Request Operation Revision";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const trimmedRationale = rationale.trim();
    if (isMandatoryRationale && trimmedRationale.length < 5) {
      setValidationError("Mandatory decision rationale of at least 5 characters is required.");
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit({
        decision: action,
        reviewer_identity: "Client Admin (Frontend Simulated)",
        rationale: trimmedRationale || undefined,
        target_version: request.version,
      });
      onClose();
    } catch (err) {
      setValidationError(err instanceof Error ? err.message : "Failed to submit decision.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="decision-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div className="w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center space-x-2">
            {action === "APPROVED" ? (
              <CheckCircle2 className="h-5 w-5 text-success" />
            ) : action === "REJECTED" ? (
              <AlertCircle className="h-5 w-5 text-destructive" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-warning" />
            )}
            <h2 id="decision-dialog-title" className="text-base font-semibold text-foreground">
              {actionTitle}
            </h2>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="Close dialog"
            className="h-7 w-7"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-3 text-xs">
          <div className="rounded border border-border p-3 bg-muted/30 space-y-1">
            <span className="font-semibold text-foreground">{request.title}</span>
            <div className="text-muted-foreground flex items-center space-x-2">
              <span>Request ID: {request.request_id}</span>
              <span>•</span>
              <span>Target Version: {request.version}</span>
            </div>
            <div className="text-muted-foreground">
              Risk: <span className="font-semibold uppercase">{request.risk.level}</span> (
              {request.risk.title})
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label
                htmlFor="decision-rationale"
                className="block text-xs font-semibold text-foreground mb-1"
              >
                Decision Rationale {isMandatoryRationale ? "(Required)" : "(Optional)"}
              </label>
              <textarea
                id="decision-rationale"
                aria-label="Decision rationale"
                rows={3}
                value={rationale}
                onChange={(e) => {
                  setRationale(e.target.value);
                  if (validationError) setValidationError(null);
                }}
                placeholder={
                  isMandatoryRationale
                    ? "Enter detailed operational reasons for rejection or revision request..."
                    : "Optional operational notes for record-keeping..."
                }
                className="w-full rounded border border-input bg-background p-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
              {validationError && (
                <span className="text-[11px] text-destructive block mt-1 font-medium">
                  {validationError}
                </span>
              )}
            </div>

            <div className="rounded bg-muted/40 p-2.5 text-[11px] text-muted-foreground">
              <span className="font-semibold block mb-0.5">Simulated Decision Scope:</span>
              Decisions recorded in this console demonstrate client workflow governance and are not
              sent to live backend authorities. Approval does not trigger execution (F5).
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant={
                  action === "APPROVED"
                    ? "default"
                    : action === "REJECTED"
                      ? "destructive"
                      : "secondary"
                }
                size="sm"
                disabled={isSubmitting}
              >
                {isSubmitting ? "Submitting..." : actionTitle}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
