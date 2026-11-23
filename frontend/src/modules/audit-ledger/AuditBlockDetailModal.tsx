import { CheckCircle2, Copy, X } from "lucide-react";
import * as React from "react";
import type { AuditBlock } from "./auditTypes";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

interface AuditBlockDetailModalProps {
  block: AuditBlock | null;
  onClose: () => void;
}

export function AuditBlockDetailModal({ block, onClose }: AuditBlockDetailModalProps) {
  const [copied, setCopied] = React.useState(false);

  if (!block) return null;

  const handleCopyHash = () => {
    void navigator.clipboard?.writeText(block.block_hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="audit-detail-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
    >
      <div className="w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center space-x-2">
            <h2 id="audit-detail-title" className="text-base font-semibold text-foreground">
              Audit Block #{block.block_id} Details
            </h2>
            <Badge
              variant={
                block.status === "COMMITTED"
                  ? "success"
                  : block.status === "ROLLED_BACK"
                    ? "warning"
                    : "destructive"
              }
              className="text-[10px]"
            >
              {block.status}
            </Badge>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-7 w-7"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-3 text-xs">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-2 bg-muted/20 p-3 rounded border border-border">
            <div>
              <span className="text-[10px] text-muted-foreground uppercase block font-medium">
                Actor
              </span>
              <span className="text-foreground font-semibold">{block.actor}</span>
            </div>
            <div>
              <span className="text-[10px] text-muted-foreground uppercase block font-medium">
                Timestamp
              </span>
              <span className="text-foreground">{new Date(block.timestamp).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-[10px] text-muted-foreground uppercase block font-medium">
                Target
              </span>
              <span className="text-foreground">
                {block.target_workbook} ({block.target_sheet})
              </span>
            </div>
            <div>
              <span className="text-[10px] text-muted-foreground uppercase block font-medium">
                Operation
              </span>
              <span className="text-foreground font-mono">{block.operation_type}</span>
            </div>
          </div>

          {/* Cryptographic Hashes */}
          <div className="space-y-2 font-mono text-[11px] bg-muted/30 p-3 rounded border border-border">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-muted-foreground uppercase text-[10px] font-sans font-semibold">
                  Block SHA-256 Hash
                </span>
                <button
                  type="button"
                  onClick={handleCopyHash}
                  className="text-primary hover:text-primary/80 flex items-center space-x-1 text-[10px]"
                >
                  {copied ? <CheckCircle2 className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              </div>
              <div className="text-foreground break-all p-1.5 bg-background rounded border border-border">
                {block.block_hash}
              </div>
            </div>

            <div>
              <span className="text-muted-foreground uppercase text-[10px] font-sans font-semibold block mb-1">
                Previous Block Hash (Parent Link)
              </span>
              <div className="text-muted-foreground break-all p-1.5 bg-background rounded border border-border">
                {block.previous_hash}
              </div>
            </div>
          </div>

          {/* Payload Summary */}
          <div>
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block mb-1">
              Operation Summary & Ledger Evidence
            </span>
            <div className="p-2.5 rounded bg-muted/20 border border-border text-foreground">
              {block.payload_summary}
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
