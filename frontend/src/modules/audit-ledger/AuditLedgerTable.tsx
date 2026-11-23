import type { AuditBlock } from "./auditTypes";
import { Badge } from "../../components/ui/Badge";
import { cn } from "../../lib/utils";

interface AuditLedgerTableProps {
  blocks: readonly AuditBlock[];
  selectedBlockId: number | null;
  onSelectBlock: (block: AuditBlock) => void;
}

export function AuditLedgerTable({
  blocks,
  selectedBlockId,
  onSelectBlock,
}: AuditLedgerTableProps) {
  if (blocks.length === 0) {
    return (
      <div className="rounded-lg border border-border p-12 text-center text-xs text-muted-foreground bg-card">
        No audit records match the current filter criteria.
      </div>
    );
  }

  const truncateHash = (hash: string) => {
    if (hash.length <= 16) return hash;
    return `${hash.slice(0, 8)}...${hash.slice(-8)}`;
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="grid grid-cols-12 bg-muted/50 px-4 py-2.5 text-xs font-semibold text-muted-foreground border-b border-border">
        <div className="col-span-1">Block</div>
        <div className="col-span-3">Block Hash (SHA-256)</div>
        <div className="col-span-3">Parent Hash</div>
        <div className="col-span-2">Actor</div>
        <div className="col-span-2">Operation</div>
        <div className="col-span-1 text-right">Status</div>
      </div>

      <div className="divide-y divide-border">
        {blocks.map((block) => {
          const isSelected = selectedBlockId === block.block_id;
          const statusVariant =
            block.status === "COMMITTED"
              ? "success"
              : block.status === "ROLLED_BACK"
                ? "warning"
                : "destructive";

          return (
            <div
              key={block.block_id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectBlock(block)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onSelectBlock(block);
                }
              }}
              className={cn(
                "grid grid-cols-12 items-center px-4 py-2.5 text-xs transition-colors hover:bg-muted/40 cursor-pointer focus:outline-none focus:bg-muted/50",
                isSelected && "bg-muted/60 border-l-4 border-l-primary"
              )}
              data-testid={`audit-row-${block.block_id}`}
            >
              <div className="col-span-1 font-mono font-bold text-foreground">
                #{block.block_id}
              </div>

              <div
                className="col-span-3 font-mono text-[11px] text-foreground truncate pr-2"
                title={block.block_hash}
              >
                {truncateHash(block.block_hash)}
              </div>

              <div
                className="col-span-3 font-mono text-[11px] text-muted-foreground truncate pr-2"
                title={block.previous_hash}
              >
                {truncateHash(block.previous_hash)}
              </div>

              <div className="col-span-2 text-foreground truncate font-medium pr-1">
                {block.actor}
              </div>

              <div className="col-span-2 text-muted-foreground truncate font-mono text-[11px]">
                {block.operation_type}
              </div>

              <div className="col-span-1 text-right">
                <Badge variant={statusVariant} className="text-[9px] uppercase py-0 font-semibold">
                  {block.status === "COMMITTED"
                    ? "OK"
                    : block.status === "ROLLED_BACK"
                      ? "ROLLBACK"
                      : "FAIL"}
                </Badge>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
