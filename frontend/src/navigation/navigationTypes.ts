import type { FeatureVisibility, Terminology } from "../config/clientConfig";

export type NavGroup = "core" | "audit" | "system";

export type NavStatus = "ready" | "coming-soon" | "disabled";

export interface NavItem {
  readonly id: string;
  readonly label: string;
  readonly terminologyKey?: keyof Terminology;
  readonly path: string;
  readonly iconName: string;
  readonly group: NavGroup;
  readonly featureKey?: keyof FeatureVisibility;
  readonly status: NavStatus;
  readonly badge?: string;
  readonly order: number;
  readonly children?: readonly NavItem[];
}

export interface NavGroupSection {
  readonly group: NavGroup;
  readonly title: string;
  readonly items: readonly NavItem[];
}
