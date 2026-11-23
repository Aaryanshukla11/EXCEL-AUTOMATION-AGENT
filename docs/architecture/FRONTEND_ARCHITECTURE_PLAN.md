# Autonomous Excel Intelligence Platform
## Frontend Architecture Specification & Implementation Roadmap

**Document Type:** Strategic Frontend Architecture & Engineering Implementation Plan  
**Document Version:** 1.0-Proposed  
**Date:** 2026-11-23  
**Status:** Architecture Discovery & Planning Baseline (Zero Production Code Modified)  
**Target Capabilities:** Universal Discovery, Structural & Quality Auditing, Human-in-the-Loop Approvals, Execution & Audit  

---

## 1. Executive Summary & Context

Milestones **M01 through M05** of the Autonomous Excel Intelligence Platform are formally closed, verified across multiple Python runtimes (3.12, 3.13) and Rust, and merged into `main`. The platform currently possesses:
- A high-performance native streaming OpenXML reader (`excel_intel_rs`) with strict resident memory guards ($< 250\text{ MiB}$);
- Spatial segmentation and bounding-box discovery (`excel_intel/spatial/`);
- Statistical semantic column profiling and explicit inference states (`excel_intel/types/`);
- A pure-Python formula lexer, operator-precedence parser, strongly typed AST, and bounded calculation dependency DAG with iterative cycle detection (`excel_intel/formulas/`);
- A canonical manifest synthesis adapter (`excel_intel/adapters/manifest_adapter.py`) producing the root M01 `DiscoveryManifest`.

The platform now initiates the **Frontend Workstream**. 

### Primary Architectural Challenge: Client Change Adaptability
In enterprise data consolidation and spreadsheet automation, client requirements evolve dynamically across different engagement sizes:
- **Minor Tweaks:** Corporate brand colors, fonts, terminology changes (e.g. "Consolidation" vs. "Reconciliation"), and table column ordering.
- **Medium Adjustments:** Layout changes, custom dashboard widgets, specialized data filters, and modified approval thresholds.
- **Structural Alterations:** New multi-level approval hierarchies, custom compliance sign-offs, and new business interaction forms.
- **Major Redesigns:** Replacing traditional desktop sidebars with step-by-step wizard workflows, embedding the UI into client host portals, or introducing entirely new analytical modules.

The frontend architecture specified herein is **production-grade, modular, and client-configurable**. It avoids the naive fallacy that "all changes can be solved through configuration alone." Instead, it establishes a **5-Tier Change Management Architecture** that combines declarative configuration, headless component composability, feature-sliced module isolation, and pluggable workflow pipelines.

---

## 2. Existing Project Inspection & Baseline Audit

### 2.1 Repository Structure & Technology Baseline
The current repository is an air-gapped, pure-Python / Rust hybrid package configured via `pyproject.toml` and Cargo:
- `excel_intel/core/`: Frozen foundational schemas, Pydantic v2 data models, platform configuration, and custom exceptions.
- `crates/excel_intel_rs/`: Rust native core (`calamine` + PyO3) for memory-bounded streaming cell parsing and shared strings caching.
- `excel_intel/inspection/`: Anomaly detection algorithms and OpenXML package inspection.
- `excel_intel/spatial/`: Spatial bounding-box segmentation, header hierarchy resolution, and zone classification.
- `excel_intel/types/`: Deterministic 2D coordinate sampling (10,000 cells max) and statistical column type inference.
- `excel_intel/formulas/`: Pure-Python formula tokenizer, AST parser, dependency graph, and iterative Tarjan SCC cycle detector.
- `excel_intel/adapters/`: Downstream synthesis adapter assembling the canonical `DiscoveryManifest`.
- `excel_intel/cli.py`: Command-line dispatcher supporting `validate-config`, `inspect`, `plan`, `apply`, `rollback`, and `audit`.

