import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "./AppRoutes";
import { DEFAULT_CLIENT_CONFIG } from "../config/clientConfig";

describe("AppRoutes & Navigation Routing (F0–F5 All 9 Routes)", () => {
  it("redirects root path '/' to configured defaultRoute", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(
      screen.getByText(
        "Enterprise Spreadsheet Ingestion, Quality Audit & Deterministic Execution Shell"
      )
    ).toBeInTheDocument();
  });

  it("renders 404 NotFoundPage on unknown route path", () => {
    render(
      <MemoryRouter initialEntries={["/unknown-route-12345"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(screen.getByText("404 — Page Not Found")).toBeInTheDocument();
    expect(
      screen.getByText(/The requested route '\/unknown-route-12345' does not exist/)
    ).toBeInTheDocument();
  });

  it("renders OverviewPage on '/overview'", async () => {
    render(
      <MemoryRouter initialEntries={["/overview"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Autonomous Excel Intelligence")).toBeInTheDocument();
  });

  it("renders WorkbookManagementPage on '/staging'", async () => {
    render(
      <MemoryRouter initialEntries={["/staging"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Workbook Management & Staging")).toBeInTheDocument();
  });

  it("renders SpatialViewerPage on '/spatial-viewer'", async () => {
    render(
      <MemoryRouter initialEntries={["/spatial-viewer"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Spatial Discovery Viewer")).toBeInTheDocument();
  });

  it("renders SchemaMappingPage on '/schema-studio'", async () => {
    render(
      <MemoryRouter initialEntries={["/schema-studio"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Schema Mapping Studio")).toBeInTheDocument();
  });

  it("renders DataQualityPage on '/quality-audit'", async () => {
    render(
      <MemoryRouter initialEntries={["/quality-audit"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Data Quality & Audit Console")).toBeInTheDocument();
  });

  it("renders ApprovalConsolePage on '/approval-console'", async () => {
    render(
      <MemoryRouter initialEntries={["/approval-console"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Human-in-the-Loop Approval Console")).toBeInTheDocument();
  });

  it("renders ExecutionMonitorPage on '/execution-monitor'", async () => {
    render(
      <MemoryRouter initialEntries={["/execution-monitor"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Execution & WAL Durability Monitor")).toBeInTheDocument();
  });

  it("renders AuditLedgerPage on '/audit-ledger'", async () => {
    render(
      <MemoryRouter initialEntries={["/audit-ledger"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Audit Ledger & Lineage Explorer")).toBeInTheDocument();
  });

  it("renders SettingsPage on '/settings'", async () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(await screen.findByText("Client Customization & Settings Panel")).toBeInTheDocument();
  });

  it("navigates back to overview when action button is clicked on 404 page", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/non-existent"]}>
        <AppRoutes config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    const backBtn = screen.getByRole("button", { name: "Return to Overview" });
    await user.click(backBtn);

    expect(
      await screen.findByText(
        "Enterprise Spreadsheet Ingestion, Quality Audit & Deterministic Execution Shell"
      )
    ).toBeInTheDocument();
  });
});
