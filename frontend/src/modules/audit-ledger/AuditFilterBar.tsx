import { Search } from "lucide-react";
import type { AuditFilterState } from "./auditTypes";
import { Input } from "../../components/ui/Input";
import { cn } from "../../lib/utils";

interface AuditFilterBarProps {
  filters: AuditFilterState;
  onFilterChange: (updated: Partial<AuditFilterState>) => void;
  totalCount: number;
}

export function AuditFilterBar({ filters, onFilterChange, totalCount }: AuditFilterBarProps) {
  const statusOptions = [
    { id: "all", label: "All" },
    { id: "COMMITTED", label: "Committed" },
    { id: "ROLLED_BACK", label: "Rolled Back" },
    { id: "FAILED", label: "Failed" },
  ] as const;

  return (
    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-card p-3 rounded-lg border border-border">
      {/* Search */}
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          type="search"
          placeholder="Search by hash, actor, operation, workbook..."
          value={filters.search}
          onChange={(e) => onFilterChange({ search: e.target.value })}
          className="pl-8 text-xs h-9"
          aria-label="Search audit records"
        />
      </div>

      {/* Status Pills */}
      <div className="flex items-center space-x-1">
        {statusOptions.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => onFilterChange({ status: opt.id })}
            className={cn(
              "text-xs px-2.5 py-1 rounded font-medium transition-colors",
              filters.status === opt.id
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="text-[11px] text-muted-foreground shrink-0 font-mono">
        Records: <span className="text-foreground font-semibold">{totalCount}</span>
      </div>
    </div>
  );
}
