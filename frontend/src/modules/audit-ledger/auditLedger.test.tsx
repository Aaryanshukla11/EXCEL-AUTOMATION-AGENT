import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AuditLedgerPage } from "./AuditLedgerPage";

describe("Audit Ledger & Compliance Explorer Integration (F5)", () => {
  it("renders page header, immutable notice, and verification banner", async () => {
    render(<AuditLedgerPage />);

    expect(await screen.findByText("Audit Ledger & Lineage Explorer")).toBeInTheDocument();
    expect(screen.getByText("Immutable Cryptographic Audit Trail")).toBeInTheDocument();
    expect(screen.getByTestId("audit-chain-banner")).toBeInTheDocument();
    expect(screen.getByText("Cryptographic SHA-256 Hash-Chain Intact")).toBeInTheDocument();
  });

  it("renders audit blocks table with truncated hashes and status pills", async () => {
    render(<AuditLedgerPage />);

    expect(await screen.findByTestId("audit-row-1")).toBeInTheDocument();
    expect(screen.getByText("system_genesis")).toBeInTheDocument();
    expect(screen.getByText("GENESIS_INITIALIZATION")).toBeInTheDocument();
    expect(screen.getByTestId("audit-row-6")).toBeInTheDocument();
    expect(screen.getAllByText("wal_execution_engine").length).toBeGreaterThan(0);
  });

  it("opens detail modal on row click displaying complete hashes and payload", async () => {
    const user = userEvent.setup();
    render(<AuditLedgerPage />);

    const row = await screen.findByTestId("audit-row-5");
    await user.click(row);

    expect(await screen.findByText("Audit Block #5 Details")).toBeInTheDocument();
    expect(screen.getByText("Block SHA-256 Hash")).toBeInTheDocument();
    expect(screen.getAllByText("lead_operator@corp.internal").length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Approved REQ-001 \(Blank-Field Entity Code Enrichment\)/)
    ).toBeInTheDocument();
  });
});
