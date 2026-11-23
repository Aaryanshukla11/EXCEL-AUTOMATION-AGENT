import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

/**
 * Browser MSW Service Worker for development mode.
 * STRICTLY active in development mode only; excluded from production builds.
 */
export const worker = setupWorker(...handlers);

export async function enableMocking(): Promise<void> {
  // Never enable MSW in production builds
  if (!import.meta.env.DEV) {
    return;
  }

  // Skip if service worker is not supported or not running in a standard window
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    console.warn("[MSW] ServiceWorker API is not available; mock service worker disabled.");
    return;
  }

  try {
    const startPromise = worker.start({
      onUnhandledRequest: "bypass",
      serviceWorker: {
        url: "/mockServiceWorker.js",
      },
      waitUntilReady: false,
    });

    const timeoutPromise = new Promise<void>((_, reject) =>
      setTimeout(() => reject(new Error("MSW registration timed out after 2000ms")), 2000)
    );

    await Promise.race([startPromise, timeoutPromise]);
  } catch (err) {
    console.warn(
      "[MSW] Failed to register service worker or timed out. Development mock endpoints may be unavailable:",
      err
    );
    if (typeof window !== "undefined") {
      (window as unknown as { __MSW_INIT_ERROR__?: unknown }).__MSW_INIT_ERROR__ = err;
    }
  }
}
