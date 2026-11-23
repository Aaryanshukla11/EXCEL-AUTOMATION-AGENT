import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Breadcrumbs } from "./Breadcrumbs";
import { DEFAULT_CLIENT_CONFIG } from "../../config/clientConfig";

describe("Breadcrumbs Component", () => {
  it("renders simple Overview anchor on home route", () => {
    render(
      <MemoryRouter initialEntries={["/overview"]}>
        <Breadcrumbs config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(screen.getByText("Overview")).toBeInTheDocument();
  });

  it("generates multi-level breadcrumb path on nested or sub-routes with terminology", () => {
    render(
      <MemoryRouter initialEntries={["/staging"]}>
        <Breadcrumbs config={DEFAULT_CLIENT_CONFIG} />
      </MemoryRouter>
    );

    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Workbook Staging")).toBeInTheDocument();
  });
});