### 2.2 Available Backend Integration Boundaries (What Exists)
The backend produces structured, frozen, Pydantic v2 data contracts that form the bedrock for frontend consumption:
1. `DiscoveryManifest`: Root workbook artifact containing SHA-256 hash, file size, table lists, and formula graph metadata.
2. `TableMetadata` & `SpatialTableRegion`: Exact 1-indexed coordinate bounding boxes (`row_start`, `row_end`, `col_start`, `col_end`), header zones, data bodies, subtotals, and footers.
3. `RegionTypeReport` & `ColumnProfile`: Inferred semantic types (`INTEGER`, `DECIMAL`, `CURRENCY`, `DATE`, `BOOLEAN`, `STRING`), discrete inference states (`INFERRED`, `UNKNOWN`, `AMBIGUOUS`, `INSUFFICIENT_DATA`), homogeneity ratios ($H$), and heuristic support scores ($S$).
4. `FormulaGraphReport`: Precedent-dependent directed edges ($u \rightarrow v$), confirmed circular reference paths, volatile function lists, dynamic spill tags (`DYNAMIC_SPILL`), and incomplete dependency sentinels (`POTENTIAL_CYCLES_UNVERIFIED`).
5. `AuditLedgerEntry`: SHA-256 chained transaction records capturing operation intent, timestamps, and execution status.

### 2.3 Integration Gaps (What Does Not Exist Yet)
- **Zero Web Server / API Layer:** There is currently no HTTP, REST, or WebSocket server in the repository. The backend operates exclusively as a library and CLI tool.
- **No Background Task Supervisor:** Long-running multi-workbook inspection and consolidation tasks run synchronously in the CLI. A web frontend requires an asynchronous job runner with session UUIDs and streaming event emitters.
- **No Multipart Upload Endpoint:** Files are currently read from local filesystem paths.

---

## 3. Recommended Frontend Architecture

### 3.1 Technology Stack Selection & Rationale

| Layer | Recommended Technology | Justification & Architectural Trade-offs |
| :--- | :--- | :--- |
| **Framework & Runtime** | **Vite + React 18 / 19 + TypeScript** | ADR-11 dictates a self-contained local desktop/intranet service with zero cloud dependencies. A lightweight React SPA served by a local ASGI daemon is significantly lighter, starts faster, consumes less process RAM, and bundles cleanly into local desktop wrappers (Tauri / Electron) compared to full Next.js server runtimes. |
| **Component Primitives** | **Radix UI Primitives (Headless) + Tailwind CSS** | Radical client redesigns require complete control over markup and styling. Headless unstyled primitives provide 100% WAI-ARIA accessibility, keyboard navigation, and composability without enforcing baked-in visual styling. |
| **Styling & Theming** | **Tailwind CSS + CSS Custom Properties (Design Tokens)** | Dynamic client theming (brand colors, typography, border radiuses, spacing) is driven by CSS variables resolved at runtime without requiring client-specific build steps. |
| **Server State & Caching**| **TanStack Query (React Query v5)** | Provides declarative caching, automated background polling for inspection/execution status, optimistic updates, request deduplication, and zero-boilerplate error boundaries. |
| **Client & UI State** | **Zustand** | Minimalist, unopinionated, slice-based state store with zero context re-render overhead. Ideal for managing active sessions, theme state, selection queues, and modal triggers. |
| **Complex Table Grids** | **TanStack Table (React Table v8)** | Headless, virtualized grid architecture capable of rendering 100,000-cell inspection matrices smoothly, with multi-column sorting, column reordering, resizing, and dynamic pin support. |
| **Workflow State Machine**| **XState v5 (or lightweight reducer statecharts)** | Manages multi-step Human-in-the-Loop (HITL) approval gates, preventing invalid state transitions (e.g. attempting to commit before cryptographic HMAC signature verification). |
| **Form Management** | **React Hook Form + Zod** | High-performance, uncontroller-based form engine with runtime Zod schema validation matching backend Pydantic models. |
| **Network & Mocking** | **Axios / Fetch + Mock Service Worker (MSW v2)** | Intercepts requests at the network layer during development, enabling frontend engineers to develop against strict OpenAPI contracts before backend endpoints are built. |

### 3.2 Application Architecture: Feature-Sliced Design (FSD)
The frontend repository will be organized into decoupled, highly cohesive architectural layers to guarantee maintainability and prevent circular dependencies:

