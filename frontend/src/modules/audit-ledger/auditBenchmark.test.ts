import { describe, expect, it } from "vitest";
import type { AuditBlock } from "./auditTypes";
import {
  computeAuditBlockHash,
  filterAndSortAuditBlocks,
  GENESIS_PARENT_HASH,
  verifyAuditChain,
} from "./auditLedgerUtils";

describe("Audit Ledger Large-Scale Benchmark (F5)", () => {
  it("verifies hash-chain structure across 5,000 blocks under 100 milliseconds", async () => {
    const blocks: AuditBlock[] = [];
    let prevHash = GENESIS_PARENT_HASH;

    for (let i = 1; i <= 5000; i++) {
      const blockHash = `${i.toString().padStart(8, "0")}${"a".repeat(56)}`;
      blocks.push({
        block_id: i,
        timestamp: new Date(Date.now() - (5000 - i) * 1000).toISOString(),
        previous_hash: prevHash,
        block_hash: blockHash,
        actor: `actor_${i % 10}@corp.internal`,
        operation_type: i % 2 === 0 ? "UPDATE_CELL" : "INSERT_ROW",
        target_workbook: "master.xlsx",
        target_sheet: "Sheet1",
        target_range: `A${i}`,
        payload_summary: `Operation #${i}`,
        status: "COMMITTED",
      });
      prevHash = blockHash;
    }

    const startTime = performance.now();
    const result = await verifyAuditChain(blocks, { verifyPayloadHashes: false });
    const duration = performance.now() - startTime;

    expect(result.is_valid).toBe(true);
    expect(result.total_blocks).toBe(5000);
    expect(duration).toBeLessThan(100);
  });

  it("verifies full SHA-256 cryptographic payload integrity across 1,000 blocks under 200 milliseconds", async () => {
    const blocks: AuditBlock[] = [];
    let prevHash = GENESIS_PARENT_HASH;

    for (let i = 1; i <= 1000; i++) {
      const partial = {
        block_id: i,
        timestamp: new Date(Date.now() - (1000 - i) * 1000).toISOString(),
        previous_hash: prevHash,
        actor: `operator_${i % 5}@corp.internal`,
        operation_type: i % 2 === 0 ? "UPDATE_CELL" : "INSERT_ROW",
        target_workbook: "master.xlsx",
        target_sheet: "Sheet1",
        target_range: `A${i}`,
        payload_summary: `Operation #${i}`,
        status: "COMMITTED" as const,
      };
      const hash = await computeAuditBlockHash(partial);
      blocks.push({ ...partial, block_hash: hash });
      prevHash = hash;
    }

    const startTime = performance.now();
    const result = await verifyAuditChain(blocks, { verifyPayloadHashes: true });
    const duration = performance.now() - startTime;

    expect(result.is_valid).toBe(true);
    expect(result.total_blocks).toBe(1000);
    expect(duration).toBeLessThan(200);
  });

  it("filters and sorts 5,000 audit blocks under 100 milliseconds", () => {
    const blocks: AuditBlock[] = Array.from({ length: 5000 }).map((_, i) => ({
      block_id: i + 1,
      timestamp: new Date(Date.now() - i * 10000).toISOString(),
      previous_hash: GENESIS_PARENT_HASH,
      block_hash: `${i.toString().padStart(8, "0")}${"a".repeat(56)}`,
      actor: `operator_${i % 5}`,
      operation_type: i % 3 === 0 ? "MUTATION" : "INSPECTION",
      target_workbook: `workbook_${i % 10}.xlsx`,
      target_sheet: "Sheet1",
      target_range: "A1:B10",
      payload_summary: `Payload summary for block #${i + 1}`,
      status: i % 4 === 0 ? "ROLLED_BACK" : "COMMITTED",
    }));

    const startTime = performance.now();
    const filtered = filterAndSortAuditBlocks(
      blocks,
      "block #42",
      "COMMITTED",
      "all",
      "all",
      "timestamp",
      false
    );
    const duration = performance.now() - startTime;

    expect(filtered.length).toBeGreaterThan(0);
    expect(duration).toBeLessThan(100);
  });
});
