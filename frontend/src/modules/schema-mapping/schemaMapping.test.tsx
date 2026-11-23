import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { SchemaMappingPage } from "./SchemaMappingPage";
import { CandidateCard } from "./CandidateCard";
import { evaluateConflicts } from "./mappingUtils";
import { MOCK_TARGET_MASTER_SCHEMAS, MOCK_MAPPING_CANDIDATES } from "../../mocks/fixtures";
import type { DraftColumnMapping } from "../../contracts/mapping";

describe("Schema Mapping Studio (F3)", () => {
  describe("SchemaMappingPage Integration", () => {
    it("renders page header, unapproved draft mode disclaimer, and workspace", async () => {
      render(
        <MemoryRouter>
          <SchemaMappingPage />
        </MemoryRouter>
      );

      expect(await screen.findByText("Schema Mapping Studio")).toBeInTheDocument();
      expect(screen.getByText("Draft Mapping Mode Active")).toBeInTheDocument();
      expect(
        screen.getByText(/Field associations configured here are non-binding drafts/)
      ).toBeInTheDocument();
      expect(screen.getByText("Source Column (Discovered)")).toBeInTheDocument();
      expect(screen.getByText("Target Column (Master Schema)")).toBeInTheDocument();
    });

    it("displays discovered source columns from active region", async () => {
      render(
        <MemoryRouter>
          <SchemaMappingPage />
        </MemoryRouter>
      );

      expect(await screen.findByText("Region_Code")).toBeInTheDocument();
      expect(screen.getByText("Division")).toBeInTheDocument();
      expect(screen.getByText("FY25_Budget")).toBeInTheDocument();
      expect(screen.getByText("FY25_Actual")).toBeInTheDocument();
    });

    it("opens detail panel on source column click and displays recommendations", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <SchemaMappingPage />
        </MemoryRouter>
      );

      const regionCodeRow = await screen.findByTestId("mapping-row-2");
      await user.click(regionCodeRow);

      expect(screen.getByTestId("mapping-detail-panel")).toBeInTheDocument();
      expect(screen.getByText("Mapping Recommendations (1)")).toBeInTheDocument();
      expect(screen.getByText(/Semantic Category/i)).toBeInTheDocument();
      expect(
        screen.getByText(/High semantic overlap with standard entity ISO/i)
      ).toBeInTheDocument();
    });

    it("creates draft when 'Use Recommendation' is clicked", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <SchemaMappingPage />
        </MemoryRouter>
      );

      const regionCodeRow = await screen.findByTestId("mapping-row-2");
      await user.click(regionCodeRow);

      const applyBtn = screen.getByRole("button", { name: /Use Recommendation/i });
      await user.click(applyBtn);

      expect(screen.getAllByText(/Drafted/i).length).toBeGreaterThan(0);
    });

    it("auto-applies recommendations when toolbar button is clicked", async () => {
      const user = userEvent.setup();
      render(
        <MemoryRouter>
          <SchemaMappingPage />
        </MemoryRouter>
      );

      await screen.findByText("Schema Mapping Studio");
      const autoBtn = screen.getByRole("button", { name: /Apply Recommendations/i });
      await user.click(autoBtn);

      expect(screen.getByText(/Drafted \(6\)/i)).toBeInTheDocument();
    });
  });

  describe("Conflict Detection Logic (Unit)", () => {
    it("detects conflicting assignments when multiple source columns map to the same one_to_one target", () => {
      const targetColumns = MOCK_TARGET_MASTER_SCHEMAS[0]!.columns;
      const drafts: DraftColumnMapping[] = [
        {
          id: "d1",
          source_column_index: 2,
          target_column_index: 2, // Entity_Code
          cardinality: "one_to_one",
          status: "draft",
          is_conflict: false,
        },
        {
          id: "d2",
          source_column_index: 3,
          target_column_index: 2, // Conflicting assignment to Entity_Code
          cardinality: "one_to_one",
          status: "draft",
          is_conflict: false,
        },
      ];

      const evaluated = evaluateConflicts(drafts, targetColumns);
      expect(evaluated[0]?.is_conflict).toBe(true);
      expect(evaluated[1]?.is_conflict).toBe(true);
      expect(evaluated[0]?.conflict_reason).toContain("One-to-one constraint violation");
    });

    it("clears conflict when conflicting assignment is removed", () => {
      const targetColumns = MOCK_TARGET_MASTER_SCHEMAS[0]!.columns;
      const drafts: DraftColumnMapping[] = [
        {
          id: "d1",
          source_column_index: 2,
          target_column_index: 2,
          cardinality: "one_to_one",
          status: "draft",
          is_conflict: false,
        },
      ];

      const evaluated = evaluateConflicts(drafts, targetColumns);
      expect(evaluated[0]?.is_conflict).toBe(false);
      expect(evaluated[0]?.conflict_reason).toBeUndefined();
    });
  });

  describe("CandidateCard & Explainability", () => {
    it("renders candidate with confidence percentage and explanation evidence", () => {
      const cand = MOCK_MAPPING_CANDIDATES[0]!;
      const targetCol = MOCK_TARGET_MASTER_SCHEMAS[0]!.columns[1]!;

      render(
        <CandidateCard
          candidate={cand}
          targetColumn={targetCol}
          isApplied={false}
          onApply={vi.fn()}
        />
      );

      expect(screen.getByText("Entity_Code")).toBeInTheDocument();
      expect(screen.getByText("Semantic Category")).toBeInTheDocument();
      expect(screen.getByText("92%")).toBeInTheDocument();
      expect(screen.getByText(cand.evidence)).toBeInTheDocument();
    });
  });
});
