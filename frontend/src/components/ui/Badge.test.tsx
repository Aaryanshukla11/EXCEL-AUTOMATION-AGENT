import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";

describe("Badge Component", () => {
  it("renders with default styling", () => {
    render(<Badge>Active</Badge>);
    const badge = screen.getByText("Active");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("bg-primary");
  });

  it("applies variant classes correctly", () => {
    const { rerender } = render(<Badge variant="success">Passed</Badge>);
    expect(screen.getByText("Passed")).toHaveClass("bg-success");

    rerender(<Badge variant="destructive">Error</Badge>);
    expect(screen.getByText("Error")).toHaveClass("bg-destructive");

    rerender(<Badge variant="warning">Review</Badge>);
    expect(screen.getByText("Review")).toHaveClass("bg-warning");
  });
});
