import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./Tooltip";

describe("Tooltip Component", () => {
  it("renders trigger and displays tooltip content on focus/hover", async () => {
    const user = userEvent.setup();

    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip>
          <TooltipTrigger asChild>
            <button>Hover Target</button>
          </TooltipTrigger>
          <TooltipContent>Helpful context tooltip</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );

    const trigger = screen.getByRole("button", { name: "Hover Target" });
    expect(trigger).toBeInTheDocument();

    await user.hover(trigger);
    expect(await screen.findByText("Helpful context tooltip")).toBeInTheDocument();
  });
});
