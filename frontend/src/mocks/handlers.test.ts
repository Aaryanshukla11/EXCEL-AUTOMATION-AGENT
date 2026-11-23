import { describe, expect, it } from "vitest";
import { apiClient } from "../api/client";
import type { DiscoveryManifest } from "../contracts/discovery";
import type { SpatialRegion } from "../contracts/spatial";
import type { RegionTypeReport } from "../contracts/types";
import type { ClientConfig } from "../config/clientConfig";

describe("MSW Contract Handlers & API Transport", () => {
  it("fetches DiscoveryManifest matching M01 contract", async () => {
    const data = await apiClient<DiscoveryManifest>("/api/v1/manifest");

    expect(data.manifest_id).toBe("550e8400-e29b-41d4-a716-446655440000");
    expect(data.tables).toHaveLength(1);
    expect(data.tables[0]?.sheet_name).toBe("Revenue");
    expect(data.tables[0]?.bounding_box).toEqual({
      start_row: 5,
      start_col: 2,
      end_row: 25,
      end_col: 8,
    });
    expect(data.formula_graph.has_cycles).toBe(false);
  });

  it("fetches SpatialRegions matching M04 contract", async () => {
    const data = await apiClient<SpatialRegion[]>("/api/v1/spatial");

    expect(data.length).toBeGreaterThanOrEqual(1);
    expect(data[0]?.region_type).toBe("declared_table");
    expect(data[0]?.evidence[0]?.evidence_type).toBe("DECLARED_OPENXML");
  });

  it("fetches RegionTypeReport matching M05 contract", async () => {
    const data = await apiClient<RegionTypeReport>("/api/v1/types");

    expect(data.region_id).toBe("region_rev_01");
    expect(data.columns[2]?.inferred_type).toBe("STRING");
    expect(data.columns[3]?.inferred_type).toBe("DECIMAL");
  });

  it("fetches ClientConfig matching schema", async () => {
    const data = await apiClient<ClientConfig>("/api/v1/config/client");

    expect(data.configVersion).toBe("1.1.0");
    expect(data.branding.organizationName).toBe("Test Environment");
  });
});
