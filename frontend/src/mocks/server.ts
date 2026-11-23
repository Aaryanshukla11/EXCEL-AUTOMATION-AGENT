import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/**
 * Node MSW Server for Vitest test environment.
 */
export const server = setupServer(...handlers);
