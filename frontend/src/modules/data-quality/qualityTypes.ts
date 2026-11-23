import type { AnomalySeverity } from "../../contracts/spatial";
import type { QualityFindingCategory } from "../../contracts/quality";

export interface QualityFilterState {
  search: string;
  category: QualityFindingCategory | "all";
  severity: AnomalySeverity | "all";
  sheetName: string; // "all" or specific sheet
  sortBy: "severity" | "code" | "category" | "cell_ref";
  sortAsc: boolean;
}

export interface QualityCategoryCount {
  category: QualityFindingCategory;
  label: string;
  count: number;
}
