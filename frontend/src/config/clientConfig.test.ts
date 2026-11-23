import { describe, expect, it } from "vitest";
import { DEFAULT_CLIENT_CONFIG, validateClientConfig } from "./clientConfig";

describe("Client Configuration Validation & Safe Fallback (F1 Extended)", () => {
  it("validates the canonical default configuration successfully (v1.1.0)", () => {
    const result = validateClientConfig(DEFAULT_CLIENT_CONFIG);
    expect(result.isValid).toBe(true);
    expect(result.config.configVersion).toBe("1.1.0");
    expect(result.config.defaultRoute).toBe("/overview");
    expect(result.config.features.enableQualityAudit).toBe(true);
    expect(result.config.layout.density).toBe("comfortable");
  });

  it("supports backward compatibility for legacy v1.0.0 configurations", () => {
    const legacyConfig = {
      configVersion: "1.0.0",
      branding: {
        appTitle: "Legacy Enterprise Rollup",
        organizationName: "Legacy Corp",
      },
      theme: {
        colorScheme: "light",
        primaryHue: 210,
        primarySaturation: 80,
        primaryLightness: 50,
        borderRadius: "sm",
        fontFamily: "sans-serif",
        monoFontFamily: "monospace",
      },
      terminology: {
        workbook: "Spreadsheet",
        sheet: "Tab",
        table: "Data Block",
        defect: "Error",
        remediation: "Fix",
        approval: "Sign-Off",
        dag: "Tree",
        wal: "Log",
      },
    };

    const result = validateClientConfig(legacyConfig);
    expect(result.isValid).toBe(true);
    expect(result.config.configVersion).toBe("1.0.0");
    expect(result.config.branding.appTitle).toBe("Legacy Enterprise Rollup");
    // Verifies that new v1.1.0 fields are populated with safe defaults:
    expect(result.config.defaultRoute).toBe("/overview");
    expect(result.config.features.enableApprovalConsole).toBe(true);
    expect(result.config.layout.variant).toBe("default");
  });

  it("safely falls back to defaults when input is null or undefined", () => {
    const resultNull = validateClientConfig(null);
    expect(resultNull.isValid).toBe(false);
    expect(resultNull.config).toEqual(DEFAULT_CLIENT_CONFIG);
    expect(resultNull.errors).toBeDefined();

    const resultUndefined = validateClientConfig(undefined);
    expect(resultUndefined.isValid).toBe(false);
    expect(resultUndefined.config).toEqual(DEFAULT_CLIENT_CONFIG);
  });

  it("safely rejects and falls back when unsupported configVersion is provided", () => {
    const invalidConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      configVersion: "2.0.0", // Unsupported major version
    };
    const result = validateClientConfig(invalidConfig);
    expect(result.isValid).toBe(false);
    expect(result.config).toEqual(DEFAULT_CLIENT_CONFIG);
    expect(result.errors?.[0]).toContain("configVersion");
  });

  it("blocks injection attempts in font families and URLs", () => {
    const maliciousConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      theme: {
        ...DEFAULT_CLIENT_CONFIG.theme,
        fontFamily: "Inter; } body { background: red; } /*",
      },
    };

    const result = validateClientConfig(maliciousConfig);
    expect(result.isValid).toBe(false);
    expect(result.config).toEqual(DEFAULT_CLIENT_CONFIG);
  });

  it("blocks javascript: pseudoprotocol in logo URL", () => {
    const xssLogoConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      branding: {
        ...DEFAULT_CLIENT_CONFIG.branding,
        logoUrl: "javascript:alert(1)",
      },
    };

    const result = validateClientConfig(xssLogoConfig);
    expect(result.isValid).toBe(false);
    expect(result.config).toEqual(DEFAULT_CLIENT_CONFIG);
  });
});
