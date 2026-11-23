import { describe, expect, it } from "vitest";
import { DEFAULT_CLIENT_CONFIG, type ClientConfig } from "../config/clientConfig";
import { resolveNavigation } from "./defaultNavigation";

describe("Dynamic Navigation Resolution", () => {
  it("resolves all default navigation items in correct groups", () => {
    const sections = resolveNavigation(DEFAULT_CLIENT_CONFIG);

    expect(sections).toHaveLength(3);
    expect(sections[0]?.group).toBe("core");
    expect(sections[0]?.title).toBe("Core Operations");
    expect(sections[1]?.group).toBe("audit");
    expect(sections[2]?.group).toBe("system");

    const coreIds = sections[0]?.items.map((i) => i.id);
    expect(coreIds).toContain("overview");
    expect(coreIds).toContain("staging");
  });

  it("filters out items when feature flag is disabled", () => {
    const configWithDisabledAudit: ClientConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      features: {
        ...DEFAULT_CLIENT_CONFIG.features,
        enableQualityAudit: false,
      },
    };

    const sections = resolveNavigation(configWithDisabledAudit);
    const auditSection = sections.find((s) => s.group === "audit");
    const itemIds = auditSection?.items.map((i) => i.id);

    expect(itemIds).not.toContain("quality-audit");
    expect(itemIds).toContain("approval-console");
  });

  it("applies client terminology dynamically to navigation labels", () => {
    const customizedConfig: ClientConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      terminology: {
        ...DEFAULT_CLIENT_CONFIG.terminology,
        workbook: "Financial Report",
        defect: "Anomaly",
        approval: "Sign-Off",
      },
    };

    const sections = resolveNavigation(customizedConfig);
    const coreSection = sections.find((s) => s.group === "core");
    const stagingItem = coreSection?.items.find((i) => i.id === "staging");
    expect(stagingItem?.label).toBe("Financial Report Staging");

    const auditSection = sections.find((s) => s.group === "audit");
    const defectItem = auditSection?.items.find((i) => i.id === "quality-audit");
    expect(defectItem?.label).toBe("Anomaly Audit");

    const approvalItem = auditSection?.items.find((i) => i.id === "approval-console");
    expect(approvalItem?.label).toBe("Sign-Off Console");
  });

  it("applies navigation overrides for order and custom labels", () => {
    const overrideConfig: ClientConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      navigationOverrides: [
        {
          id: "overview",
          labelOverride: "Executive Dashboard",
          order: 999, // Move to bottom
        },
        {
          id: "spatial-viewer",
          hidden: true, // Hide completely
        },
      ],
    };

    const sections = resolveNavigation(overrideConfig);
    const coreSection = sections.find((s) => s.group === "core");
    const overviewItem = coreSection?.items.find((i) => i.id === "overview");
    expect(overviewItem?.label).toBe("Executive Dashboard");
    expect(overviewItem?.order).toBe(999);

    const spatialItem = coreSection?.items.find((i) => i.id === "spatial-viewer");
    expect(spatialItem).toBeUndefined();
  });
});
