import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./Card";

describe("Card Component", () => {
  it("renders all card subcomponents with structured content", () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Workbook Ingestion</CardTitle>
          <CardDescription>Upload an OpenXML workbook for inspection</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Main content area</p>
        </CardContent>
        <CardFooter>
          <button>Submit</button>
        </CardFooter>
      </Card>
    );

    expect(screen.getByText("Workbook Ingestion")).toBeInTheDocument();
    expect(screen.getByText("Upload an OpenXML workbook for inspection")).toBeInTheDocument();
    expect(screen.getByText("Main content area")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit" })).toBeInTheDocument();
  });
});
