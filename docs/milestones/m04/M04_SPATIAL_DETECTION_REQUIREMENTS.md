# Milestone M04 — Spatial Detection
## Document 2 of 3: Detailed Requirements & Specification

**Date:** 2026-11-21  
**Milestone:** M04 — Spatial Detection  
**Stage:** Prompt 1 of 4 (Architecture Inspection & Requirements Discovery)  
**Status:** COMPLETE (Planning & Audit Only — Zero Code Modification)  
**Branch:** `main` (Strict Zero Autonomous Commits/Pushes)

---

## 1. Primary Purpose & Scope

Milestone M04 delivers the **Spatial Grid & Bounding-Box Analyzer** specified in Section 2 and Section 5.1 of the System Architecture Design (SAD).

Its objective is to take the structural facts and streaming cell tokens from M02/M03 and segment worksheets into distinct, bounded rectangular tabular entities, resolve header hierarchies, decompose internal semantic zones (title, header, body, summary, footnotes), and enforce ADR-005 append boundary safety.

---

## 2. Functional Requirements (FRs)

### FR-1: 2D Spatial Connected-Component & Whitespace Segmentation
- **FR-1.1 (Vertical & Horizontal Whitespace Cuts):** The segmenter must identify both horizontal whitespace gaps (empty rows) and vertical whitespace gaps (empty columns) to partition populated cells into discrete rectangular regions.
- **FR-1.2 (Side-by-Side Table Separation):** When two or more tabular grids occupy the same horizontal row band separated by $\ge 1$ blank column(s), the segmenter must isolate them as distinct spatial regions rather than lumping them into a single wide block.
- **FR-1.3 (Stacked Table Separation):** When tables are stacked vertically with $\ge 1$ blank row or separated by a distinct header/schema transition, they must be partitioned into independent spatial regions.
- **FR-1.4 (Sparse Island Clustering):** Scattered, low-density coordinates must be grouped into `SparseIslandRegion` objects without causing artificial table expansion across millions of empty cells.

### FR-2: Header Hierarchy & Multi-Row Resolution
- **FR-2.1 (Single-Row Header Detection):** Detect standard 1-row column headers using type transition entropy (string headers above numeric/date data) and style formatting cues.
- **FR-2.2 (Multi-Row Stacked Headers):** Recognize hierarchical multi-level headers (e.g. parent category in Row 1 spanning cols A..D, child sub-headers in Row 2). Synthesize canonical compound column names (e.g. `"2024 Performance -> Q1"`).
- **FR-2.3 (Merged Header Blocks):** Integrate declared OpenXML `DeclaredMergeCell` facts into header hierarchy resolution. A merged range across cols A..C in header row 1 must distribute its parent label across columns A, B, and C.
- **FR-2.4 (Title Banner Disambiguation):** Distinguish top-level sheet titles or metadata key-value banners (e.g. single cells or merged banners across row 1) from the actual column header row. Ensure titles are classified as `RegionZoneType.TITLE_BANNER` and not mistaken for column headers.

### FR-3: Intra-Region Semantic Zone Decomposition
Every detected tabular region must be decomposed into exact 1-indexed bounding sub-boxes:
1. `TITLE_BANNER`: Optional metadata or title rows above the header grid.
2. `COLUMN_HEADER`: 1 or more rows containing column labels.
3. `DATA_BODY`: Contiguous rectangular grid containing primary data records.
4. `SUMMARY_TOTALS`: Optional summary row(s) containing aggregation formulas (`SUM`, `AVERAGE`, `COUNT`, `SUBTOTAL`) or summary label keywords (`Total`, `Average`).
5. `FOOTNOTES`: Optional disclaimer, note, or signature lines below the table.

### FR-4: ADR-005 Boundary Collision & Margin Clearance Analysis
- **FR-4.1 (Spare Cell Margin Measurement):** For every detected tabular region, calculate the count of blank rows immediately below the data body or summary zone before the next cell or worksheet boundary.
- **FR-4.2 (Zero-Space Collision Detection):** If an ordinary range (non-ListObject) has 0 spare rows below it, or has summary formulas located immediately in the row below the data body, emit `ERR_BOUNDARY_COLLISION`.
- **FR-4.3 (Formula Proximity Sentinel):** Detect if cells immediately below or adjacent to a table contain formulas referencing the table's coordinates. Automated record append is prohibited without explicit user escalation to convert the range to a `ListObject` (ADR-005).

### FR-5: Spatial Overlap & Cross-Boundary Merge Cell Conflict Detection
- **FR-5.1 (Region Collision Detection):** Detect if any two candidate regions overlap or share coordinates (`region_a.box.intersects(region_b.box)`). Emit `WARNING_AMBIGUOUS_STRUCTURE` and flag the intersection zone.
- **FR-5.2 (Cross-Boundary Merge Detection):** Detect if a `DeclaredMergeCell` spans across the boundary of a detected region (e.g., top-left inside table, bottom-right outside table). Emit `ANOM_CROSS_BOUNDARY_MERGE`.

