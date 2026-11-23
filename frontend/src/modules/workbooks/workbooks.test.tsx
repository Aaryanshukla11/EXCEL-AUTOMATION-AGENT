import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { WorkbookDropzone } from "./WorkbookDropzone";
import { StagingQueue } from "./StagingQueue";
import { WorkbookInventory } from "./WorkbookInventory";
import { WorkbookManagementPage } from "./WorkbookManagementPage";
import type { StagedWorkbook, WorkbookInventoryItem } from "./workbookTypes";
import { formatBytes } from "./workbookUtils";

describe("Workbook Management & Staging (F2)", () => {
  describe("WorkbookDropzone", () => {
    it("accepts valid .xlsx files through file input", () => {
      const handleFiles = vi.fn();
      render(<WorkbookDropzone onFilesSelected={handleFiles} />);

      const input = screen.getByTestId("workbook-file-input") as HTMLInputElement;
      const file = new File(["dummy content"], "monthly_report.xlsx", {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      fireEvent.change(input, { target: { files: [file] } });
      expect(handleFiles).toHaveBeenCalledTimes(1);
    });

    it("triggers file callback on drag and drop", () => {
      const handleFiles = vi.fn();
      render(<WorkbookDropzone onFilesSelected={handleFiles} />);

      const dropArea = screen.getByText(/Select or drag Excel workbooks here/i);
      const file = new File(["dummy"], "budget_fy25.xlsm");

      fireEvent.drop(dropArea, {
        dataTransfer: { files: [file] },
      });

      expect(handleFiles).toHaveBeenCalledTimes(1);
    });
  });

  describe("StagingQueue", () => {
    const mockItems: StagedWorkbook[] = [
      {
        id: "staged_1",
        file: new File(["data"], "sales_q1.xlsx"),
        name: "sales_q1.xlsx",
        sizeBytes: 1024 * 500, // 500 KiB
        format: "xlsx",
        lastModified: 1700000000000,
        validationStatus: "valid",
        validationErrors: [],
        discoveryStatus: "not_started",
        stagedAt: "2026-11-23T04:00:00Z",
      },
      {
        id: "staged_2",
        file: new File(["data"], "notes.txt"),
        name: "notes.txt",
        sizeBytes: 1024 * 10,
        format: "unsupported",
        lastModified: 1700000000000,
        validationStatus: "unsupported_format",
        validationErrors: [
          "Unsupported format. Only OpenXML formats (.xlsx, .xlsm) are supported.",
        ],
        discoveryStatus: "not_started",
        stagedAt: "2026-11-23T04:01:00Z",
      },
      {
        id: "staged_3",
        file: new File(["data"], "sales_q1_dup.xlsx"),
        name: "sales_q1_dup.xlsx",
        sizeBytes: 1024 * 500,
        format: "xlsx",
        lastModified: 1700000000000,
        validationStatus: "duplicate",
        validationErrors: ["Workbook is already present in the staging queue."],
        discoveryStatus: "not_started",
        stagedAt: "2026-11-23T04:02:00Z",
      },
    ];

    it("renders valid, duplicate, and rejected items with appropriate badges", () => {
      render(
        <StagingQueue items={mockItems} onRemove={vi.fn()} onClear={vi.fn()} onInspect={vi.fn()} />
      );

      expect(screen.getByText("sales_q1.xlsx")).toBeInTheDocument();
      expect(screen.getByText("notes.txt")).toBeInTheDocument();
      expect(screen.getAllByText(/Ready/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Rejected/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/Duplicate/i).length).toBeGreaterThanOrEqual(1);
    });

    it("triggers remove and clear callbacks", async () => {
      const handleRemove = vi.fn();
      const handleClear = vi.fn();
      const user = userEvent.setup();

      render(
        <StagingQueue
          items={mockItems}
          onRemove={handleRemove}
          onClear={handleClear}
          onInspect={vi.fn()}
        />
      );

      const clearBtn = screen.getByRole("button", { name: /Clear Queue/i });
      await user.click(clearBtn);
      expect(handleClear).toHaveBeenCalledTimes(1);

      const removeBtn = screen.getByRole("button", { name: /Remove sales_q1\.xlsx/i });
      await user.click(removeBtn);
      expect(handleRemove).toHaveBeenCalledWith("staged_1");
    });
  });

  describe("WorkbookInventory", () => {
    const mockInventory: WorkbookInventoryItem[] = [
      {
        id: "wb_1",
        name: "balance_sheet_2025.xlsx",
        format: "xlsx",
        sizeBytes: 2048000,
        sheetCount: 3,
        discoveryStatus: "completed",
        source: "backend_fixture",
        lastActivity: "2026-11-23T04:00:00Z",
      },
      {
        id: "wb_2",
        name: "cashflow_model.xlsm",
        format: "xlsm",
        sizeBytes: 1048576,
        sheetCount: 1,
        discoveryStatus: "not_started",
        source: "memory_staged",
        lastActivity: "2026-11-23T04:05:00Z",
      },
    ];

    it("filters inventory items based on search query", async () => {
      const user = userEvent.setup();
      render(<WorkbookInventory items={mockInventory} onSelectWorkbook={vi.fn()} />);

      expect(screen.getByText("balance_sheet_2025.xlsx")).toBeInTheDocument();
      expect(screen.getByText("cashflow_model.xlsm")).toBeInTheDocument();

      const searchInput = screen.getByPlaceholderText(/Search workbooks\.\.\./i);
      await user.type(searchInput, "balance");

      expect(screen.getByText("balance_sheet_2025.xlsx")).toBeInTheDocument();
      expect(screen.queryByText("cashflow_model.xlsm")).not.toBeInTheDocument();
    });
  });

  describe("WorkbookManagementPage Integration", () => {
    it("renders page header, in-memory disclaimer alert, and inventory", () => {
      render(
        <MemoryRouter>
          <WorkbookManagementPage />
        </MemoryRouter>
      );

      expect(screen.getByText("Workbook Management & Staging")).toBeInTheDocument();
      expect(screen.getByText("In-Memory Staging Mode Active")).toBeInTheDocument();
      expect(screen.getByText("Workbook Inventory")).toBeInTheDocument();
      expect(screen.getByText("financial_model_q4.xlsx")).toBeInTheDocument();
    });
  });

  describe("formatBytes helper", () => {
    it("formats byte values into human-readable units", () => {
      expect(formatBytes(0)).toBe("0 Bytes");
      expect(formatBytes(1024)).toBe("1 KiB");
      expect(formatBytes(1048576)).toBe("1 MiB");
      expect(formatBytes(1073741824)).toBe("1 GiB");
    });
  });
});