```text
frontend/
├── public/                    # Static assets, fallback logos, client overrides
├── src/
│   ├── app/                   # App initialization, router, global providers, theme root
│   │   ├── providers/         # ThemeProvider, QueryClientProvider, AuthProvider
│   │   └── router.tsx         # Route manifests & dynamic route guards
│   ├── config/                # Declarative Client Configuration Engine
│   │   ├── client.schema.ts   # Zod validation schema for client configuration
│   │   ├── default.config.ts  # Universal base platform configuration
│   │   └── theme.tokens.ts    # Design tokens mapped to CSS custom properties
│   ├── modules/               # Feature Slices (Domain Capabilities)
│   │   ├── dashboard/         # Executive summary, recent runs, health cards
│   │   ├── upload/            # Workbook drag-drop, SHA-256 preflight, format validation
│   │   ├── discovery/         # Spatial grid viewer, zone overlays, semantic type inspector
│   │   ├── formula-graph/     # Directed DAG visualization, cycle inspector, volatile catalog
│   │   ├── mapping/           # Column alignment matrix, candidate key selector
│   │   ├── quality-audit/     # 5 defect category viewer, jagged row & cycle inspectors
│   │   ├── approval-hitl/     # Side-by-side diff cards, HMAC token signer, conflict adjudication
│   │   ├── execution/         # 6-phase WAL monitor, real-time event timeline, rollback trigger
│   │   ├── audit-ledger/      # Chained SHA-256 ledger explorer, compliance export
│   │   └── settings/          # Visual theme customizer, table density, threshold configuration
│   ├── components/            # Reusable Headless Component Library (Atomic UI)
│   │   ├── ui/                # Radix UI wrappers (Button, Dialog, Dropdown, Tabs, Tooltip)
│   │   ├── layout/            # Shell, TopNav, Sidebar, Header, Breadcrumbs, StatusFooter
│   │   ├── table/             # Virtualized TanStack Table wrapper with column switcher
│   │   └── feedback/          # AlertBanner, ErrorBoundary, ProgressRing, ToastManager
│   ├── lib/                   # Shared Infrastructure & Utilities
│   │   ├── api/               # Type-safe API client generated from backend OpenAPI
│   │   ├── formatters/        # Currency, date, coordinate, and file size formatters
│   │   └── hooks/             # useTheme, useWorkbook, useSSEEventStream
│   └── mocks/                 # Isolated Mock Service Worker (MSW) Handlers & Fixtures
```

---

## 4. Required UI Modules Specification

Every module maps strictly to actual product requirements defined in Release 1.0 (`PRODUCT_REQUIREMENTS_BASELINE.md` and `SYSTEM_ARCHITECTURE.md`).

```
+==================================================================================================+
|                                    APPLICATION SHELL & NAVIGATION                                |
+==================================================================================================+
|  [Sidebar / TopNav]   |  [Breadcrumbs]                     [Client Logo] [Theme] [Storage Quota] |
+-----------------------+--------------------------------------------------------------------------+
|  1. Dashboard         |  ACTIVE WORKFLOW: Multi-Source Vendor Consolidation (Session #4f8a2)     |
|  2. Workbooks         |  +--------------------------------------------------------------------+  |
|  3. Discovery Viewer  |  | Stage 1: Upload  -->  Stage 2: Discovery  -->  Stage 3: Mapping    |  |
|  4. Field Mapping     |  | Stage 4: Quality -->  Stage 5: Approval   -->  Stage 6: Execution  |  |
|  5. Quality Audit     |  +--------------------------------------------------------------------+  |
|  6. HITL Approvals    |                                                                          |
|  7. Execution Monitor |  [ACTIVE MODULE VIEWPORT]                                                |
|  8. Audit Ledger      |  (Dynamically rendered based on active route and client layout config)   |
|  9. Settings          |                                                                          |
+==================================================================================================+
```

### Module 1: Application Shell & Responsive Layout Engine
- **Purpose:** Host navigation, user session context, memory/storage quota indicators, and dynamic brand identity.
- **Capabilities:**
  - Pluggable layout modes: Left Sidebar, Collapsible Mini-Bar, Top Navbar, or Embedded Portal Mode.
  - Runtime theme injector applying client tokens (`--color-primary`, `--font-family`, `--radius`).
  - Active session tracker showing memory usage against the 235 MiB / 250 MiB process limit.

