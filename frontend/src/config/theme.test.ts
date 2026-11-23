import { describe, expect, it } from "vitest";
import { DEFAULT_CLIENT_CONFIG } from "./clientConfig";
import { applyThemeTokens, getTerminology } from "./theme";

describe("Runtime Theme Application", () => {
  it("injects CSS variables onto document.documentElement", () => {
    const testElement = document.createElement("div");

    applyThemeTokens(DEFAULT_CLIENT_CONFIG, testElement);

    expect(testElement.style.getPropertyValue("--primary")).toBe("221 83% 53%");
    expect(testElement.style.getPropertyValue("--radius")).toBe("0.5rem");
    expect(testElement.style.getPropertyValue("--font-sans")).toContain("Segoe UI");
  });

  it("applies dark mode class when colorScheme is dark", () => {
    const testElement = document.createElement("div");
    const darkConfig = {
      ...DEFAULT_CLIENT_CONFIG,
      theme: {
        ...DEFAULT_CLIENT_CONFIG.theme,
        colorScheme: "dark" as const,
      },
    };

    applyThemeTokens(darkConfig, testElement);
    expect(testElement.classList.contains("dark")).toBe(true);
  });

  it("removes dark mode class when colorScheme is light", () => {
    const testElement = document.createElement("div");
    testElement.classList.add("dark");

    applyThemeTokens(DEFAULT_CLIENT_CONFIG, testElement);
    expect(testElement.classList.contains("dark")).toBe(false);
  });

  it("resolves client terminology with getTerminology helper", () => {
    expect(getTerminology(DEFAULT_CLIENT_CONFIG, "defect")).toBe("Defect");
    expect(getTerminology(DEFAULT_CLIENT_CONFIG, "approval")).toBe("Approval");

    const customized = {
      ...DEFAULT_CLIENT_CONFIG,
      terminology: {
        ...DEFAULT_CLIENT_CONFIG.terminology,
        defect: "Anomaly",
      },
    };
    expect(getTerminology(customized, "defect")).toBe("Anomaly");
  });
});
