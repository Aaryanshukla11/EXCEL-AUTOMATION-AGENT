import { z } from "zod";

/**
 * Extended Terminology Schema supporting custom client domain language.
 */
export const TerminologySchema = z.object({
  workbook: z.string().min(1).default("Workbook"),
  sheet: z.string().min(1).default("Sheet"),
  table: z.string().min(1).default("Table"),
  defect: z.string().min(1).default("Defect"),
  remediation: z.string().min(1).default("Remediation"),
  approval: z.string().min(1).default("Approval"),
  dag: z.string().min(1).default("Dependency Graph"),
  wal: z.string().min(1).default("Write-Ahead Log"),
  consolidation: z.string().min(1).default("Consolidation"),
  lineage: z.string().min(1).default("Lineage"),
});

/**
 * Enterprise Branding Schema.
 * Strictly sanitizes URLs to prevent javascript: or malformed URI injection.
 */
export const BrandingSchema = z.object({
  appTitle: z.string().min(1).default("Autonomous Excel Intelligence"),
  organizationName: z.string().min(1).default("Default Organization"),
  logoUrl: z
    .string()
    .regex(/^(https?:\/\/|\/|data:image\/).+$/i, "Must be a valid HTTP(S), relative, or data URI")
    .optional(),
  faviconUrl: z
    .string()
    .regex(/^(https?:\/\/|\/|data:image\/).+$/i, "Must be a valid HTTP(S), relative, or data URI")
    .optional(),
  supportEmail: z.string().email().optional(),
});

/**
 * Runtime Theme Tokens Schema.
 * Values are bounded integers and enums to prevent arbitrary CSS injection.
 */
export const ThemeTokensSchema = z.object({
  colorScheme: z.enum(["light", "dark", "system"]).default("light"),
  primaryHue: z.number().min(0).max(360).default(221),
  primarySaturation: z.number().min(0).max(100).default(83),
  primaryLightness: z.number().min(0).max(100).default(53),
  secondaryHue: z.number().min(0).max(360).default(215),
  secondarySaturation: z.number().min(0).max(100).default(20),
  secondaryLightness: z.number().min(0).max(100).default(65),
  borderRadius: z.enum(["none", "sm", "md", "lg", "full"]).default("md"),
  fontFamily: z
    .string()
    .min(1)
    .regex(/^[^;{}<>]+$/, "Font family contains illegal characters")
    .default("-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"),
  monoFontFamily: z
    .string()
    .min(1)
    .regex(/^[^;{}<>]+$/, "Mono font family contains illegal characters")
    .default("ui-monospace, SFMono-Regular, Menlo, Monaco, monospace"),
  baseFontSize: z.number().min(12).max(20).default(14),
});

/**
 * Feature Visibility Flags.
 * Enables clients to selectively toggle future modules.
 */
export const FeatureVisibilitySchema = z.object({
  enableOverview: z.boolean().default(true),
  enableStaging: z.boolean().default(true),
  enableSpatialViewer: z.boolean().default(true),
  enableSchemaStudio: z.boolean().default(true),
  enableQualityAudit: z.boolean().default(true),
  enableApprovalConsole: z.boolean().default(true),
  enableExecutionMonitor: z.boolean().default(true),
  enableAuditLedger: z.boolean().default(true),
  enableCustomizationStudio: z.boolean().default(true),
});

/**
 * Layout Preferences Schema.
 */
export const LayoutPreferencesSchema = z.object({
  variant: z.enum(["default", "minimal", "portal"]).default("default"),
  sidebarCollapsedDefault: z.boolean().default(false),
  density: z.enum(["comfortable", "compact"]).default("comfortable"),
});

/**
 * Navigation Item Override Schema.
 */
export const NavigationOverrideSchema = z.object({
  id: z.string().min(1),
  labelOverride: z.string().optional(),
  order: z.number().optional(),
  hidden: z.boolean().optional(),
});

/**
 * Complete Client Configuration Schema.
 * Supports configVersion "1.0.0" (backward-compatible) and "1.1.0".
 */
