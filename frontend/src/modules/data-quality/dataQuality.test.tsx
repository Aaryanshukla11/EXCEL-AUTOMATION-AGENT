import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DataQualityPage } from "./DataQualityPage";
import { FormulaGraphCard } from "./FormulaGraphCard";
import { filterAndSortFindings } from "./qualityUtils";
import { MOCK_QUALITY_FINDINGS, MOCK_FORMULA_GRAPH_REPORT } from "../../mocks/fixtures";
import type { QualityFilterState } from "./qualityTypes";

describe("Data Quality & Audit Console (F3)", () => {
  describe("DataQualityPage Integration", () => {
    it("renders page header, overview cards, formula graph summary, and findings table", async () => {
      render(
        <MemoryRouter>
          <DataQualityPage />
        </MemoryRouter>
      );

      expect(await screen.findByText("Data Quality & Audit Console")).toBeInTheDocument();
      expect(screen.getByText("[DEV FIXTURE]")).toBeInTheDocument();
      expect(screen.getByText("Total Inspection Findings")).toBeInTheDocument();
      expect(screen.getByText("Formula Dependency DAG & Cycle Sentinels")).toBeInTheDocument();
      expect(screen.getByText("ANOM_SPARSE_MARGIN")).toBeInTheDocument();
      expect(screen.getByText("FORMULA_VOLATILE")).toBeInTheDocument();
      expect(screen.getByText("UNSUPPORTED_SYNTAX")).toBeInTheDocument();
    });

    it("filters findings by search query", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <DataQualityPage />
        </MemoryRouter>
      );

      const searchInput = await screen.findByPlaceholderText(/Search findings, codes/i);
      await user.type(searchInput, "UNSUPPORTED");

      expect(screen.getByText("UNSUPPORTED_SYNTAX")).toBeInTheDocument();
      expect(screen.queryByText("FORMULA_VOLATILE")).not.toBeInTheDocument();
    });

    it("filters findings by category pill", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <DataQualityPage />
        </MemoryRouter>
      );

      const catBtn = await screen.findByRole("button", { name: "Volatile Function" });
      await user.click(catBtn);

      expect(screen.getByText("FORMULA_VOLATILE")).toBeInTheDocument();
      expect(screen.queryByText("ANOM_SPARSE_MARGIN")).not.toBeInTheDocument();
    });

    it("opens finding detail panel on row click and shows coordinates and evidence", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <DataQualityPage />
        </MemoryRouter>
      );

      const row = await screen.findByTestId("finding-row-find_01");
      await user.click(row);

      expect(screen.getByTestId("finding-detail-panel")).toBeInTheDocument();
      expect(screen.getAllByText("ANOM_SPARSE_MARGIN").length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("B28")).toBeInTheDocument();
      expect(screen.getByText(/ADR-005 sentinel margin scan/i)).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Inspect in Spatial Discovery Viewer/i })
      ).toBeInTheDocument();
    });
  });

  describe("FormulaGraphCard Component", () => {
    it("renders cycle-free badge, node/edge counts, and volatile cells", () => {
      render(<FormulaGraphCard report={MOCK_FORMULA_GRAPH_REPORT} />);

      expect(screen.getByText("Cycle-Free")).toBeInTheDocument();
      expect(screen.getByText("120 nodes / 145 edges")).toBeInTheDocument();
      expect(screen.getByText(/Revenue!E25/i)).toBeInTheDocument();
      expect(screen.getByText(/Expenses!F15/i)).toBeInTheDocument();
    });

    it("renders nothing when report is null", () => {
      const { container } = render(<FormulaGraphCard report={null} />);
      expect(container).toBeEmptyDOMElement();
    });
  });

  describe("Quality Filter & Sort Utilities (Unit)", () => {
    it("filters findings by severity and sorts by code", () => {
      const filters: QualityFilterState = {
        search: "",
        category: "all",
        severity: "warning",
        sheetName: "all",
        sortBy: "code",
        sortAsc: true,
      };

      const result = filterAndSortFindings(MOCK_QUALITY_FINDINGS, filters);
      expect(result.length).toBe(2);
      expect(result.every((r) => r.severity === "warning")).toBe(true);
      expect(result[0]?.code.localeCompare(result[1]?.code || "")).toBeLessThanOrEqual(0);
    });
  });
});
