import { Search } from "lucide-react";
import type { AnomalySeverity } from "../../contracts/spatial";
import type { QualityFindingCategory } from "../../contracts/quality";
import type { QualityFilterState } from "./qualityTypes";
import { CATEGORY_LABELS } from "./qualityUtils";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";

interface FindingsFilterBarProps {
  filters: QualityFilterState;
  onFilterChange: (updated: Partial<QualityFilterState>) => void;
  availableSheets: readonly string[];
}

export function FindingsFilterBar({
  filters,
  onFilterChange,
  availableSheets,
}: FindingsFilterBarProps) {
  return (
    <div className="space-y-3">
      {/* Top Search & Dropdown Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Input
            placeholder="Search findings, codes, coordinates..."
            value={filters.search}
            onChange={(e) => onFilterChange({ search: e.target.value })}
            className="h-8 pl-8 text-xs"
          />
          <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
        </div>

        <div className="flex items-center space-x-2">
          {/* Severity Filter */}
          <select
            aria-label="Filter by severity"
            value={filters.severity}
            onChange={(e) =>
              onFilterChange({ severity: e.target.value as AnomalySeverity | "all" })
            }
            className="h-8 text-xs rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          {/* Worksheet Filter */}
          <select
            aria-label="Filter by worksheet"
            value={filters.sheetName}
            onChange={(e) => onFilterChange({ sheetName: e.target.value })}
            className="h-8 text-xs rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Worksheets</option>
            {availableSheets.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          {/* Sort Selection */}
          <select
            aria-label="Sort findings"
            value={filters.sortBy}
            onChange={(e) =>
              onFilterChange({
                sortBy: e.target.value as "severity" | "code" | "category" | "cell_ref",
              })
            }
            className="h-8 text-xs rounded border border-input bg-background px-2 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="severity">Sort by Severity</option>
            <option value="code">Sort by Code</option>
            <option value="category">Sort by Category</option>
            <option value="cell_ref">Sort by Coordinate</option>
          </select>
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
        <Button
          variant={filters.category === "all" ? "default" : "outline"}
          size="sm"
          onClick={() => onFilterChange({ category: "all" })}
          className="h-6 text-[11px] px-2.5"
        >
          All Categories
        </Button>
        {Object.entries(CATEGORY_LABELS).map(([catKey, label]) => (
          <Button
            key={catKey}
            variant={filters.category === catKey ? "default" : "outline"}
            size="sm"
            onClick={() => onFilterChange({ category: catKey as QualityFindingCategory })}
            className="h-6 text-[11px] px-2.5 whitespace-nowrap"
          >
            {label}
          </Button>
        ))}
      </div>
    </div>
  );
}
