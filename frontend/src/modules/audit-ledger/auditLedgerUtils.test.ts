import { describe, expect, it } from "vitest";
import {
  computeAuditBlockHash,
  filterAndSortAuditBlocks,
  GENESIS_PARENT_HASH,
  verifyAuditChain,
} from "./auditLedgerUtils";
import type { AuditBlock } from "./auditTypes";

describe("Audit Ledger & Cryptographic Chain Utilities (F5)", () => {
  async function createValidChain(): Promise<AuditBlock[]> {
    const rawBlocks = [
      {
        block_id: 1,
        timestamp: "2026-11-23T09:00:00Z",
        previous_hash: GENESIS_PARENT_HASH,
        actor: "system_genesis",
        operation_type: "GENESIS",
        target_workbook: "system",
        target_sheet: "system",
        target_range: "N/A",
        payload_summary: "Genesis block",
        status: "COMMITTED" as const,
      },
      {
        block_id: 2,
        timestamp: "2026-11-23T09:10:00Z",
        previous_hash: "",
        actor: "operator_alex",
        operation_type: "MUTATION",
        target_workbook: "sales.xlsx",
        target_sheet: "Q4",
        target_range: "A1:B10",
        payload_summary: "Appended rows",
        status: "COMMITTED" as const,
      },
      {
        block_id: 3,
        timestamp: "2026-11-23T09:20:00Z",
        previous_hash: "",
        actor: "operator_alex",
        operation_type: "ROLLBACK",
        target_workbook: "sales.xlsx",
        target_sheet: "Q4",
        target_range: "A1:B10",
        payload_summary: "Rollback performed",
        status: "ROLLED_BACK" as const,
      },
    ];

    const blocks: AuditBlock[] = [];
    let prev = GENESIS_PARENT_HASH;
    for (const b of rawBlocks) {
      b.previous_hash = prev;
      const hash = await computeAuditBlockHash(b);
      const fullBlock: AuditBlock = { ...b, block_hash: hash };
      blocks.push(fullBlock);
      prev = hash;
    }
    return blocks;
  }

  it("successfully verifies valid cryptographic hash chain using SHA-256", async () => {
    const blocks = await createValidChain();
    const result = await verifyAuditChain(blocks);
    expect(result.is_valid).toBe(true);
    expect(result.total_blocks).toBe(3);
    expect(result.verified_blocks).toBe(3);
    expect(result.broken_link_index).toBeUndefined();
  });

  it("detects tampered payload content even when previous_hash link is unchanged", async () => {
    const blocks = await createValidChain();
    // Tamper with payload_summary in block 2 without recomputing hash
    const tamperedBlocks: AuditBlock[] = [
      blocks[0]!,
      { ...blocks[1]!, payload_summary: "MALICIOUS INJECTION" },
      blocks[2]!,
    ];

    const result = await verifyAuditChain(tamperedBlocks);
    expect(result.is_valid).toBe(false);
    expect(result.broken_link_index).toBe(1);
    expect(result.error_message).toContain("Payload tamper detected at Block #2");
  });

  it("detects broken parent hash links", async () => {
    const blocks = await createValidChain();
    const brokenLinkBlocks: AuditBlock[] = [
      blocks[0]!,
      {
        ...blocks[1]!,
        previous_hash: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
      },
      blocks[2]!,
    ];

    const result = await verifyAuditChain(brokenLinkBlocks);
    expect(result.is_valid).toBe(false);
    expect(result.broken_link_index).toBe(1);
    expect(result.error_message).toContain("Hash chain broken at Block #2");
  });

  it("detects invalid genesis block missing 64-zero parent hash", async () => {
    const blocks = await createValidChain();
    const invalidGenesis: AuditBlock[] = [
      {
        ...blocks[0]!,
        previous_hash: "1111111111111111111111111111111111111111111111111111111111111111",
      },
      blocks[1]!,
      blocks[2]!,
    ];

    const result = await verifyAuditChain(invalidGenesis);
    expect(result.is_valid).toBe(false);
    expect(result.broken_link_index).toBe(0);
    expect(result.error_message).toContain("Invalid genesis block at Block #1");
  });

  it("detects sequence discontinuity (missing or reordered blocks)", async () => {
    const blocks = await createValidChain();
    // Discontinuous block_id (1, then 3 skipping 2)
    const reordered: AuditBlock[] = [blocks[0]!, blocks[2]!];

    const result = await verifyAuditChain(reordered);
    expect(result.is_valid).toBe(false);
    expect(result.broken_link_index).toBe(1);
    expect(result.error_message).toContain("Sequence discontinuity at index 1");
  });

  it("detects malformed non-hex hash format", async () => {
    const blocks = await createValidChain();
    const malformed: AuditBlock[] = [
      blocks[0]!,
      { ...blocks[1]!, block_hash: "not-a-valid-64-character-sha256-hex" },
      blocks[2]!,
    ];

    const result = await verifyAuditChain(malformed);
    expect(result.is_valid).toBe(false);
    expect(result.broken_link_index).toBe(1);
    expect(result.error_message).toContain("Malformed hash at Block #2");
  });

  it("handles empty audit chain safely", async () => {
    const result = await verifyAuditChain([]);
    expect(result.is_valid).toBe(true);
    expect(result.total_blocks).toBe(0);
    expect(result.verified_blocks).toBe(0);
  });

  it("filters audit blocks by status and query string", async () => {
    const blocks = await createValidChain();
    const filtered = filterAndSortAuditBlocks(blocks, "Appended rows", "all");
    expect(filtered).toHaveLength(1);
    expect(filtered[0]!.block_id).toBe(2);

    const rollbackBlocks = filterAndSortAuditBlocks(blocks, "", "ROLLED_BACK");
    expect(rollbackBlocks).toHaveLength(1);
    expect(rollbackBlocks[0]!.block_id).toBe(3);
  });
});
