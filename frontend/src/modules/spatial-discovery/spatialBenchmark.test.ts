import { describe, expect, it } from "vitest";
import type { SpatialTableRegion } from "../../contracts/spatial";
import { colIndexToLetter, boundingBoxToA1, normalizeBoundingBox } from "./spatialUtils";

function generateSyntheticRegions(count: number, sheetCount: number): SpatialTableRegion[] {
  const regions: SpatialTableRegion[] = [];
  for (let i = 0; i < count; i++) {
    const sheetIndex = i % sheetCount;
    const startRow = ((i * 15) % 1000) + 1;
    const endRow = startRow + 20;
    const startCol = ((i * 4) % 20) + 1;
    const endCol = startCol + 6;

    regions.push({
      region_id: `bench_region_${i}`,
      sheet_name: `Sheet_${sheetIndex}`,
      bounding_box: {
        start_row: startRow,
        start_col: startCol,
        end_row: endRow,
        end_col: endCol,
      },
      region_type: i % 3 === 0 ? "declared_table" : "inferred_table",
      is_declared: i % 3 === 0,
      heuristic_confidence: 0.95,
      cell_count: (endRow - startRow + 1) * (endCol - startCol + 1),
      populated_cell_count: (endRow - startRow) * (endCol - startCol),
      density: 0.95,
      zones: {},
      zone_list: [],
      evidence: [],
    });
  }
  return regions;
}

describe("Spatial Discovery Large-Scale Benchmark (F2)", () => {
  it("processes and projects 500 spatial table regions under 100 milliseconds", () => {
    const regions = generateSyntheticRegions(500, 50);
    const startTime = performance.now();

    const transformedRanges = regions.map((r) => boundingBoxToA1(r.bounding_box));
    const transformedLetters = regions.map((r) =>
      colIndexToLetter(normalizeBoundingBox(r.bounding_box).start_col)
    );

    const duration = performance.now() - startTime;

    expect(transformedRanges).toHaveLength(500);
    expect(transformedLetters).toHaveLength(500);
    expect(duration).toBeLessThan(100);
  });

  it("processes and projects 5,000 spatial table regions under 250 milliseconds", () => {
    const regions = generateSyntheticRegions(5000, 100);
    const startTime = performance.now();

    const transformedRanges = regions.map((r) => boundingBoxToA1(r.bounding_box));
    const transformedLetters = regions.map((r) =>
      colIndexToLetter(normalizeBoundingBox(r.bounding_box).start_col)
    );

    const duration = performance.now() - startTime;

    expect(transformedRanges).toHaveLength(5000);
    expect(transformedLetters).toHaveLength(5000);
    expect(duration).toBeLessThan(250);
  });

  it("processes and projects 10,000 spatial table regions under 500 milliseconds", () => {
    const regions = generateSyntheticRegions(10000, 200);
    const startTime = performance.now();

    const transformedRanges = regions.map((r) => boundingBoxToA1(r.bounding_box));
    const transformedLetters = regions.map((r) =>
      colIndexToLetter(normalizeBoundingBox(r.bounding_box).start_col)
    );

    const duration = performance.now() - startTime;

    expect(transformedRanges).toHaveLength(10000);
    expect(transformedLetters).toHaveLength(10000);
    expect(duration).toBeLessThan(500);
  });
});