### Module 2: Dashboard & Operation Overview
- **Purpose:** Central command screen displaying recent activity, pending action items, and engine health.
- **Capabilities:**
  - Pending Approval Action Cards (e.g. "3 workbooks require blank-field enrichment authorization").
  - Consolidation History Table with status pills (`COMMITTED`, `ROLLED_BACK`, `FAILED`).
  - Health Metrics: Process RSS, active temporary staging storage, and SQLite audit hash-chain status.

### Module 3: Workbook Upload & Staging Manager
- **Purpose:** Ingest master and source workbooks with client-side preflight safety.
- **Capabilities:**
  - Multi-file drag-and-drop supporting `.xlsx`, `.xlsm`, and read-only `.xlsb`.
  - Client-side preflight: WebCrypto SHA-256 calculation, file size validation ($< 1\text{ GiB}$ aggregate quota), and format signature verification.
  - Source role assigner: Flag workbooks as `TARGET_MASTER` or `SOURCE_N`.

### Module 4: Workbook Inspection & Spatial Discovery Viewer
- **Purpose:** Visual spreadsheet grid viewer displaying structural topology discovered in M02, M04, and M05.
- **Capabilities:**
  - Multi-sheet tab switcher.
  - Visual zone overlays: Color-coded bounding boxes highlighting `TITLE_BANNER`, `COLUMN_HEADER`, `DATA_BODY`, `SUBTOTAL`, `GRAND_TOTAL`, and `FOOTNOTE`.
  - Column Semantic Type Inspector: Clicking a column surfaces the M05 statistical drawer showing inferred type, state (`INFERRED`, `AMBIGUOUS`, etc.), homogeneity ratio ($H$), support score ($S$), and nullability ratio.
  - Formula DAG Visualizer: Interactive tree rendering precedent cell chains, cycle warnings, and volatile function tags (`NOW()`, `TODAY()`, `OFFSET()`).

### Module 5: Schema Alignment & Semantic Field Mapping
- **Purpose:** Interactive alignment matrix matching source columns to destination Master columns.
- **Capabilities:**
  - Column alignment table with confidence badges ($S \ge 0.80$ green, $< 0.80$ yellow).
  - Manual drag-and-drop mapping override with human justification input.
  - Candidate Key Selector: Flag columns as primary/composite keys for deduplication (`BENCH-DEDUP-500`).
  - Unmapped field indicator highlighting source fields with no destination in the Master table.

### Module 6: Data Quality & Anomaly Report
- **Purpose:** Pre-execution audit surfacing the 5 explicit defect categories defined in Release 1.0 (`PROTOCOL-QA-01`).
- **Capabilities:**
  - Category 1: Formula Evaluation Errors (`#REF!`, `#VALUE!`, `#DIV/0!`, `#NAME?`, `#N/A`).
  - Category 2: Calculation Circular Reference Cycles (reconstructing closed Tarjan SCC paths).
  - Category 3: Jagged Rows (structural row length variance violating table boundary).
  - Category 4: Unmapped Source Fields.
  - Category 5: Candidate Key Collision Anomalies (duplicate keys with conflicting attributes).
  - One-click filtering and CSV/JSON defect manifest export.

### Module 7: Human-in-the-Loop (HITL) Approval Console
- **Purpose:** Enforce mandatory approval gates before any physical workbook mutation occurs.
- **Capabilities:**
  - Gate 1: Blank-Field Enrichment Approval (`CON-03` / `FR-09`).
  - Gate 2: Populated Cell Overwrite Approval (`CON-04` / `FR-10`).
  - Gate 3: Divergent Key Value Adjudication (`DR-A2`).
  - Visual Side-by-Side Diff Cards: Display target coordinate, existing value, incoming proposed value, source workbook provenance, and confidence score.
  - Granular selection: "Approve Selected", "Reject Selected", or "Override with Custom Value".
  - Cryptographic Signer: Generates client-side HMAC-SHA256 signature binding the approved payload.

