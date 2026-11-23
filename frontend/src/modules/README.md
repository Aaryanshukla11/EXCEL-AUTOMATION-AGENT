# Frontend Feature Modules Directory

This directory implements the Feature-Sliced architecture defined in `docs/architecture/FRONTEND_ARCHITECTURE_PLAN.md`.

In accordance with the **Milestone F0 scope boundary**, business feature logic is strictly deferred to subsequent milestones:

- `src/modules/shell/` — Milestone F1 (Shell & Navigation)
- `src/modules/dashboard/` — Milestone F1 (Ingestion & Pipeline Metrics)
- `src/modules/staging/` — Milestone F1 (Workbook Ingestion & Validation)
- `src/modules/spatial-viewer/` — Milestone F2 (Spatial Grid & Bounding Box Viewer)
- `src/modules/schema-studio/` — Milestone F4 (Column Mapping & Transformation)
- `src/modules/quality-audit/` — Milestone F3 (5 Defect Category Triage Console)
- `src/modules/approval-console/` — Milestone F3 (HITL Workflow & Sign-Off)
- `src/modules/execution-monitor/` — Milestone F4 (WAL & Step Execution Stream)
- `src/modules/audit-ledger/` — Milestone F4 (DAG Lineage & Cryptographic Proofs)
- `src/modules/customization-studio/` — Milestone F5 (Live Client Configuration Editor)
