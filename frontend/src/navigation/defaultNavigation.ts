import type { ClientConfig } from "../config/clientConfig";
import { getTerminology } from "../config/theme";
import type { NavGroupSection, NavItem } from "./navigationTypes";

export const DEFAULT_NAV_ITEMS: readonly NavItem[] = [
  {
    id: "overview",
    label: "Overview & Health",
    path: "/overview",
    iconName: "LayoutDashboard",
    group: "core",
    featureKey: "enableOverview",
    status: "ready",
    order: 10,
  },
  {
    id: "staging",
    label: "Workbook Staging",
    terminologyKey: "workbook",
    path: "/staging",
    iconName: "UploadCloud",
    group: "core",
    featureKey: "enableStaging",
    status: "ready",
    order: 20,
  },
  {
    id: "spatial-viewer",
    label: "Spatial Discovery",
    terminologyKey: "table",
    path: "/spatial-viewer",
    iconName: "Grid",
    group: "core",
    featureKey: "enableSpatialViewer",
    status: "ready",
    order: 30,
  },
  {
    id: "schema-studio",
    label: "Schema Studio",
    path: "/schema-studio",
    iconName: "Workflow",
    group: "core",
    featureKey: "enableSchemaStudio",
    status: "ready",
    order: 40,
  },
  {
    id: "quality-audit",
    label: "Defect Audit Console",
    terminologyKey: "defect",
    path: "/quality-audit",
    iconName: "ShieldAlert",
    group: "audit",
    featureKey: "enableQualityAudit",
    status: "ready",
    order: 50,
  },
  {
    id: "approval-console",
    label: "HITL Approvals",
    terminologyKey: "approval",
    path: "/approval-console",
    iconName: "CheckSquare",
    group: "audit",
    featureKey: "enableApprovalConsole",
    status: "ready",
    order: 60,
  },
  {
    id: "execution-monitor",
    label: "Execution & WAL",
    terminologyKey: "wal",
    path: "/execution-monitor",
    iconName: "Activity",
    group: "audit",
    featureKey: "enableExecutionMonitor",
    status: "ready",
    order: 70,
  },
  {
    id: "audit-ledger",
    label: "Audit Ledger",
    terminologyKey: "dag",
    path: "/audit-ledger",
    iconName: "FileCheck",
    group: "audit",
    featureKey: "enableAuditLedger",
    status: "ready",
    order: 80,
  },
  {
    id: "settings",
    label: "Settings & Customization",
    path: "/settings",
    iconName: "Sliders",
    group: "system",
    featureKey: "enableCustomizationStudio",
    status: "ready",
    order: 90,
  },
];

const GROUP_TITLES: Record<string, string> = {
  core: "Core Operations",
  audit: "Quality & Governance",
  system: "Platform Configuration",
};

/**
 * Dynamically resolves navigation items based on:
 * 1. Feature visibility flags
 * 2. Client terminology mappings
 * 3. Client navigation overrides (ordering, custom label, hidden)
 */
export function resolveNavigation(config: ClientConfig): readonly NavGroupSection[] {
  const overridesMap = new Map(config.navigationOverrides.map((o) => [o.id, o]));

  // Filter and transform items
  const resolvedItems: NavItem[] = [];

  for (const item of DEFAULT_NAV_ITEMS) {
    // Check feature flag
    if (item.featureKey && !config.features[item.featureKey]) {
      continue;
    }

    const override = overridesMap.get(item.id);

    // Check if explicitly hidden
    if (override?.hidden) {
      continue;
    }

    // Resolve dynamic label
    let resolvedLabel = item.label;
    if (override?.labelOverride) {
      resolvedLabel = override.labelOverride;
    } else if (item.terminologyKey) {
      const term = getTerminology(config, item.terminologyKey);
      if (item.id === "staging") {
        resolvedLabel = `${term} Staging`;
      } else if (item.id === "spatial-viewer") {
        resolvedLabel = `${term} Explorer`;
      } else if (item.id === "quality-audit") {
        resolvedLabel = `${term} Audit`;
      } else if (item.id === "approval-console") {
        resolvedLabel = `${term} Console`;
      } else if (item.id === "execution-monitor") {
        resolvedLabel = `${term} Monitor`;
      } else if (item.id === "audit-ledger") {
        resolvedLabel = `${term} Ledger`;
      }
    }

    resolvedItems.push({
      ...item,
      label: resolvedLabel,
      order: override?.order !== undefined ? override.order : item.order,
    });
  }

  // Sort items by order
  resolvedItems.sort((a, b) => a.order - b.order);

  // Group items into sections
  const groups: Record<string, NavItem[]> = {
    core: [],
    audit: [],
    system: [],
  };

  for (const item of resolvedItems) {
    groups[item.group]?.push(item);
  }

  const sections: NavGroupSection[] = [];
  for (const [groupKey, items] of Object.entries(groups)) {
    if (items.length > 0) {
      sections.push({
        group: groupKey as NavGroupSection["group"],
        title: GROUP_TITLES[groupKey] || groupKey,
        items,
      });
    }
  }

  return sections;
}
