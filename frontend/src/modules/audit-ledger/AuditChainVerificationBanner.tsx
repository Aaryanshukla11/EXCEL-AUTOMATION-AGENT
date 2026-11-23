import { RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import type { AuditChainVerificationResult } from "./auditTypes";
import { Button } from "../../components/ui/Button";

interface AuditChainVerificationBannerProps {
  result: AuditChainVerificationResult | null;
  isVerifying: boolean;
  onVerify: () => Promise<void>;
}

export function AuditChainVerificationBanner({
  result,
  isVerifying,
  onVerify,
}: AuditChainVerificationBannerProps) {
  if (!result) return null;

  return (
    <div
      data-testid="audit-chain-banner"
      className={`rounded-lg border p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
        result.is_valid
          ? "border-success/30 bg-success/5"
          : "border-destructive/40 bg-destructive/5"
      }`}
    >
      <div className="flex items-start space-x-3">
        <div className="pt-0.5">
          {result.is_valid ? (
            <ShieldCheck className="h-6 w-6 text-success" />
          ) : (
            <ShieldAlert className="h-6 w-6 text-destructive" />
          )}
        </div>
        <div className="space-y-0.5">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-semibold text-foreground">
              {result.is_valid
                ? "Cryptographic SHA-256 Hash-Chain Intact"
                : "Hash Chain Verification Failure"}
            </h3>
            <span
              className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                result.is_valid
                  ? "bg-success/20 text-success"
                  : "bg-destructive/20 text-destructive"
              }`}
            >
              {result.is_valid ? "VALIDATED" : "BROKEN LINK"}
            </span>
          </div>

          <p className="text-xs text-muted-foreground">
            {result.is_valid
              ? `All ${result.verified_blocks} audit blocks cryptographically validated against previous parent hashes.`
              : result.error_message ||
                "A mismatch was detected between child previous_hash and parent block_hash."}
          </p>
        </div>
      </div>

      <Button
        variant="outline"
        size="sm"
        disabled={isVerifying}
        onClick={onVerify}
        className="h-8 text-xs shrink-0 self-start sm:self-center"
        data-testid="reverify-chain-button"
      >
        <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${isVerifying ? "animate-spin" : ""}`} />
        {isVerifying ? "Verifying..." : "Re-Verify Chain"}
      </Button>
    </div>
  );
}
