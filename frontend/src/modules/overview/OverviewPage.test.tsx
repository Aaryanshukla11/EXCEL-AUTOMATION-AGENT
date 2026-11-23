import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { OverviewPage } from "./OverviewPage";
import { DEFAULT_CLIENT_CONFIG, type ClientConfig } from "../../config/clientConfig";

describe("OverviewPage Component", () => {
  it("renders status banner, quick launch cards, and architecture telemetry", () => {
    render(
      <MemoryRouter>
        <OverviewPage config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(screen.getByText("Process Quota & Telemetry Baseline")).toBeInTheDocument();
    expect(screen.getByText("235 MiB (Spill Trigger)")).toBeInTheDocument();
    expect(screen.getByText("250 MiB (Process Abort)")).toBeInTheDocument();
    expect(screen.getByText("Active Client Configuration")).toBeInTheDocument();
    expect(screen.getByText("Frontend Delivery Roadmap Alignment")).toBeInTheDocument();
  });

  it("reflects customized terminology in card headers", () => {
    const customConfig: ClientConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      terminology: {
        ...DEFAULT_CLIENT_CONFIG.terminology,
        workbook: "Financial Dossier",
        defect: "Data Discrepancy",
      },
    };

    render(
      <MemoryRouter>
        <OverviewPage config={customConfig} />
      </MemoryRouter>
    );

    expect(screen.getByText("Financial Dossier Staging")).toBeInTheDocument();
    expect(screen.getByText("Data Discrepancy Audit")).toBeInTheDocument();
  });
});
