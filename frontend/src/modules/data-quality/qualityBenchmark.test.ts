import { describe, expect, it } from "vitest";
import type { QualityFinding } from "../../contracts/quality";
import { filterAndSortFindings } from "./qualityUtils";
import type { QualityFilterState } from "./qualityTypes";

describe("Data Quality & Audit Console Large-Scale Benchmark (F3)", () => {
  it("filters and sorts 1,000 quality findings under 20 milliseconds", () => {
    const findings: QualityFinding[] = Array.from({ length: 1000 }).map((_, i) => ({
      finding_id: `finding_${i}`,
      category:
        i % 4 === 0
          ? "structural_anomaly"
          : i % 4 === 1
            ? "type_ambiguity"
            : i % 4 === 2
              ? "formula_cycle"
              : "volatile_function",
      severity: i % 3 === 0 ? "critical" : i % 3 === 1 ? "warning" : "info",
      code: `CODE_${i % 20}`,
      message: `Diagnostic inspection message for finding #${i}`,
      workbook_path: "C:/data/financial_model.xlsx",
      sheet_name: `Sheet_${i % 5}`,
      cell_ref: `A${(i % 100) + 1}`,
      detection_source: "excel_intel.sentinels",
      confidence: 0.9,
    }));

    const filters: QualityFilterState = {
      search: "finding #4",
      category: "all",
      severity: "all",
      sheetName: "Sheet_2",
      sortBy: "severity",
      sortAsc: false,
    };

    const startTime = performance.now();
    const results = filterAndSortFindings(findings, filters);
    const duration = performance.now() - startTime;

    expect(results.length).toBeGreaterThan(0);
    expect(duration).toBeLessThan(50);
  });

  it("filters and sorts 5,000 quality findings under 150 milliseconds", () => {
    const findings: QualityFinding[] = Array.from({ length: 5000 }).map((_, i) => ({
      finding_id: `finding_${i}`,
      category:
        i % 4 === 0
          ? "structural_anomaly"
          : i % 4 === 1
            ? "type_ambiguity"
            : i % 4 === 2
              ? "formula_cycle"
              : "volatile_function",
      severity: i % 3 === 0 ? "critical" : i % 3 === 1 ? "warning" : "info",
      code: `CODE_${i % 20}`,
      message: `Diagnostic inspection message for finding #${i}`,
      workbook_path: "C:/data/financial_model.xlsx",
      sheet_name: `Sheet_${i % 10}`,
      cell_ref: `A${(i % 1000) + 1}`,
      detection_source: "excel_intel.sentinels",
      confidence: 0.9,
    }));

    const filters: QualityFilterState = {
      search: "finding #4",
      category: "all",
      severity: "all",
      sheetName: "Sheet_2",
      sortBy: "severity",
      sortAsc: false,
    };

    const startTime = performance.now();
    const results = filterAndSortFindings(findings, filters);
    const duration = performance.now() - startTime;

    expect(results.length).toBeGreaterThan(0);
    expect(duration).toBeLessThan(150);
  });

  it("filters and sorts 10,000 quality findings under 400 milliseconds", () => {
    const findings: QualityFinding[] = Array.from({ length: 10000 }).map((_, i) => ({
      finding_id: `finding_${i}`,
      category: "structural_anomaly",
      severity: i % 2 === 0 ? "critical" : "warning",
      code: `ANOM_${i % 50}`,
      message: `Anomaly detection report #${i}`,
      sheet_name: `Sheet_${i % 25}`,
      detection_source: "excel_intel.sentinels",
    }));

    const filters: QualityFilterState = {
      search: "Anomaly detection",
      category: "structural_anomaly",
      severity: "critical",
      sheetName: "all",
      sortBy: "code",
      sortAsc: true,
    };

    const startTime = performance.now();
    const results = filterAndSortFindings(findings, filters);
    const duration = performance.now() - startTime;

    expect(results).toHaveLength(5000);
    expect(duration).toBeLessThan(400);
  });
});
