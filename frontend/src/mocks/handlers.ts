import { http, HttpResponse } from "msw";
import {
  MOCK_CLIENT_CONFIG,
  MOCK_DISCOVERY_MANIFEST,
  MOCK_FORMULA_DAG,
  MOCK_FORMULA_GRAPH_REPORT,
  MOCK_MAPPING_CANDIDATES,
  MOCK_QUALITY_AUDIT_REPORT,
  MOCK_SPATIAL_REGIONS,
  MOCK_TARGET_MASTER_SCHEMAS,
  MOCK_TYPE_REPORT,
  MOCK_WORKBOOK_DISCOVERY,
  MOCK_APPROVAL_REQUESTS,
  MOCK_EXECUTION_JOBS,
  MOCK_AUDIT_BLOCKS,
} from "./fixtures";

/**
 * MSW v2 Request Handlers for Development & Testing.
 * Strictly mirrors backend contracts.
 */
export const handlers = [
  // GET /api/v1/manifest
  http.get("/api/v1/manifest", () => {
    return HttpResponse.json(MOCK_DISCOVERY_MANIFEST);
  }),

  // GET /api/v1/spatial/discovery
  http.get("/api/v1/spatial/discovery", () => {
    return HttpResponse.json(MOCK_WORKBOOK_DISCOVERY);
  }),

  // GET /api/v1/spatial
  http.get("/api/v1/spatial", () => {
    return HttpResponse.json(MOCK_SPATIAL_REGIONS);
  }),

  // GET /api/v1/types
  http.get("/api/v1/types", () => {
    return HttpResponse.json(MOCK_TYPE_REPORT);
  }),

  // GET /api/v1/formulas/dag
  http.get("/api/v1/formulas/dag", () => {
    return HttpResponse.json(MOCK_FORMULA_DAG);
  }),

  // GET /api/v1/formulas/graph
  http.get("/api/v1/formulas/graph", () => {
    return HttpResponse.json(MOCK_FORMULA_GRAPH_REPORT);
  }),

  // GET /api/v1/schema-mapping/targets
  http.get("/api/v1/schema-mapping/targets", () => {
    return HttpResponse.json(MOCK_TARGET_MASTER_SCHEMAS);
  }),

  // GET /api/v1/schema-mapping/candidates
  http.get("/api/v1/schema-mapping/candidates", () => {
    return HttpResponse.json(MOCK_MAPPING_CANDIDATES);
  }),

  // GET /api/v1/quality/findings
  http.get("/api/v1/quality/findings", () => {
    return HttpResponse.json(MOCK_QUALITY_AUDIT_REPORT);
  }),

  // GET /api/v1/config/client
  http.get("/api/v1/config/client", () => {
    return HttpResponse.json(MOCK_CLIENT_CONFIG);
  }),

  // GET /api/v1/approvals
  http.get("/api/v1/approvals", () => {
    return HttpResponse.json(MOCK_APPROVAL_REQUESTS);
  }),

  // GET /api/v1/approvals/:id
  http.get("/api/v1/approvals/:id", ({ params }) => {
    const found = MOCK_APPROVAL_REQUESTS.find((r) => r.request_id === params.id);
    if (!found) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(found);
  }),

  // GET /api/v1/execution/jobs
  http.get("/api/v1/execution/jobs", () => {
    return HttpResponse.json(MOCK_EXECUTION_JOBS);
  }),

  // GET /api/v1/execution/jobs/:id
  http.get("/api/v1/execution/jobs/:id", ({ params }) => {
    const found = MOCK_EXECUTION_JOBS.find((j) => j.job_id === params.id);
    if (!found) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(found);
  }),

  // GET /api/v1/audit/blocks
  http.get("/api/v1/audit/blocks", () => {
    return HttpResponse.json(MOCK_AUDIT_BLOCKS);
  }),

  // POST /api/v1/audit/verify-chain
  http.post("/api/v1/audit/verify-chain", () => {
    return HttpResponse.json({
      is_valid: true,
      total_blocks: MOCK_AUDIT_BLOCKS.length,
      verified_blocks: MOCK_AUDIT_BLOCKS.length,
      checked_at: new Date().toISOString(),
    });
  }),
];
