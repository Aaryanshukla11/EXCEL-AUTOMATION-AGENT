import type { SpatialTableRegion } from "../../contracts/spatial";

export interface ViewportState {
  zoom: number; // 0.5 to 2.0
  selectedRegionId: string | null;
  hoveredRegionId: string | null;
  hoveredCoord: { row: number; col: number } | null;
}

export interface RegionVisualProperties {
  strokeColor: string;
  fillColor: string;
  textColor: string;
  pattern: "solid" | "hatched" | "dotted";
  label: string;
}

export function getRegionVisualProperties(region: SpatialTableRegion): RegionVisualProperties {
  switch (region.region_type) {
    case "declared_table":
      return {
        strokeColor: "rgb(37, 99, 235)", // Blue-600
        fillColor: "rgba(37, 99, 235, 0.12)",
        textColor: "rgb(30, 64, 175)",
        pattern: "solid",
        label: region.declared_name ? `Table: ${region.declared_name}` : "Declared Table",
      };
    case "inferred_table":
      return {
        strokeColor: "rgb(147, 51, 234)", // Purple-600
        fillColor: "rgba(147, 51, 234, 0.12)",
        textColor: "rgb(107, 33, 168)",
        pattern: "solid",
        label: "Inferred Table",
      };
    case "key_value_grid":
      return {
        strokeColor: "rgb(5, 150, 105)", // Emerald-600
        fillColor: "rgba(5, 150, 105, 0.12)",
        textColor: "rgb(6, 95, 70)",
        pattern: "dotted",
        label: "Key-Value Block",
      };
    case "sparse_island":
      return {
        strokeColor: "rgb(217, 119, 6)", // Amber-600
        fillColor: "rgba(217, 119, 6, 0.12)",
        textColor: "rgb(146, 64, 14)",
        pattern: "hatched",
        label: "Sparse Island",
      };
    case "irregular_composite":
      return {
        strokeColor: "rgb(225, 29, 72)", // Rose-600
        fillColor: "rgba(225, 29, 72, 0.12)",
        textColor: "rgb(159, 18, 57)",
        pattern: "hatched",
        label: "Irregular Composite",
      };
    default:
      return {
        strokeColor: "rgb(100, 116, 139)",
        fillColor: "rgba(100, 116, 139, 0.12)",
        textColor: "rgb(51, 65, 85)",
        pattern: "solid",
        label: "Unknown Region",
      };
  }
}
