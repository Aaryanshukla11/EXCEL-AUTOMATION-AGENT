import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./Dialog";

describe("Dialog Component", () => {
  it("opens dialog on trigger click and closes on close button", async () => {
    const user = userEvent.setup();

    render(
      <Dialog>
        <DialogTrigger>Open Dialog</DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Mutation</DialogTitle>
            <DialogDescription>Are you sure you want to apply this operation?</DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );

    expect(screen.queryByText("Confirm Mutation")).not.toBeInTheDocument();

    // Click trigger to open
    await user.click(screen.getByText("Open Dialog"));
    expect(screen.getByText("Confirm Mutation")).toBeInTheDocument();
    expect(screen.getByText("Are you sure you want to apply this operation?")).toBeInTheDocument();

    // Click close button
    const closeBtn = screen.getByRole("button", { name: "Close" });
    await user.click(closeBtn);
    expect(screen.queryByText("Confirm Mutation")).not.toBeInTheDocument();
  });
});
