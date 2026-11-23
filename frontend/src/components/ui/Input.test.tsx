import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Input } from "./Input";

describe("Input Component", () => {
  it("renders input element and accepts user typing", async () => {
    const user = userEvent.setup();
    render(<Input placeholder="Enter workbook name" aria-label="Workbook name" />);

    const input = screen.getByPlaceholderText("Enter workbook name");
    expect(input).toBeInTheDocument();

    await user.type(input, "Q4_Report.xlsx");
    expect(input).toHaveValue("Q4_Report.xlsx");
  });

  it("sets aria-invalid and displays helper error message when error is true", () => {
    render(
      <Input id="sheet-name" error helperText="Sheet name cannot contain invalid characters" />
    );

    const input = screen.getByRole("textbox");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Sheet name cannot contain invalid characters")).toBeInTheDocument();
  });

  it("respects disabled attribute", () => {
    render(<Input disabled placeholder="Locked input" />);
    expect(screen.getByPlaceholderText("Locked input")).toBeDisabled();
  });
});
