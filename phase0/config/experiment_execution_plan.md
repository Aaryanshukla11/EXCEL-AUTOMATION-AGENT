# Phase 0 Experiment Execution Plan

## 1. Sequence and Dependency Graph

```
[EXP-01: OpenXML Part Preservation] --> [EXP-05: Format & VBA Streams]
[EXP-02: Streaming & Memory Scaling] --> [EXP-03: Formula Recalculation]
[EXP-04: Dynamic & Volatile AST] ----> [EXP-07: Plan Validation & Invariants]
[EXP-06: Storage & Transactions] ----> [EXP-08: Scoped HMAC Token Security]
                                 \
                                  --> [EXP-09: Cognitive Architecture 3-Way Benchmark]
                                  --> [PROTOCOL-QA-01: Statistical Sample-Size Audit]
```

## 2. Experiment Execution Matrix

1. **EXP-01:** OpenXML Part Preservation (Compare openpyxl vs. Archive Part-Patcher on charts, dynamic array spills, slicers, tables).
2. **EXP-02:** Streaming Ingestion & Memory Scaling (100k-row sheet RSS benchmark & 5x20k multi-workbook consolidation profiling).
3. **EXP-03:** Formula Recalculation & Headless Value Caching (fullCalcOnLoad vs. headless pandas/calamine evaluation).
4. **EXP-04:** Dynamic & Volatile Formula AST Dependencies (Static EBNF DAG vs. INDIRECT/OFFSET/Spill quarantine).
5. **EXP-05:** Format Limits & Opaque VBA Preservation (.xlsx, .xlsm opaque vbaProject.bin SHA-256 parity, .xlsb read availability).
6. **EXP-06:** Storage & Transaction Durability (Staging, fsync, parent dir sync, os.replace, WAL, simulated crash recovery).
7. **EXP-07:** Operation-Plan Shadow Dry-Run Validation (Intercept 50 adversarial invalid plans before disk write).
8. **EXP-08:** Scoped HMAC-SHA256 Token Lifecycle & Concurrency (50-thread concurrent replay attack, TTL, tampering).
9. **EXP-09:** Cognitive Architecture Topology Benchmark (8-Agent Swarm vs. 4-Subsystem vs. Tool-Augmented Orchestrator via repeated-measures LMM).
10. **Statistical Audit Verification:** Validate the 837-unit power derivation, verify the 850-unit requirement, and simulate ICC distributions.
