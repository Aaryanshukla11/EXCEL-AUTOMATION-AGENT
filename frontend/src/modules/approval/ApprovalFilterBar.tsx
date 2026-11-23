import { Search } from "lucide-react";
import type {
  ApprovalFilterState,
  ApprovalState,
  OperationRiskCategory,
  RiskLevel,
} from "./approvalTypes";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";

interface ApprovalFilterBarProps {
  filters: ApprovalFilterState;
  onFilterChange: (updated: Partial<ApprovalFilterState>) => void;
  pendingCount: number;
  totalCount: number;
}

const STATE_TABS: Array<{ id: ApprovalState | "all"; label: string }> = [
  { id: "all", label: "All Requests" },
  { id: "PENDING_REVIEW", label: "Pending Review" },
  { id: "APPROVED", label: "Approved" },
  { id: "REJECTED", label: "Rejected" },
  { id: "NEEDS_REVISION", label: "Needs Revision" },
];

export function ApprovalFilterBar({
  filters,
  onFilterChange,
  pendingCount,
  totalCount,
}: ApprovalFilterBarProps) {
  return (
    <div className="space-y-3">
      {/* State filter buttons */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-border pb-2">
        {STATE_TABS.map((tab) => {
          const isActive = filters.state === tab.id;
          return (
            <Button
              key={tab.id}
              variant={isActive ? "default" : "outline"}
              size="sm"
              onClick={() => onFilterChange({ state: tab.id })}
              className="h-7 text-xs px-2.5"
            >
              {tab.label}
              {tab.id === "PENDING_REVIEW" && pendingCount > 0 && (
                <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] bg-warning/20 text-warning font-mono">
                  {pendingCount}
                </span>
              )}
              {tab.id === "all" && (
                <span className="ml-1.5 text-[10px] text-muted-foreground font-mono">
                  ({totalCount})
                </span>
              )}
            </Button>
          );
        })}
      </div>

      {/* Search and Secondary Filter Row */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Input
            placeholder="Search by request ID, title, sheet, or risk..."
            value={filters.search}
            onChange={(e) => onFilterChange({ search: e.target.value })}
            className="h-8 pl-8 text-xs"
          />
          <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
        </div>

        <div className="flex items-center space-x-2">
          {/* Risk Level Dropdown */}
          <select
            aria-label="Filter by Risk Level"
            value={filters.riskLevel}
            onChange={(e) => onFilterChange({ riskLevel: e.target.value as RiskLevel | "all" })}
            className="h-8 text-xs rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Risk Levels</option>
            <option value="critical">Critical Risk</option>
            <option value="high">High Risk</option>
            <option value="medium">Medium Risk</option>
            <option value="low">Low Risk</option>
          </select>

          {/* Risk Category Dropdown */}
          <select
            aria-label="Filter by Risk Category"
            value={filters.riskCategory}
            onChange={(e) =>
              onFilterChange({
                riskCategory: e.target.value as OperationRiskCategory | "all",
              })
            }
            className="h-8 text-xs rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Risk Categories</option>
            <option value="read_only">Read-Only</option>
            <option value="non_destructive">Non-Destructive</option>
            <option value="ambiguous_mapping">Ambiguous Mapping</option>
            <option value="overwrite_replacement">Overwrite / Replacement</option>
            <option value="destructive">Destructive Mutation</option>
            <option value="structural_change">Structural Change</option>
            <option value="unresolved_unsupported">Unresolved / Unsupported</option>
          </select>
        </div>
      </div>
    </div>
  );
}
