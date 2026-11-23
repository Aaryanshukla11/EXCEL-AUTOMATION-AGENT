import type { ClientConfig } from "./clientConfig";

const RADIUS_MAP: Record<NonNullable<ClientConfig["theme"]["borderRadius"]>, string> = {
  none: "0px",
  sm: "0.25rem",
  md: "0.5rem",
  lg: "0.75rem",
  full: "9999px",
};

/**
 * Injects runtime theme tokens into CSS Custom Properties on the target DOM element.
 * Defaults to document.documentElement (HTML root).
 *
 * Enables instant white-labeling and rebranding without rebuilding the bundle.
 */
export function applyThemeTokens(
  config: ClientConfig,
  target: HTMLElement = typeof document !== "undefined"
    ? document.documentElement
    : (null as unknown as HTMLElement)
): void {
  if (!target) return;

  const { theme, layout } = config;

  // Apply primary color HSL
  target.style.setProperty(
    "--primary",
    `${theme.primaryHue} ${theme.primarySaturation}% ${theme.primaryLightness}%`
  );
  target.style.setProperty(
    "--ring",
    `${theme.primaryHue} ${theme.primarySaturation}% ${theme.primaryLightness}%`
  );

  // Apply secondary color HSL
  target.style.setProperty(
    "--secondary",
    `${theme.secondaryHue} ${theme.secondarySaturation}% ${theme.secondaryLightness}%`
  );

  // Apply border radius
  const radiusVal = RADIUS_MAP[theme.borderRadius] || "0.5rem";
  target.style.setProperty("--radius", radiusVal);

  // Apply typography
  target.style.setProperty("--font-sans", theme.fontFamily);
  target.style.setProperty("--font-mono", theme.monoFontFamily);
  target.style.setProperty("--font-size-base", `${theme.baseFontSize}px`);

  // Apply density
  if (layout.density === "compact") {
    target.classList.add("density-compact");
  } else {
    target.classList.remove("density-compact");
  }

  // Apply color scheme class
  if (theme.colorScheme === "dark") {
    target.classList.add("dark");
  } else if (theme.colorScheme === "light") {
    target.classList.remove("dark");
  } else if (typeof window !== "undefined" && window.matchMedia) {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (prefersDark) {
      target.classList.add("dark");
    } else {
      target.classList.remove("dark");
    }
  }
}

/**
 * Access a terminology term with safe fallback to English defaults.
 */
export function getTerminology(
  config: ClientConfig,
  key: keyof ClientConfig["terminology"]
): string {
  return config.terminology[key] || key;
}
