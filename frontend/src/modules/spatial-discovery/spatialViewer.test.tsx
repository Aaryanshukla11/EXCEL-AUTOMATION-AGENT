import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { SpatialViewerPage } from "./SpatialViewerPage";
import { SpatialGridMap } from "./SpatialGridMap";
import { RegionDetailsPanel } from "./RegionDetailsPanel";
import { SpatialAnomaliesCard } from "./SpatialAnomaliesCard";
import { MOCK_WORKBOOK_DISCOVERY, MOCK_SPATIAL_REGIONS } from "../../mocks/fixtures";
import { colIndexToLetter, toA1, boundingBoxToA1 } from "./spatialUtils";

describe("Spatial Discovery Viewer (F2)", () => {
  describe("SpatialViewerPage Integration", () => {
    it("renders workbook header, KPI metrics, sheet tabs, and grid map", async () => {
      render(
        <MemoryRouter>
          <SpatialViewerPage />
        </MemoryRouter>
      );

      expect(await screen.findByText("Spatial Discovery Viewer")).toBeInTheDocument();
      expect(screen.getByText("[DEV FIXTURE]")).toBeInTheDocument();
      expect(screen.getByText("Detected Regions")).toBeInTheDocument();
      expect(screen.getAllByText("Revenue").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Expenses").length).toBeGreaterThanOrEqual(1);
    });

    it("switches sheets when worksheet tab is clicked", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <SpatialViewerPage />
        </MemoryRouter>
      );

      const expensesTab = await screen.findByRole("button", { name: /Expenses/i });
      await user.click(expensesTab);

      expect(screen.getByText(/\(1 Regions\)/i)).toBeInTheDocument();
    });
  });

  describe("SpatialGridMap Component", () => {
    it("renders coordinate headers, region bounding boxes, and zoom controls", () => {
      const handleSelectRegion = vi.fn();
      const sheet = MOCK_WORKBOOK_DISCOVERY.sheets[0]!;

      render(
        <SpatialGridMap sheet={sheet} selectedRegionId={null} onSelectRegion={handleSelectRegion} />
      );

      // Verify coordinate headers
      expect(screen.getByText("A")).toBeInTheDocument();
      expect(screen.getByText("B")).toBeInTheDocument();
      expect(screen.getByText("1")).toBeInTheDocument();

      // Verify zoom controls
      expect(screen.getByRole("button", { name: "Zoom in" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Zoom out" })).toBeInTheDocument();

      // Verify region rendered
      expect(screen.getByTestId("region-shape-region_rev_01")).toBeInTheDocument();
    });

    it("invokes onSelectRegion callback when a region is clicked", async () => {
      const handleSelectRegion = vi.fn();
      const user = userEvent.setup();
      const sheet = MOCK_WORKBOOK_DISCOVERY.sheets[0]!;

      render(
        <SpatialGridMap sheet={sheet} selectedRegionId={null} onSelectRegion={handleSelectRegion} />
      );

      const regionShape = screen.getByTestId("region-shape-region_rev_01");
      await user.click(regionShape);

      expect(handleSelectRegion).toHaveBeenCalledWith("region_rev_01");
    });
  });

  describe("RegionDetailsPanel Component", () => {
    it("renders unselected empty state when region is null", () => {
      render(<RegionDetailsPanel region={null} onClose={vi.fn()} />);
      expect(
        screen.getByText("Select any region on the grid map to inspect structural metadata.")
      ).toBeInTheDocument();
    });

    it("renders full metadata, clearance, and evidence for selected region", () => {
      const selected = MOCK_SPATIAL_REGIONS[0]!;
      render(<RegionDetailsPanel region={selected} onClose={vi.fn()} />);

      expect(screen.getByTestId("region-details-panel")).toBeInTheDocument();
      expect(screen.getByText("Table: Table_Revenue")).toBeInTheDocument();
      expect(screen.getByText(/Range: B4:G25/)).toBeInTheDocument();
      expect(screen.getByText("Safe for Append")).toBeInTheDocument();
      expect(screen.getByText("DECLARED_OPENXML")).toBeInTheDocument();
    });
  });

  describe("SpatialAnomaliesCard Component", () => {
    it("renders anomalies with severity badges", () => {
      const anomalies = MOCK_WORKBOOK_DISCOVERY.sheets[0]!.anomalies;
      render(<SpatialAnomaliesCard anomalies={anomalies} />);

      expect(screen.getByText("Structural Anomalies Detected (1)")).toBeInTheDocument();
      expect(screen.getByText("ANOM_SPARSE_MARGIN")).toBeInTheDocument();
      expect(screen.getByText("B28")).toBeInTheDocument();
    });

    it("renders null when anomaly collection is empty", () => {
      const { container } = render(<SpatialAnomaliesCard anomalies={[]} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe("spatialUtils coordinate helpers", () => {
    it("converts column indices to column letters correctly", () => {
      expect(colIndexToLetter(1)).toBe("A");
      expect(colIndexToLetter(2)).toBe("B");
      expect(colIndexToLetter(26)).toBe("Z");
      expect(colIndexToLetter(27)).toBe("AA");
      expect(colIndexToLetter(28)).toBe("AB");
      expect(colIndexToLetter(52)).toBe("AZ");
      expect(colIndexToLetter(53)).toBe("BA");
    });

    it("formats cell and bounding box into canonical A1 notation", () => {
      expect(toA1(1, 1)).toBe("A1");
      expect(toA1(10, 5)).toBe("E10");
      expect(boundingBoxToA1({ start_row: 4, start_col: 2, end_row: 25, end_col: 7 })).toBe(
        "B4:G25"
      );
      expect(boundingBoxToA1({ start_row: 5, start_col: 3, end_row: 5, end_col: 3 })).toBe("C5");
    });
  });
});
