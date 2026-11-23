import * as React from "react";
import { AlertCircle, CheckCircle2, ChevronRight, Search, Sparkles } from "lucide-react";
import type {
  DraftColumnMapping,
  MappingCandidate,
  TargetMasterColumn,
} from "../../contracts/mapping";
import type { ColumnMetadata } from "../../contracts/discovery";
import { Input } from "../../components/ui/Input";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { buildMappingPairs } from "./mappingUtils";
import type { MappingFilterStatus } from "./mappingTypes";
import { cn } from "../../lib/utils";

interface MappingWorkspaceProps {
  sourceColumns: readonly ColumnMetadata[];
  targetColumns: readonly TargetMasterColumn[];
  candidates: readonly MappingCandidate[];
  drafts: readonly DraftColumnMapping[];
  selectedSourceColIndex: number | null;
  onSelectSourceColumn: (colIndex: number) => void;
  onAutoApply: () => void;
  onClearDrafts: () => void;
}

export function MappingWorkspace({
  sourceColumns,
  targetColumns,
  candidates,
  drafts,
  selectedSourceColIndex,
  onSelectSourceColumn,
  onAutoApply,
  onClearDrafts,
}: MappingWorkspaceProps) {
  const [search, setSearch] = React.useState("");
  const [filter, setFilter] = React.useState<MappingFilterStatus>("all");

  const pairs = React.useMemo(() => {
    return buildMappingPairs(sourceColumns, targetColumns, candidates, drafts);
  }, [sourceColumns, targetColumns, candidates, drafts]);

  const filteredPairs = React.useMemo(() => {
    return pairs.filter((pair) => {
      const matchSearch =
        pair.sourceColumn.header_name.toLowerCase().includes(search.toLowerCase()) ||
        (pair.targetColumn && pair.targetColumn.name.toLowerCase().includes(search.toLowerCase()));

      let matchFilter = true;
      if (filter === "mapped") matchFilter = !!pair.draft;
      if (filter === "unmapped") matchFilter = !pair.draft;
      if (filter === "candidates") matchFilter = pair.candidates.length > 0;
      if (filter === "conflicts") matchFilter = pair.isConflict;

      return matchSearch && matchFilter;
    });
  }, [pairs, search, filter]);

  const mappedCount = pairs.filter((p) => p.draft).length;
  const conflictCount = pairs.filter((p) => p.isConflict).length;

  return (
    <div className="space-y-3">
      {/* Search, Filter, and Action Toolbar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <div className="relative w-full sm:w-60">
            <Input
              placeholder="Filter columns..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 pl-8 text-xs"
            />
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-muted-foreground" />
          </div>

          <div className="flex items-center space-x-1">
            <Button
              variant={filter === "all" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("all")}
              className="h-7 text-[11px] px-2"
            >
              All ({pairs.length})
            </Button>
            <Button
              variant={filter === "mapped" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("mapped")}
              className="h-7 text-[11px] px-2"
            >
              Drafted ({mappedCount})
            </Button>
            <Button
              variant={filter === "unmapped" ? "default" : "outline"}
              size="sm"
              onClick={() => setFilter("unmapped")}
              className="h-7 text-[11px] px-2"
            >
              Unmapped ({pairs.length - mappedCount})
            </Button>
            {conflictCount > 0 && (
              <Button
                variant={filter === "conflicts" ? "destructive" : "outline"}
                size="sm"
                onClick={() => setFilter("conflicts")}
                className="h-7 text-[11px] px-2 text-destructive"
              >
                Conflicts ({conflictCount})
              </Button>
            )}
          </div>
        </div>

        <div className="flex items-center space-x-2 self-end sm:self-center">
          <Button
            variant="outline"
            size="sm"
            onClick={onAutoApply}
            className="h-7 text-xs"
            title="Auto-apply all high-confidence recommendations (>= 85%)"
          >
            <Sparkles className="h-3.5 w-3.5 mr-1 text-primary" />
            Apply Recommendations
          </Button>
          {drafts.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearDrafts}
              className="h-7 text-xs text-destructive hover:text-destructive"
            >
              Clear Drafts
            </Button>
          )}
        </div>
      </div>

      {/* Column Mapping Table Header */}
      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="grid grid-cols-12 bg-muted/50 px-4 py-2 text-xs font-semibold text-muted-foreground border-b border-border">
          <div className="col-span-5">Source Column (Discovered)</div>
          <div className="col-span-2 text-center">Relationship</div>
          <div className="col-span-5">Target Column (Master Schema)</div>
        </div>

        {/* Mapping Rows */}
        <div className="divide-y divide-border">
          {filteredPairs.length > 0 ? (
            filteredPairs.map((pair) => {
              const isSelected = selectedSourceColIndex === pair.sourceColumn.index;

              return (
                <div
                  key={pair.sourceColumn.index}
                  onClick={() => onSelectSourceColumn(pair.sourceColumn.index)}
                  className={cn(
                    "grid grid-cols-12 px-4 py-3 items-center text-xs cursor-pointer transition-colors",
                    isSelected
                      ? "bg-primary/10 border-l-4 border-primary"
                      : "hover:bg-muted/30 border-l-4 border-transparent"
                  )}
                  data-testid={`mapping-row-${pair.sourceColumn.index}`}
                >
                  {/* Source Column */}
                  <div className="col-span-5 flex items-center space-x-2 truncate">
                    <span className="font-mono text-muted-foreground">
                      #{pair.sourceColumn.index}
                    </span>
                    <span className="font-medium text-foreground truncate">
                      {pair.sourceColumn.header_name}
                    </span>
                    <Badge variant="outline" className="font-mono text-[9px] uppercase">
                      {pair.sourceColumn.inferred_type}
                    </Badge>
                  </div>

                  {/* Relationship / Status Icon */}
                  <div className="col-span-2 flex items-center justify-center">
                    {pair.isConflict ? (
                      <Badge variant="destructive" className="text-[10px] py-0">
                        <AlertCircle className="h-3 w-3 mr-0.5" /> Conflict
                      </Badge>
                    ) : pair.draft ? (
                      <Badge variant="success" className="text-[10px] py-0">
                        <CheckCircle2 className="h-3 w-3 mr-0.5" /> Draft
                      </Badge>
                    ) : pair.candidates.length > 0 ? (
                      <Badge variant="secondary" className="text-[10px] py-0">
                        <Sparkles className="h-3 w-3 mr-0.5 text-primary" />{" "}
                        {pair.candidates.length} Cand.
                      </Badge>
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground opacity-40" />
                    )}
                  </div>

                  {/* Target Column */}
                  <div className="col-span-5 flex items-center space-x-2 truncate">
                    {pair.targetColumn ? (
                      <>
                        <span className="font-medium text-foreground truncate">
                          {pair.targetColumn.name}
                        </span>
                        <Badge variant="outline" className="font-mono text-[9px] uppercase">
                          {pair.targetColumn.expected_type}
                        </Badge>
                      </>
                    ) : (
                      <span className="text-muted-foreground italic text-[11px]">
                        Unmapped target field
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-8 text-center text-muted-foreground text-xs">
              No columns match the current filter.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
