import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ExecutionMonitorPage } from "./ExecutionMonitorPage";

describe("Execution & WAL Monitor Integration (F5)", () => {
  it("renders page header, simulation disclaimer, and KPI cards", async () => {
    render(<ExecutionMonitorPage />);

    expect(await screen.findByText("Execution & WAL Durability Monitor")).toBeInTheDocument();
    expect(screen.getByText("Simulated Execution & Durability Environment")).toBeInTheDocument();
    expect(screen.getByText("Total Pipelines")).toBeInTheDocument();
    expect(screen.getByText("Committed (WAL)")).toBeInTheDocument();
  });

  it("displays execution jobs in queue and selects a job", async () => {
    render(<ExecutionMonitorPage />);

    expect(await screen.findByText("EXEC-JOB-101")).toBeInTheDocument();
    expect(screen.getByText("master_financial_consolidation.xlsx")).toBeInTheDocument();
    expect(screen.getByTestId("wal-pipeline-timeline")).toBeInTheDocument();
  });

  it("switches to rolled back job and shows rollback reason", async () => {
    const user = userEvent.setup();
    render(<ExecutionMonitorPage />);

    const job2 = await screen.findByTestId("execution-job-EXEC-JOB-102");
    await user.click(job2);

    expect(await screen.findByText("Rollback Triggered")).toBeInTheDocument();
    expect(
      screen.getByText(/Simulated I\/O lock collision during atomic replace/)
    ).toBeInTheDocument();
  });

  it("renders post-flight verification telemetry card with pre/post hashes", async () => {
    render(<ExecutionMonitorPage />);

    expect(await screen.findByTestId("post-flight-verification-card")).toBeInTheDocument();
    expect(screen.getByText("HASH VERIFIED")).toBeInTheDocument();
    expect(screen.getByText("1,420")).toBeInTheDocument();
  });
});