### Module 8: Execution & WAL Durability Monitor
- **Purpose:** Real-time visibility into the 6-phase atomic execution sequence.
- **Capabilities:**
  - Live pipeline progress tracking:
    `1. Pre-State Snapshot (.bak)` $\rightarrow$ `2. WAL Intent Recorded` $\rightarrow$ `3. Staged Mutation & fsync` $\rightarrow$ `4. Atomic Replace` $\rightarrow$ `5. Parent Dir Sync` $\rightarrow$ `6. WAL Committed`.
  - Emergency Abort Button: Trigger immediate atomic rollback restoring the pre-execution `.bak` state.
  - Post-flight verification card displaying cell write counts and post-run hash verification.

### Module 9: Audit Ledger & Compliance Explorer
- **Purpose:** Transparent provenance inspection of all historical operations.
- **Capabilities:**
  - Cryptographic audit trail table reading from `audit_trail.jsonl`.
  - SHA-256 Chain Integrity Verifier: Visual verification that every block's `previous_hash` matches.
  - Filter by date, user, workbook, target table, or operation type (`INSERT_ROW`, `ENRICH_CELL`, `OVERWRITE_CELL`).

### Module 10: Client Customization & Settings Panel
- **Purpose:** Interactive editor for client branding, thresholds, and operational rules.
- **Capabilities:**
  - Live Theme Customizer: Edit primary color, font family, border radius, and logo with instant preview.
  - Quality Threshold Sliders: Adjust ambiguity penalty thresholds ($0.80$) and sampling cell caps.
  - Export/Import Configuration: Download `client.config.json` for deployment version control.

---

## 5. Client Change Management Architecture

To accommodate client requests of any size without architectural rewrites, the frontend implements a **5-Tier Change Management Framework**:

```
+==================================================================================================+
|                             5-TIER CLIENT CHANGE MANAGEMENT FRAMEWORK                            |
+==================================================================================================+
|  Tier 1: Configuration-Only Changes  | Zero Code Change  | JSON Schema, CSS Variables, Branding  |
|  Tier 2: Component-Level Overrides   | Minor Code Change | Headless Slots, Custom Cell Renderers |
|  Tier 3: Modular Screen Additions    | Isolated Extension| Feature Slices, Pluggable Routes      |
|  Tier 4: Workflow & Gate Changes     | Pipeline Extension| XState Statecharts, Custom Gates      |
|  Tier 5: Major UI Redesigns          | Shell Swapping    | Swappable Layout Providers            |
+==================================================================================================+
```

### Tier 1: Configuration-Only Changes (Zero Code Changes)
* **Scope:** Colors, typography, brand logo, enterprise labels, terminology overrides ("Vendor" $\rightarrow$ "Supplier"), default table page size, and enabled module flags.
* **Mechanism:**
  - Driven by a declarative `client.config.json` file validated against a strict Zod schema (`client.schema.ts`).
  - Theme tokens are mapped to standard CSS Custom Properties at the root document level:
    ```css
    :root {
      --color-primary: #1e40af;
      --color-surface: #ffffff;
      --font-family-base: "Inter", sans-serif;
      --border-radius-base: 6px;
    }
    ```
  - Label dictionary maps UI text keys (`terminology.consolidation_title: "Monthly Financial Rollup"`).
  - Can be updated in production by replacing `client.config.json` without recompiling or rebuilding the application.

### Tier 2: Component-Level Overrides (Minor, Controlled Code Changes)
* **Scope:** Custom table column formatters, specialized filter dropdowns, client-specific metric cards, or proprietary cell badges.
* **Mechanism:**
  - Headless component slots. Complex components expose explicit slot interfaces:
    ```tsx
    <DataTable
      columns={columns}
      data={data}
      slots={{
        headerCell: CustomClientHeaderRenderer,
        actionCell: CustomApprovalActionDropdown,
      }}
    />
    ```
  - Developers implement isolated component adapters without modifying table logic, pagination, or sorting hooks.

### Tier 3: Modular Screen Additions (Feature-Sliced Extensions)
* **Scope:** Adding a completely new functional screen (e.g. "Tax Regulatory Summary" or "Vendor Master Reconciler").
* **Mechanism:**
  - Develop an independent directory in `src/modules/<new-feature>/`.
  - Register the new module in the dynamic `routeManifest.ts`:
    ```ts
    registerModule({
      id: "tax-summary",
      title: "Tax Regulatory Summary",
      icon: "ReceiptIcon",
      path: "/tax-summary",
      component: lazy(() => import("@/modules/tax-summary")),
      requiredPermissions: ["AUDIT_READ"],
    });
    ```
  - Zero modification to existing modules, core navigation shells, or backend adapters.

