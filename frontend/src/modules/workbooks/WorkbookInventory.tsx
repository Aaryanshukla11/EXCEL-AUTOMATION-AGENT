import * as React from "react";
import { ArrowUpDown, FileSpreadsheet, Search } from "lucide-react";
import { Input } from "../../components/ui/Input";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import type { WorkbookInventoryItem } from "./workbookTypes";
import { formatBytes } from "./workbookUtils";

interface WorkbookInventoryProps {
  items: readonly WorkbookInventoryItem[];
  onSelectWorkbook: (id: string) => void;
}

export function WorkbookInventory({ items, onSelectWorkbook }: WorkbookInventoryProps) {
  const [search, setSearch] = React.useState("");
  const [sortField, setSortField] = React.useState<"name" | "sizeBytes" | "sheetCount">("name");
  const [sortAsc, setSortAsc] = React.useState(true);
  const [statusFilter, setStatusFilter] = React.useState<string>("all");

  const filteredItems = React.useMemo(() => {
    return items
      .filter((item) => {
        const matchesSearch = item.name.toLowerCase().includes(search.toLowerCase());
        const matchesStatus =
          statusFilter === "all" ||
          (statusFilter === "completed" && item.discoveryStatus === "completed") ||
          (statusFilter === "staged" && item.source === "memory_staged");
        return matchesSearch && matchesStatus;
      })
      .sort((a, b) => {
        let valA = a[sortField];
        let valB = b[sortField];
        if (typeof valA === "string") valA = valA.toLowerCase();
        if (typeof valB === "string") valB = valB.toLowerCase();
        if (valA < valB) return sortAsc ? -1 : 1;
        if (valA > valB) return sortAsc ? 1 : -1;
        return 0;
      });
  }, [items, search, sortField, sortAsc, statusFilter]);

  const toggleSort = (field: "name" | "sizeBytes" | "sheetCount") => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Workbook Inventory</CardTitle>
            <CardDescription>Available workbooks and discovery profiles</CardDescription>
          </div>
          <div className="flex items-center space-x-2">
            <Badge variant="outline" className="font-mono text-xs">
              {filteredItems.length} Available
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Search & Filters */}
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative w-full sm:w-72">
            <Input
              placeholder="Search workbooks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
            <Search className="h-4 w-4 absolute left-3 top-2.5 text-muted-foreground" />
          </div>

          <div className="flex items-center space-x-1.5 w-full sm:w-auto">
            <Button
              variant={statusFilter === "all" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("all")}
              className="text-xs h-8"
            >
              All
            </Button>
            <Button
              variant={statusFilter === "completed" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("completed")}
              className="text-xs h-8"
            >
              Discovered
            </Button>
            <Button
              variant={statusFilter === "staged" ? "default" : "outline"}
              size="sm"
              onClick={() => setStatusFilter("staged")}
              className="text-xs h-8"
            >
              Staged
            </Button>
          </div>
        </div>

        {/* Inventory List / Table */}
        {filteredItems.length === 0 ? (
          <EmptyState
            icon={<FileSpreadsheet className="h-6 w-6 text-muted-foreground" />}
            title="No workbooks match your filter"
            description="Stage a new workbook above or clear your search query."
          />
        ) : (
          <div className="rounded-md border border-border overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 border-b border-border text-xs text-muted-foreground uppercase font-medium">
                <tr>
                  <th className="p-3 cursor-pointer select-none" onClick={() => toggleSort("name")}>
                    <div className="flex items-center space-x-1">
                      <span>Workbook Name</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>
                  <th className="p-3">Format</th>
                  <th
                    className="p-3 cursor-pointer select-none"
                    onClick={() => toggleSort("sizeBytes")}
                  >
                    <div className="flex items-center space-x-1">
                      <span>File Size</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>
                  <th
                    className="p-3 cursor-pointer select-none"
                    onClick={() => toggleSort("sheetCount")}
                  >
                    <div className="flex items-center space-x-1">
                      <span>Sheets</span>
                      <ArrowUpDown className="h-3 w-3" />
                    </div>
                  </th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filteredItems.map((wb) => (
                  <tr key={wb.id} className="hover:bg-muted/30 transition-colors">
                    <td className="p-3 font-medium text-foreground flex items-center space-x-2">
                      <FileSpreadsheet className="h-4 w-4 text-primary flex-shrink-0" />
                      <span className="truncate max-w-xs">{wb.name}</span>
                    </td>
                    <td className="p-3">
                      <Badge variant="outline" className="font-mono text-[10px] uppercase">
                        {wb.format}
                      </Badge>
                    </td>
                    <td className="p-3 font-mono text-xs">{formatBytes(wb.sizeBytes)}</td>
                    <td className="p-3 font-mono text-xs">{wb.sheetCount}</td>
                    <td className="p-3">
                      {wb.source === "backend_fixture" ? (
                        <Badge variant="success" className="text-[10px]">
                          [FIXTURE] Discovered
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px]">
                          [LOCAL] In-Memory
                        </Badge>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onSelectWorkbook(wb.id)}
                        className="h-7 text-xs"
                      >
                        Spatial View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
