import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./Tabs";

describe("Tabs Component", () => {
  it("renders tab triggers and displays default active content", () => {
    render(
      <Tabs defaultValue="tables">
        <TabsList>
          <TabsTrigger value="tables">Tables</TabsTrigger>
          <TabsTrigger value="formulas">Formulas</TabsTrigger>
        </TabsList>
        <TabsContent value="tables">Tables Content View</TabsContent>
        <TabsContent value="formulas">Formulas Content View</TabsContent>
      </Tabs>
    );

    expect(screen.getByText("Tables Content View")).toBeInTheDocument();
    expect(screen.queryByText("Formulas Content View")).not.toBeInTheDocument();
  });

  it("switches content when another tab trigger is clicked", async () => {
    const user = userEvent.setup();

    render(
      <Tabs defaultValue="tables">
        <TabsList>
          <TabsTrigger value="tables">Tables</TabsTrigger>
          <TabsTrigger value="formulas">Formulas</TabsTrigger>
        </TabsList>
        <TabsContent value="tables">Tables Content View</TabsContent>
        <TabsContent value="formulas">Formulas Content View</TabsContent>
      </Tabs>
    );

    await user.click(screen.getByRole("tab", { name: "Formulas" }));
    expect(screen.getByText("Formulas Content View")).toBeInTheDocument();
    expect(screen.queryByText("Tables Content View")).not.toBeInTheDocument();
  });
});
