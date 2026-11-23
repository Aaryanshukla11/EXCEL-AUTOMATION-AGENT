import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";

describe("Button Component", () => {
  it("renders with default styling and children", () => {
    render(<Button>Click Me</Button>);
    const button = screen.getByRole("button", { name: "Click Me" });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it("handles click events", async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(<Button onClick={handleClick}>Trigger Action</Button>);
    await user.click(screen.getByRole("button", { name: "Trigger Action" }));

    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("disables interaction and displays loader when isLoading is true", async () => {
    const handleClick = vi.fn();
    const user = userEvent.setup();

    render(
      <Button isLoading onClick={handleClick}>
        Saving
      </Button>
    );

    const button = screen.getByRole("button", { name: "Saving" });
    expect(button).toBeDisabled();
    await user.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it("applies variant classes correctly", () => {
    const { rerender } = render(<Button variant="destructive">Delete</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-destructive");

    rerender(<Button variant="outline">Cancel</Button>);
    expect(screen.getByRole("button")).toHaveClass("border-input");
  });
});