### FR-6: Canonical Transformation to M01 `TableMetadata`
- **FR-6.1 (Contract Compliance):** Provide an immutable transformation method `to_table_metadata() -> TableMetadata` conforming to `excel_intel.core.types.TableMetadata`.
- **FR-6.2 (Discovery Manifest Readiness):** Ensure all detected spatial tables can be aggregated into `DiscoveryManifest.tables`.

---

## 3. Non-Functional Requirements (NFRs)

### NFR-1: Bounded Memory & Spatial Scaling ($O(C \cdot W)$)
- Spatial detection must operate within bounded memory complexity.
- Row analysis must use a sliding lookahead window of size $W \le 50$ rows.
- Peak RSS memory growth during spatial detection of a 100,000-row sheet must not exceed **50.0 MB** above baseline. Total process memory must remain strictly below the 235 MB warning limit and 250 MB hard ceiling.

### NFR-2: Throughput & Latency Target
- Spatial segmentation and zone decomposition must execute in **$< 200\text{ ms}$ per 10,000 populated cells**.
- For standard workbooks (< 50 MB, < 5 sheets), total spatial analysis must complete in **$< 1.5\text{ seconds}$**.

### NFR-3: Determinism & Immutability
- Given the same input workbook, spatial detection must produce bit-for-bit identical region bounding boxes, header names, and zone coordinates across multiple runs.
- Source workbook files must remain completely unmodified (SHA-256 integrity strictly verified).

### NFR-4: Multi-Workbook Concurrency & Isolation
- The spatial analyzer must be stateless, reentrant, and thread-safe.
- Multiple worker threads inspecting distinct workbooks simultaneously must execute with **zero cross-contamination** and zero shared mutable state.

---

## 4. Edge Cases & Complex Topologies

1. **Side-by-Side Tables on Shared Rows:** Two distinct tables occupying rows 5..50 (Table A in cols B..E, Table B in cols H..K) separated by blank cols F..G. M04 must produce two distinct `SpatialTableRegion` entities.
2. **Stacked Tables with 1 Blank Row:** Table 1 in rows 1..10, Row 11 blank, Table 2 in rows 12..25. Must produce two distinct tables, not one 25-row table with an empty row.
3. **Stacked Tables with 0 Blank Rows (Direct Schema Transition):** Table 1 ending at row 10, Table 2 starting at row 11 with a new header row. Must detect type entropy shift and segment into two tables.
4. **Multi-Row Header with Colspan & Rowspan:** Row 1 has merged cell A1:B1 ("Q1 Metrics"), Row 2 has A2 ("Revenue"), B2 ("Cost"), and Row 1:2 has merged cell C1:C2 ("Status"). Must resolve compound headers: `["Q1 Metrics -> Revenue", "Q1 Metrics -> Cost", "Status"]`.
5. **Title Banners & Freeform Metadata:** Single text cell in A1 ("CONFIDENTIAL REPORT 2024"), followed by blank row 2, followed by table at A3:D20. A1 must be classified as `TITLE_BANNER`, not a 1-column header.
6. **Trailing Summary Rows without Labels:** Data rows 2..20 have numbers; row 21 has `=SUM(A2:A20)` with no text label like "Total". Must identify formula pattern and classify row 21 as `SUMMARY_TOTALS`.
7. **Zero-Space Collision (ADR-005):** Ordinary range at A1:D20; Row 21 contains `=SUM(D2:D20)`. Append operation target at row 21 must trigger `ERR_BOUNDARY_COLLISION`.
8. **Extreme Coordinates & Sparse Islands:** Table at A1:E20, single stray note cell at `XFD1000000`. Must bound the table at A1:E20 and isolate the stray cell as `SPARSE_ISLAND`, not expand table to `A1:XFD1000000`.

---

## 5. Acceptance Criteria & Quality Gates

| Metric / Requirement | Target Threshold | Validation Method |
| :--- | :---: | :--- |
| **Tabular Bounding Box Intersection-over-Union (IoU)** | $\text{IoU} \ge 0.98$ | Tested against synthetic and benchmark ground-truth corpora. |
| **Side-by-Side Table Separation Accuracy** | $100\%$ | Multi-table verification test fixtures. |
| **Header Row Transition Accuracy** | $\ge 99.0\%$ | Ground-truth benchmark evaluation. |
| **ADR-005 Zero-Space Collision Recall** | $100.0\%$ | Negative boundary test fixtures with trailing summary formulas. |
| **Memory Ceiling Compliance** | Peak RSS $\le 250.0\text{ MB}$ | OS Working Set measurement during 100k-row scaling run. |
| **Thread Safety & Multi-Workbook Isolation** | $0$ cross-contamination | Concurrent multi-threaded test with distinct workbooks. |
| **Source Immutability** | $100\%$ SHA-256 match | Pre/post inspection checksum verification. |
