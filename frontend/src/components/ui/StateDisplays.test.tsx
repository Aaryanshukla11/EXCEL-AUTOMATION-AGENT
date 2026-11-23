import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoadingState } from "./LoadingState";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { DataTableSkeleton } from "./DataTableSkeleton";

describe("State Display Components", () => {
  describe("LoadingState", () => {
    it("renders with accessible role='status' and aria-busy='true'", () => {
      render(<LoadingState message="Analyzing formula DAG..." />);
      const status = screen.getByRole("status");
      expect(status).toHaveAttribute("aria-busy", "true");
      expect(screen.getByText("Analyzing formula DAG...")).toBeInTheDocument();
    });
  });

  describe("EmptyState", () => {
    it("renders title, description and optional action slot", () => {
      render(
        <EmptyState
          title="No Workbooks Staged"
          description="Upload an Excel file to begin structural discovery."
          action={<button>Upload File</button>}
        />
      );

      expect(screen.getByText("No Workbooks Staged")).toBeInTheDocument();
      expect(
        screen.getByText("Upload an Excel file to begin structural discovery.")
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Upload File" })).toBeInTheDocument();
    });
  });

  describe("ErrorState", () => {
    it("renders error message and triggers onRetry callback", async () => {
      const handleRetry = vi.fn();
      const user = userEvent.setup();

      render(
        <ErrorState
          title="Manifest Parse Failure"
          message="Workbook contains invalid OpenXML parts."
          detail="Error: Zip bomb mitigation triggered at 250MB uncompressed limit"
          onRetry={handleRetry}
        />
      );

      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText("Manifest Parse Failure")).toBeInTheDocument();
      expect(screen.getByText("Workbook contains invalid OpenXML parts.")).toBeInTheDocument();
      expect(screen.getByText(/Zip bomb mitigation/)).toBeInTheDocument();

      const retryBtn = screen.getByRole("button", { name: /Retry/i });
      await user.click(retryBtn);
      expect(handleRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe("DataTableSkeleton", () => {
    it("renders skeleton rows and columns with accessible label", () => {
      render(<DataTableSkeleton rows={4} columns={3} />);
      const skeleton = screen.getByRole("status", { name: "Loading table data" });
      expect(skeleton).toHaveAttribute("aria-busy", "true");
    });
  });
});
