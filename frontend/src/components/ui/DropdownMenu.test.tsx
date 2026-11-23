import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./DropdownMenu";

describe("DropdownMenu Component", () => {
  it("opens dropdown and selects an item", async () => {
    const handleSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <DropdownMenu>
        <DropdownMenuTrigger>Actions</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onSelect={handleSelect}>Export CSV</DropdownMenuItem>
          <DropdownMenuItem>View Lineage</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );

    expect(screen.queryByText("Export CSV")).not.toBeInTheDocument();

    await user.click(screen.getByText("Actions"));
    expect(screen.getByText("Export CSV")).toBeInTheDocument();

    await user.click(screen.getByText("Export CSV"));
    expect(handleSelect).toHaveBeenCalledTimes(1);
  });
});
