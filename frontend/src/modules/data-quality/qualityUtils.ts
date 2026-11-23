import type { QualityFinding, QualityFindingCategory } from "../../contracts/quality";
import type { QualityFilterState } from "./qualityTypes";

export const CATEGORY_LABELS: Record<QualityFindingCategory, string> = {
  structural_anomaly: "Structural Anomaly",
  type_ambiguity: "Type Ambiguity",
  formula_cycle: "Calculation Cycle",
  unsupported_formula: "Unsupported Syntax",
  unresolved_dependency: "Unresolved Reference",
  volatile_function: "Volatile Function",
  dynamic_spill: "Dynamic Spill Range",
};

const SEVERITY_WEIGHTS: Record<string, number> = {
  critical: 3,
  warning: 2,
  info: 1,
};

export function filterAndSortFindings(
  findings: readonly QualityFinding[],
  filters: QualityFilterState
): QualityFinding[] {
  const search = filters.search.trim().toLowerCase();
  const hasSearch = search.length > 0;
  const filterCat = filters.category !== "all" ? filters.category : null;
  const filterSev = filters.severity !== "all" ? filters.severity : null;
  const filterSheet = filters.sheetName !== "all" ? filters.sheetName : null;

  return findings
    .filter((f) => {
      if (filterCat && f.category !== filterCat) return false;
      if (filterSev && f.severity !== filterSev) return false;
      if (filterSheet && f.sheet_name !== filterSheet) return false;
      if (!hasSearch) return true;

      return (
        f.message.toLowerCase().includes(search) ||
        f.code.toLowerCase().includes(search) ||
        (f.cell_ref != null && f.cell_ref.toLowerCase().includes(search)) ||
        (f.column_name != null && f.column_name.toLowerCase().includes(search))
      );
    })
    .sort((a, b) => {
      let comp = 0;
      if (filters.sortBy === "severity") {
        const weightA = SEVERITY_WEIGHTS[a.severity] || 0;
        const weightB = SEVERITY_WEIGHTS[b.severity] || 0;
        comp = weightB - weightA; // higher severity first by default
      } else if (filters.sortBy === "code") {
        comp = a.code < b.code ? -1 : a.code > b.code ? 1 : 0;
      } else if (filters.sortBy === "category") {
        comp = a.category < b.category ? -1 : a.category > b.category ? 1 : 0;
      } else if (filters.sortBy === "cell_ref") {
        const refA = a.cell_ref || "";
        const refB = b.cell_ref || "";
        comp = refA < refB ? -1 : refA > refB ? 1 : 0;
      }
      return filters.sortAsc ? comp : -comp;
    });
}
