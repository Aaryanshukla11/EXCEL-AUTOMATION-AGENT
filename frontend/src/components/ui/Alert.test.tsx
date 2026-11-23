import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Alert, AlertDescription, AlertTitle } from "./Alert";

describe("Alert Component", () => {
  it("renders with role='alert' and displays title and description", () => {
    render(
      <Alert variant="warning">
        <AlertTitle>Anomaly Detected</AlertTitle>
        <AlertDescription>
          Formula references a cell outside detected table boundaries.
        </AlertDescription>
      </Alert>
    );

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText("Anomaly Detected")).toBeInTheDocument();
    expect(
      screen.getByText("Formula references a cell outside detected table boundaries.")
    ).toBeInTheDocument();
  });

  it("applies variant styling classes", () => {
    const { rerender } = render(<Alert variant="destructive">Critical Error</Alert>);
    expect(screen.getByRole("alert")).toHaveClass("border-destructive/50");

    rerender(<Alert variant="success">Operation Verified</Alert>);
    expect(screen.getByRole("alert")).toHaveClass("border-success/50");
  });
});
