import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "../mocks/server";

// Establish API mocking before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

// Reset any runtime request handlers added during individual tests
afterEach(() => {
  server.resetHandlers();
  document.documentElement.className = "";
  document.documentElement.removeAttribute("style");
});

// Clean up after all tests are finished
afterAll(() => {
  server.close();
});
