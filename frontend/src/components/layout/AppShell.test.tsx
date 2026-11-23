import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppShell } from "./AppShell";
import { DEFAULT_CLIENT_CONFIG } from "../../config/clientConfig";

describe("AppShell Component", () => {
  it("renders header, sidebar navigation, breadcrumbs, and status footer", () => {
    render(
      <BrowserRouter>
        <AppShell config={DEFAULT_CLIENT_CONFIG}>
          <div data-testid="main-content">Child View Content</div>
        </AppShell>
      </BrowserRouter>
    );

    // Header branding
    expect(screen.getByText("Autonomous Excel Intelligence")).toBeInTheDocument();
    // Sidebar nav item
    expect(screen.getByText("Overview & Health")).toBeInTheDocument();
    // Breadcrumbs
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    // Main content
    expect(screen.getByTestId("main-content")).toBeInTheDocument();
    // Footer status
    expect(screen.getByText(/Memory Soft Ceiling/)).toBeInTheDocument();
  });

  it("collapses and expands the desktop sidebar on button toggle", async () => {
    const user = userEvent.setup();

    render(
      <BrowserRouter>
        <AppShell config={DEFAULT_CLIENT_CONFIG}>
          <div>Content</div>
        </AppShell>
      </BrowserRouter>
    );

    const collapseBtn = screen.getByRole("button", { name: /Collapse sidebar/i });
    expect(collapseBtn).toBeInTheDocument();

    await user.click(collapseBtn);
    expect(screen.getByRole("button", { name: /Expand sidebar/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Expand sidebar/i }));
    expect(screen.getByRole("button", { name: /Collapse sidebar/i })).toBeInTheDocument();
  });
});
