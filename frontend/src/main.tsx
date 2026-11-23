import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app/App";
import "./index.css";

async function prepareApp() {
  if (import.meta.env.DEV) {
    try {
      const { enableMocking } = await import("./mocks/browser");
      await enableMocking();
    } catch (err) {
      console.warn("[MSW] Could not initialize development mock service worker:", err);
      if (typeof window !== "undefined") {
        (window as unknown as { __MSW_INIT_ERROR__?: unknown }).__MSW_INIT_ERROR__ = err;
      }
    }
  }
}

let isMounted = false;

function mountApp() {
  if (isMounted) return;
  const rootElement = document.getElementById("root");
  if (!rootElement) {
    throw new Error("Failed to find root DOM element.");
  }
  isMounted = true;
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// Kick off app rendering promptly; fallback after 1.5 seconds if prepareApp is blocked
prepareApp()
  .catch((err) => {
    console.error("[App] prepareApp error:", err);
  })
  .finally(() => {
    mountApp();
  });

if (typeof window !== "undefined") {
  window.setTimeout(mountApp, 1500);
}