### Tier 4: Workflow & Approval Gate Alterations (Pipeline Extensions)
* **Scope:** Adding an extra review stage (e.g. "Finance Director Sign-off"), changing approval conditions, or conditional routing.
* **Mechanism:**
  - Approval workflows are modeled as composable statecharts (XState).
  - Workflow definition files specify ordered stages and required token signatures.
  - Adding a stage involves inserting a new state node in the configuration with its associated UI gate component, preserving preceding and succeeding execution phases.

### Tier 5: Major UI Redesigns (Layout & Shell Swapping)
* **Scope:** Completely replacing the visual design (e.g. converting from an enterprise multi-tab desktop layout to a mobile-responsive wizard, or embedding inside an existing client portal iframe).
* **Mechanism:**
  - **Decoupled Viewports:** Business logic and data hooks (`useWorkbookDiscovery`, `useConsolidationReview`) are strictly decoupled from visual layouts.
  - **Layout Providers:** The application shell implements a `LayoutProvider` interface:
    - `DefaultSidebarLayout`: Standard enterprise desktop layout.
    - `WizardStepperLayout`: Step-by-step sequential guided workflow.
    - `EmbeddedHeadlessLayout`: Minimalist chromeless frame for iframe integration.
  - A radical client redesign only requires writing a new layout shell; all underlying table grids, diff cards, approval hooks, and API integrations remain 100% intact.

### 5.1 Configuration Versioning & Backward Compatibility Policy
- Every client configuration file carries a semantic schema version (`"config_version": "1.0.0"`).
- At application startup, the `ConfigurationLoader` parses `client.config.json` through versioned Zod migration transforms.
- If an older configuration is loaded (e.g. `v1.0.0` into a `v1.2.0` frontend), automated migration defaults populate missing keys, ensuring zero client breakage.
- Schema violations log granular diagnostic errors and fall back gracefully to `default.config.ts`.

---

## 6. Backend Integration Contract & API Specification

The frontend connects to the backend via a structured REST / WebSocket API. Below is the formal gap analysis identifying existing backend capabilities versus new required service endpoints.

### 6.1 Backend API Gap Analysis

| Capability Area | Existing Backend Implementation (M01–M05) | Required Web Service API (To Be Developed) | Integration Method |
| :--- | :--- | :--- | :--- |
| **Configuration** | `PlatformConfig.load_config()` | `GET /api/v1/config/environment`<br>`GET /api/v1/config/client` | REST JSON |
| **Upload & Staging** | Local path strings | `POST /api/v1/workbooks/upload`<br>`DELETE /api/v1/workbooks/{id}` | Multipart Form + WebCrypto SHA-256 |
| **Discovery & Inspection** | `SpatialDetector`, `TypeInferrer`, `manifest_adapter.py` | `POST /api/v1/workbooks/{id}/inspect`<br>`GET /api/v1/workbooks/{id}/manifest` | REST JSON (`DiscoveryManifest`) |
| **Formula & Dependency** | `FormulaParser`, `FormulaDependencyGraph`, `CycleDetector` | `GET /api/v1/workbooks/{id}/formula-graph`<br>`GET /api/v1/workbooks/{id}/cycles` | REST JSON (`FormulaGraphReport`) |
| **Consolidation Planning** | CLI placeholder (`Module 06`) | `POST /api/v1/consolidation/plan`<br>`GET /api/v1/consolidation/{id}/mapping` | REST JSON (`OperationPlan`) |
| **Quality Audit** | `AnomalyDetector` (M03), Formula Cycle checks (M05) | `GET /api/v1/workbooks/{id}/quality-report` | REST JSON (5 Defect Categories) |
| **HITL Approvals** | HMAC Token Signer specification (`ADR-08`) | `GET /api/v1/approvals/{id}/pending`<br>`POST /api/v1/approvals/{id}/sign` | REST JSON (HMAC-SHA256 Token) |
| **Execution & WAL** | CLI `apply`, WAL recovery spec (`ADR-07`) | `POST /api/v1/execution/apply`<br>`POST /api/v1/execution/{id}/rollback` | SSE / WebSocket + REST |
| **Audit Ledger** | `audit_vault.db` SQLite schema (M01) | `GET /api/v1/audit/ledger`<br>`POST /api/v1/audit/verify-chain` | REST JSON |

