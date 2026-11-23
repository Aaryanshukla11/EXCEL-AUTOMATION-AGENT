import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApprovalConsolePage } from "./ApprovalConsolePage";

describe("Human-in-the-Loop Approval Console Integration (F4)", () => {
  it("renders page header, simulated disclaimer alert, KPI cards, and queue table", async () => {
    render(
      <MemoryRouter>
        <ApprovalConsolePage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Human-in-the-Loop Approval Console")).toBeInTheDocument();
    expect(
      screen.getByText("Simulated Approval & Risk Governance Environment")
    ).toBeInTheDocument();
    expect(screen.getByText("Pending Human Review")).toBeInTheDocument();
    expect(screen.getByText("High / Critical Risk Items")).toBeInTheDocument();
    expect(screen.getAllByText("REQ-001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Blank-Field Entity Code Enrichment").length).toBeGreaterThan(0);
    expect(screen.getByTestId("approval-detail-panel")).toBeInTheDocument();
  });

  it("filters requests by state tab and search input", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ApprovalConsolePage />
      </MemoryRouter>
    );

    await screen.findAllByText("REQ-001");

    // Click 'Approved' tab
    const approvedTab = screen.getByRole("button", { name: "Approved" });
    await user.click(approvedTab);

    // REQ-005 is APPROVED in fixtures
    expect(screen.getByText("REQ-005")).toBeInTheDocument();
    expect(screen.queryByTestId("approval-row-REQ-001")).not.toBeInTheDocument();

    // Reset to 'All Requests'
    const allTab = screen.getByRole("button", { name: /All Requests/i });
    await user.click(allTab);
    expect(screen.getByTestId("approval-row-REQ-001")).toBeInTheDocument();

    // Type in search
    const searchInput = screen.getByPlaceholderText(/Search by request ID/i);
    await user.type(searchInput, "Overwrite");
    expect(screen.getByText("REQ-002")).toBeInTheDocument();
    expect(screen.queryByTestId("approval-row-REQ-001")).not.toBeInTheDocument();
  });

  it("selects request and displays risk assessment and proposed operations", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ApprovalConsolePage />
      </MemoryRouter>
    );

    const row = await screen.findByTestId("approval-row-REQ-002");
    await user.click(row);

    expect(screen.getByTestId("approval-detail-panel")).toBeInTheDocument();
    expect(screen.getAllByText("Fiscal Year Revenue Cell Overwrite").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Populated Cell Overwrite").length).toBeGreaterThan(0);
    expect(screen.getByText(/Prior value '\$1,240,500' will be overwritten/)).toBeInTheDocument();
    expect(screen.getByText("$1,248,750")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve Proposal/i })).toBeInTheDocument();
  });

  it("approves pending request via action dialog and updates UI state", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ApprovalConsolePage />
      </MemoryRouter>
    );

    const row = await screen.findByTestId("approval-row-REQ-001");
    await user.click(row);

    const approveBtn = screen.getByRole("button", { name: /Approve Proposal/i });
    await user.click(approveBtn);

    // Dialog opens
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Confirm Operation Approval" })).toBeInTheDocument();

    // Submit approval
    const confirmBtn = screen.getByRole("button", { name: "Confirm Operation Approval" });
    await user.click(confirmBtn);

    // Dialog closes and status updates to APPROVED
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(await screen.findByText("Decision Recorded:")).toBeInTheDocument();
  });

  it("validates mandatory rationale when rejecting a proposal", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ApprovalConsolePage />
      </MemoryRouter>
    );

    const row = await screen.findByTestId("approval-row-REQ-003");
    await user.click(row);

    const rejectBtn = screen.getByRole("button", { name: /Reject Proposal/i });
    await user.click(rejectBtn);

    expect(
      screen.getByRole("heading", { name: "Confirm Operation Rejection" })
    ).toBeInTheDocument();

    // Attempting submit without rationale fails validation
    const submitBtn = screen.getByRole("button", { name: "Confirm Operation Rejection" });
    await user.click(submitBtn);

    expect(
      screen.getByText("Mandatory decision rationale of at least 5 characters is required.")
    ).toBeInTheDocument();

    // Enter valid rationale
    const textarea = screen.getByLabelText("Decision rationale");
    await user.type(textarea, "Confidence score is too low for automated mapping.");
    await user.click(submitBtn);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      (await screen.findAllByText(/Confidence score is too low/)).length
    ).toBeGreaterThanOrEqual(1);
  });
});
