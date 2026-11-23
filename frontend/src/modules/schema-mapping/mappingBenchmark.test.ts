import { describe, expect, it } from "vitest";
import type { DraftColumnMapping, TargetMasterColumn } from "../../contracts/mapping";
import { evaluateConflicts, buildMappingPairs } from "./mappingUtils";
import type { ColumnMetadata } from "../../contracts/discovery";

describe("Schema Mapping Studio Large-Scale Benchmark (F3)", () => {
  it("processes and evaluates conflicts for 1,000 mapping drafts under 50 milliseconds", () => {
    const targetColumns: TargetMasterColumn[] = Array.from({ length: 500 }).map((_, i) => ({
      index: i + 1,
      name: `Target_Column_${i + 1}`,
      expected_type: i % 2 === 0 ? "STRING" : "DECIMAL",
      required: i % 3 === 0,
    }));

    const drafts: DraftColumnMapping[] = Array.from({ length: 1000 }).map((_, i) => ({
      id: `draft_${i}`,
      source_column_index: i + 1,
      target_column_index: (i % 500) + 1, // Intentional collisions for 500 columns
      cardinality: "one_to_one",
      status: "draft",
      is_conflict: false,
    }));

    const startTime = performance.now();
    const evaluated = evaluateConflicts(drafts, targetColumns);
    const duration = performance.now() - startTime;

    expect(evaluated).toHaveLength(1000);
    expect(evaluated.filter((d) => d.is_conflict).length).toBe(1000);
    expect(duration).toBeLessThan(50);
  });

  it("builds mapping pairs across 500 candidates under 50 milliseconds", () => {
    const sourceColumns: ColumnMetadata[] = Array.from({ length: 500 }).map((_, i) => ({
      index: i + 1,
      header_name: `Source_Col_${i + 1}`,
      inferred_type: "DECIMAL",
      type_confidence: 0.95,
      nullable: false,
    }));

    const targetColumns: TargetMasterColumn[] = Array.from({ length: 100 }).map((_, i) => ({
      index: i + 1,
      name: `Target_Col_${i + 1}`,
      expected_type: "DECIMAL",
      required: true,
    }));

    const candidates = Array.from({ length: 500 }).map((_, i) => ({
      candidate_id: `cand_${i}`,
      source_column_index: i + 1,
      target_column_index: (i % 100) + 1,
      match_type: "exact_header" as const,
      confidence_score: 0.95,
      evidence: "Exact token match",
      is_competing: false,
    }));

    const startTime = performance.now();
    const pairs = buildMappingPairs(sourceColumns, targetColumns, candidates, []);
    const duration = performance.now() - startTime;

    expect(pairs).toHaveLength(500);
    expect(duration).toBeLessThan(50);
  });

  it("builds mapping pairs across 5,000 source columns and candidates under 250 milliseconds", () => {
    const sourceColumns: ColumnMetadata[] = Array.from({ length: 5000 }).map((_, i) => ({
      index: i + 1,
      header_name: `Source_Col_${i + 1}`,
      inferred_type: "DECIMAL",
      type_confidence: 0.95,
      nullable: false,
    }));

    const targetColumns: TargetMasterColumn[] = Array.from({ length: 500 }).map((_, i) => ({
      index: i + 1,
      name: `Target_Col_${i + 1}`,
      expected_type: "DECIMAL",
      required: true,
    }));

    const candidates = Array.from({ length: 5000 }).map((_, i) => ({
      candidate_id: `cand_${i}`,
      source_column_index: i + 1,
      target_column_index: (i % 500) + 1,
      match_type: "exact_header" as const,
      confidence_score: 0.95,
      evidence: "Exact token match",
      is_competing: false,
    }));

    const startTime = performance.now();
    const pairs = buildMappingPairs(sourceColumns, targetColumns, candidates, []);
    const duration = performance.now() - startTime;

    expect(pairs).toHaveLength(5000);
    expect(duration).toBeLessThan(250);
  });

  it("builds mapping pairs across 10,000 source columns and candidates under 500 milliseconds", () => {
    const sourceColumns: ColumnMetadata[] = Array.from({ length: 10000 }).map((_, i) => ({
      index: i + 1,
      header_name: `Source_Col_${i + 1}`,
      inferred_type: "DECIMAL",
      type_confidence: 0.95,
      nullable: false,
    }));

    const targetColumns: TargetMasterColumn[] = Array.from({ length: 1000 }).map((_, i) => ({
      index: i + 1,
      name: `Target_Col_${i + 1}`,
      expected_type: "DECIMAL",
      required: true,
    }));

    const candidates = Array.from({ length: 10000 }).map((_, i) => ({
      candidate_id: `cand_${i}`,
      source_column_index: i + 1,
      target_column_index: (i % 1000) + 1,
      match_type: "exact_header" as const,
      confidence_score: 0.95,
      evidence: "Exact token match",
      is_competing: false,
    }));

    const startTime = performance.now();
    const pairs = buildMappingPairs(sourceColumns, targetColumns, candidates, []);
    const duration = performance.now() - startTime;

    expect(pairs).toHaveLength(10000);
    expect(duration).toBeLessThan(200);
  });
});