### 6.2 Strict Production Integrity Policy (No Fake APIs)
- **Zero Mocking in Production Code:** Production frontend builds strictly call verified backend endpoints. Fake API responses or hardcoded fallback records in production bundles are strictly forbidden.
- **Isolated Development Mock Harness (MSW v2):** During frontend engineering phases prior to backend service readiness, Mock Service Worker (MSW) intercepts requests at the browser network layer (`src/mocks/handlers.ts`). Mock handlers validate payload schemas using the exact Pydantic-derived TypeScript interfaces, guaranteeing zero integration friction when connecting to the live FastAPI backend.

---

## 7. Frontend Implementation Roadmap & Phasing Plan

The frontend implementation proceeds in **6 structured, test-driven phases**. Each phase contains explicit deliverables, dependencies, and measurable acceptance criteria.

```text
+==================================================================================================+
|                                  FRONTEND IMPLEMENTATION ROADMAP                                 |
+==================================================================================================+
|  Phase F0: Foundation Tooling, Design System & Mock Harness (Weeks 1 - 2)                        |
|  - Vite, TypeScript, Tailwind, Radix UI, Storybook, MSW OpenAPI Mock Harness                     |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase F1: Application Shell, Theming & Client Config Engine (Weeks 3 - 4)                       |
|  - Dynamic Shell, Zod Client Config, CSS Variable Theme Engine, Navigation Router                |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase F2: Workbook Management & Discovery Grid Viewer (Weeks 5 - 6)                             |
|  - Upload Manager, Virtualized Grid, Zone Overlays, Column Type Inspector, Formula DAG Visualizer|
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase F3: Mapping Matrix, Quality Audit & Anomaly Reporting (Weeks 7 - 8)                       |
|  - Field Mapping Matrix, Candidate Key Selector, 5 Defect Category Viewers, Export Engine        |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase F4: Human-in-the-Loop Approval Console & Cryptographic Signer (Weeks 9 - 10)              |
|  - Side-by-Side Diff Cards, Gate Evaluator, Client-Side HMAC-SHA256 Token Generator              |
+--------------------------------------------------------------------------------------------------+
                                                |
                                                v
|  Phase F5: Execution Monitor, Audit Ledger & Live Backend Integration (Weeks 11 - 12)             |
|  - 6-Phase WAL Timeline, Abort Trigger, Audit Chain Explorer, End-to-End FastAPI Verification    |
+==================================================================================================+
```

### Phase F0: Foundation Tooling, Design System & Mock Harness (Duration: 2 Weeks)
* **Objective:** Establish the development environment, headless design system, and contract-first mock server.
* **Deliverables:**
  - Vite + React + TypeScript repository setup under `frontend/`.
  - Tailwind CSS configuration with dynamic CSS custom property bindings.
  - Headless component primitives: Button, Dialog, Dropdown, Tabs, Tooltip, Input, Card.
  - Mock Service Worker (MSW v2) fixture harness reflecting backend M01–M05 data schemas.
* **Acceptance Criteria:**
  - 100% component unit test coverage on core primitives via Vitest and React Testing Library.
  - MSW mock server successfully serves valid `DiscoveryManifest` and `RegionTypeReport` fixtures.
  - Zero build warnings under strict TypeScript (`"strict": true`).

### Phase F1: Application Shell, Theming & Client Config Engine (Duration: 2 Weeks)
* **Objective:** Build the responsive shell, client configuration engine, and runtime theme customizer.
* **Deliverables:**
  - Dynamic responsive application shell (Sidebar, Topbar, Status Footer).
  - Client configuration engine with Zod validation schema (`client.schema.ts`).
  - Runtime theme injector and visual settings editor.
  - Navigation router with breadcrumbs and active session persistence.