export const ClientConfigSchema = z.object({
  configVersion: z.enum(["1.0.0", "1.1.0"]).default("1.1.0"),
  defaultRoute: z
    .string()
    .regex(/^\/[a-zA-Z0-9/_-]*$/)
    .default("/overview"),
  branding: BrandingSchema.default({
    appTitle: "Autonomous Excel Intelligence",
    organizationName: "Default Organization",
  }),
  theme: ThemeTokensSchema.default({
    colorScheme: "light",
    primaryHue: 221,
    primarySaturation: 83,
    primaryLightness: 53,
    secondaryHue: 215,
    secondarySaturation: 20,
    secondaryLightness: 65,
    borderRadius: "md",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    monoFontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
    baseFontSize: 14,
  }),
  terminology: TerminologySchema.default({
    workbook: "Workbook",
    sheet: "Sheet",
    table: "Table",
    defect: "Defect",
    remediation: "Remediation",
    approval: "Approval",
    dag: "Dependency Graph",
    wal: "Write-Ahead Log",
    consolidation: "Consolidation",
    lineage: "Lineage",
  }),
  features: FeatureVisibilitySchema.default({
    enableOverview: true,
    enableStaging: true,
    enableSpatialViewer: true,
    enableSchemaStudio: true,
    enableQualityAudit: true,
    enableApprovalConsole: true,
    enableExecutionMonitor: true,
    enableAuditLedger: true,
    enableCustomizationStudio: true,
  }),
  layout: LayoutPreferencesSchema.default({
    variant: "default",
    sidebarCollapsedDefault: false,
    density: "comfortable",
  }),
  navigationOverrides: z.array(NavigationOverrideSchema).default([]),
});

export type ClientConfig = z.infer<typeof ClientConfigSchema>;
export type Terminology = z.infer<typeof TerminologySchema>;
export type Branding = z.infer<typeof BrandingSchema>;
export type ThemeTokens = z.infer<typeof ThemeTokensSchema>;
export type FeatureVisibility = z.infer<typeof FeatureVisibilitySchema>;
export type LayoutPreferences = z.infer<typeof LayoutPreferencesSchema>;
export type NavigationOverride = z.infer<typeof NavigationOverrideSchema>;

/**
 * Canonical default client configuration.
 */
export const DEFAULT_CLIENT_CONFIG: ClientConfig = {
  configVersion: "1.1.0",
  defaultRoute: "/overview",
  branding: {
    appTitle: "Autonomous Excel Intelligence",
    organizationName: "Default Organization",
  },
  theme: {
    colorScheme: "light",
    primaryHue: 221,
    primarySaturation: 83,
    primaryLightness: 53,
    secondaryHue: 215,
    secondarySaturation: 20,
    secondaryLightness: 65,
    borderRadius: "md",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    monoFontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, monospace",
    baseFontSize: 14,
  },
  terminology: {
    workbook: "Workbook",
    sheet: "Sheet",
    table: "Table",
    defect: "Defect",
    remediation: "Remediation",
    approval: "Approval",
    dag: "Dependency Graph",
    wal: "Write-Ahead Log",
    consolidation: "Consolidation",
    lineage: "Lineage",
  },
  features: {
    enableOverview: true,
    enableStaging: true,
    enableSpatialViewer: true,
    enableSchemaStudio: true,
    enableQualityAudit: true,
    enableApprovalConsole: true,
    enableExecutionMonitor: true,
    enableAuditLedger: true,
    enableCustomizationStudio: true,
  },
  layout: {
    variant: "default",
    sidebarCollapsedDefault: false,
    density: "comfortable",
  },
  navigationOverrides: [],
};

export interface ValidationResult {
  config: ClientConfig;
  isValid: boolean;
  errors?: string[];
}

/**
 * Validates untrusted or dynamic JSON client configuration with safe fallback.
 * Guaranteed never to throw; always returns a valid, sanitized ClientConfig.
 */
export function validateClientConfig(raw: unknown): ValidationResult {
  if (!raw || typeof raw !== "object") {
    return {
      config: DEFAULT_CLIENT_CONFIG,
      isValid: false,
      errors: ["Configuration must be a non-null JSON object."],
    };
  }

  const result = ClientConfigSchema.safeParse(raw);
  if (!result.success) {
    const errorMessages = result.error.errors.map(
      (e) => `${e.path.join(".") || "root"}: ${e.message}`
    );
    return {
      config: DEFAULT_CLIENT_CONFIG,
      isValid: false,
      errors: errorMessages,
    };
  }

  return {
    config: result.data,
    isValid: true,
  };
}
