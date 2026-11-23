import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";
import { DEFAULT_CLIENT_CONFIG } from "../../config/clientConfig";

describe("Client Customization & Settings Panel (F5)", () => {
  it("renders page header, tabs, and live theme customizer controls", () => {
    const onUpdate = vi.fn();
    render(<SettingsPage config={DEFAULT_CLIENT_CONFIG} onUpdateConfig={onUpdate} />);

    expect(screen.getByText("Client Customization & Settings Panel")).toBeInTheDocument();
    expect(screen.getByText("TIER 1 ZERO-CODE ENGINE")).toBeInTheDocument();
    expect(screen.getByText("Theme Tokens & Color Engine")).toBeInTheDocument();
    expect(screen.getByText("Live Visual Preview")).toBeInTheDocument();
  });

  it("switches to branding tab and updates application title", async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn();
    render(<SettingsPage config={DEFAULT_CLIENT_CONFIG} onUpdateConfig={onUpdate} />);

    const brandingTab = screen.getByRole("button", { name: /Branding & Identity/i });
    await user.click(brandingTab);

    expect(screen.getByText("Enterprise Branding")).toBeInTheDocument();
    const titleInput = screen.getByDisplayValue("Autonomous Excel Intelligence");
    await user.clear(titleInput);
    await user.type(titleInput, "Acme Intelligence Suite");

    const applyBtn = screen.getByRole("button", { name: /Apply Changes/i });
    await user.click(applyBtn);

    expect(onUpdate).toHaveBeenCalledWith(
      expect.objectContaining({
        branding: expect.objectContaining({ appTitle: "Acme Intelligence Suite" }),
      })
    );
  });

  it("switches to terminology overrides tab and displays custom domain inputs", async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn();
    render(<SettingsPage config={DEFAULT_CLIENT_CONFIG} onUpdateConfig={onUpdate} />);

    const termTab = screen.getByRole("button", { name: /Terminology Overrides/i });
    await user.click(termTab);

    expect(screen.getByText("Domain Terminology Overrides")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Workbook")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Defect")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Approval")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Write-Ahead Log")).toBeInTheDocument();
  });

  it("resets settings to defaults when Reset Defaults button is clicked", async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn();
    const modified = {
      ...DEFAULT_CLIENT_CONFIG,
      branding: { ...DEFAULT_CLIENT_CONFIG.branding, appTitle: "Custom Title" },
    };

    render(<SettingsPage config={modified} onUpdateConfig={onUpdate} />);

    const resetBtn = screen.getByRole("button", { name: /Reset Defaults/i });
    await user.click(resetBtn);

    expect(onUpdate).toHaveBeenCalledWith(DEFAULT_CLIENT_CONFIG);
  });
});
