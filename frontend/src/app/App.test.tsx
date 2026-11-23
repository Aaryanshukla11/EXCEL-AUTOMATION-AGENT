import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { App } from "./App";

describe("Application Root & Shell Integration (F1)", () => {
  it("renders main application header, branding, and default landing page", () => {
    render(<App />);
    expect(screen.getAllByText("Autonomous Excel Intelligence")[0]).toBeInTheDocument();
    expect(screen.getByText("Overview & Health")).toBeInTheDocument();
    expect(screen.getByText("Milestone F1 Shell Active")).toBeInTheDocument();
  });

  it("toggles color theme between light and dark", async () => {
    const user = userEvent.setup();
    render(<App />);

    const themeToggleBtn = screen.getByRole("button", { name: "Toggle theme" });
    expect(themeToggleBtn).toBeInTheDocument();

    await user.click(themeToggleBtn);
    expect(document.documentElement.classList.contains("dark")).toBe(true);

    await user.click(themeToggleBtn);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("opens notification dialog from header icon button", async () => {
    const user = userEvent.setup();
    render(<App />);

    const notifyBtn = screen.getByRole("button", { name: "View notifications" });
    await user.click(notifyBtn);

    expect(screen.getByText("Platform Notifications")).toBeInTheDocument();
  });

  it("navigates to staging route from quick action card", async () => {
    const user = userEvent.setup();
    render(<App />);

    const inspectButtons = screen.getAllByRole("button", { name: /Inspect/i });
    expect(inspectButtons.length).toBeGreaterThan(0);

    await user.click(inspectButtons[0]!);
    expect(screen.getByText("Workbook Management & Staging")).toBeInTheDocument();
  });
});
