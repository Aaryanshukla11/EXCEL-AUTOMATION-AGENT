# Phase 0 Benchmark Corpus Inventory

The following synthetic benchmark fixtures are generated dynamically by isolated research harnesses for Phase 0 execution:

1. `BENCH-FIDELITY-01.xlsm`: Macro-enabled workbook containing an Excel `ListObject`, dynamic array formula (`=SORT(UNIQUE(A2:A10))#`), table slicer, column chart, comments, and opaque `vbaProject.bin`. Used for EXP-01 and EXP-05.
2. `BENCH-SCALE-100K.xlsx`: Synthetic 100,000 rows × 50 columns sparse grid workbook. Used for EXP-02 single-sheet streaming RSS benchmark.
3. `BENCH-PERF-MULTI-5`: 5 source workbooks of 20,000 rows each + 1 Master workbook (total 120,000 rows). Used for EXP-02 multi-workbook consolidation profiling benchmark (V1.2 NFR-03).
4. `BENCH-CALC-20.xlsx`: 20 standard formula types evaluated for headless reader behavior under deferred calculation. Used for EXP-03.
5. `BENCH-FORMULA-100.json`: 100 formula strings containing static references, cross-sheet links, structured references, and dynamic volatile tokens (`INDIRECT`, `OFFSET`, `#`). Used for EXP-04.
6. `BENCH-STORAGE-FAULT-100`: Synthetic directory containing simulated transaction writes with SIGKILL / abrupt power-fail simulation across local NTFS and simulated sync lock contention. Used for EXP-06.
7. `BENCH-PLANS-50.json`: 50 adversarial consolidation plans injecting boundary collisions, circular references, unauthorized cell overwrites, and type errors. Used for EXP-07.
8. `BENCH-TOKEN-RACE-50`: Multi-threaded cryptographic test suite firing 50 concurrent requests with identical HMAC-SHA256 tokens and nonces. Used for EXP-08.
9. `BENCH-CONSOL-20`: 20 diverse multi-workbook consolidation tasks evaluated across 5 repeated runs per cognitive architecture candidate ($N=100$ runs per candidate). Used for EXP-09.
10. `BENCH-AUDIT-200-SIM`: Simulated pilot corpus of 200 workbooks (100 clean, 50 isolated, 50 mixed) used to compute empirical intra-cluster correlation (ICC) and validate sample size models.