* **Acceptance Criteria:**
  - Replacing `client.config.json` updates brand colors, logos, and labels instantly without rebuilding.
  - Schema validation gracefully rejects invalid configurations and logs actionable diagnostic errors.

### Phase F2: Workbook Management & Spatial Discovery Viewer (Duration: 2 Weeks)
* **Objective:** Deliver multi-file upload management and the spatial spreadsheet grid explorer.
* **Deliverables:**
  - Drag-and-drop file upload with client WebCrypto SHA-256 preflight.
  - Virtualized spreadsheet grid rendering table bounding boxes (`SpatialTableRegion`).
  - Semantic column type inspection drawer (homogeneity $H$, support score $S$, state).
  - Formula dependency DAG visualizer rendering precedent chains and cycle alerts.
* **Acceptance Criteria:**
  - Smooth virtualized scrolling across a 100,000-cell grid maintaining 60 FPS.
  - Visual zone bounding boxes match M04 detection coordinates bit-for-bit.

### Phase F3: Field Mapping Matrix, Quality Audit & Anomaly Reporting (Duration: 2 Weeks)
* **Objective:** Build the consolidation mapping matrix and the 5-category quality audit inspector.
* **Deliverables:**
  - Source-to-master column mapping matrix with confidence badges and override selectors.
  - Candidate key assignment interface for deduplication.
  - Quality Audit Report displaying the 5 defect categories (`#REF!`, cycles, jagged rows, unmapped fields, key collisions).
* **Acceptance Criteria:**
  - Column mapping matches `DiscoveryManifest` column profiles with zero data fabrication.
  - All 5 defect categories filter and export to JSON/CSV manifests accurately.

### Phase F4: Human-in-the-Loop (HITL) Approval Console & Cryptographic Signer (Duration: 2 Weeks)
* **Objective:** Build the mandatory approval console and HMAC-SHA256 token signing engine.
* **Deliverables:**
  - Side-by-side diff cards displaying target coordinates, old vs. proposed values, and confidence scores.
  - Approval queue for Blank-Field Enrichment (`CON-03`) and Populated Overwrites (`CON-04`).
  - Scoped HMAC-SHA256 token generator binding approved operations to user identity and session.
* **Acceptance Criteria:**
  - Unapproved operations are strictly blocked from proceeding to execution payloads.
  - Generated approval tokens conform exactly to backend `ADR-08` cryptographic specifications.

### Phase F5: Execution Monitor, Audit Ledger & Live Backend Integration (Duration: 2 Weeks)
* **Objective:** Connect to live backend APIs, visualize the 6-phase WAL execution, and verify audit ledgers.
* **Deliverables:**
  - Real-time WAL pipeline visualizer tracking atomic staging, replacement, and commits.
  - Emergency rollback trigger button.
  - Cryptographic Audit Ledger explorer verifying SHA-256 block hash integrity.
  - End-to-end integration tests connecting live React frontend to the backend service.
* **Acceptance Criteria:**
  - Simulated execution failures display instantaneous rollback notification and state restoration.
  - Audit trail viewer successfully validates SHA-256 hash chains with zero discrepancy.
  - All automated E2E tests pass across Chromium, Firefox, and WebKit via Playwright.

---

## 8. Immediate Next Milestone Recommendation

To begin frontend engineering with maximum velocity and zero risk of blocking on backend API implementation:

### **Authorize and Initiate: Milestone F0 — Foundation Tooling, Headless Design System & Contract Mock Harness**

#### Immediate Scope of Milestone F0:
1. Initialize the `frontend/` workspace using Vite, React 18/19, TypeScript, and Tailwind CSS.
2. Establish the headless component library utilizing Radix UI primitives.
3. Configure the CSS Custom Property theme engine to prove Tier 1 client configuration viability.
4. Build the Mock Service Worker (MSW v2) contract harness utilizing existing frozen M01–M05 Pydantic schemas, enabling rapid, air-gapped UI development.
5. Setup automated testing pipelines: Vitest, React Testing Library, and Playwright.

Milestone F0 establishes the client-change foundation and contract mock layer, allowing frontend development to proceed in parallel with backend service packaging.
