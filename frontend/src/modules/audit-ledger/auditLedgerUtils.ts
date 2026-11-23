import type { AuditBlock, AuditBlockStatus, AuditChainVerificationResult } from "./auditTypes";

export const GENESIS_PARENT_HASH =
  "0000000000000000000000000000000000000000000000000000000000000000";

const HEX_64_REGEX = /^[0-9a-f]{64}$/i;

/**
 * Computes canonical string representation of an audit block for SHA-256 hashing.
 */
export function getCanonicalBlockPayload(block: Omit<AuditBlock, "block_hash">): string {
  return [
    block.block_id,
    block.timestamp,
    block.previous_hash,
    block.actor,
    block.operation_type,
    block.target_workbook,
    block.target_sheet,
    block.target_range,
    block.payload_summary,
  ].join("|");
}

/**
 * Computes standard SHA-256 digest over canonical representation of an audit block using Web Crypto.
 */
export async function computeAuditBlockHash(
  block: Omit<AuditBlock, "block_hash">
): Promise<string> {
  const canonical = getCanonicalBlockPayload(block);
  const buffer = new TextEncoder().encode(canonical);
  const hashBuffer = await globalThis.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export interface VerifyChainOptions {
  /**
   * Whether to recompute cryptographic SHA-256 digests for each block payload.
   * Defaults to true.
   */
  verifyPayloadHashes?: boolean;
}

/**
 * Validates the cryptographic parent hash chain across a sequential list of audit blocks.
 * Enforces:
 * 1. 64-character lowercase hex hash syntax.
 * 2. Genesis block anchors (block_id = 1, previous_hash = 64 zeros).
 * 3. Monotonic sequential block_id continuity without gaps or duplicates.
 * 4. Child-to-parent previous_hash linkage.
 * 5. Full cryptographic recomputation of payload SHA-256 digest against block_hash (when verifyPayloadHashes is true).
 */
export async function verifyAuditChain(
  blocks: readonly AuditBlock[],
  options: VerifyChainOptions = { verifyPayloadHashes: true }
): Promise<AuditChainVerificationResult> {
  const now = new Date().toISOString();

  if (blocks.length === 0) {
    return {
      is_valid: true,
      total_blocks: 0,
      verified_blocks: 0,
      checked_at: now,
    };
  }

  // Phase 1: Structural & Chain-Link Validation
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i]!;

    // 1. Format check
    if (!HEX_64_REGEX.test(block.block_hash)) {
      return {
        is_valid: false,
        total_blocks: blocks.length,
        verified_blocks: i,
        broken_link_index: i,
        error_message: `Malformed hash at Block #${block.block_id}: block_hash must be a 64-character hex string.`,
        checked_at: now,
      };
    }

    // 2. Genesis block check
    if (i === 0) {
      if (block.block_id !== 1 || block.previous_hash !== GENESIS_PARENT_HASH) {
        return {
          is_valid: false,
          total_blocks: blocks.length,
          verified_blocks: 0,
          broken_link_index: 0,
          error_message: `Invalid genesis block at Block #${block.block_id}: genesis block must have block_id = 1 and 64-zero parent hash.`,
          checked_at: now,
        };
      }
    } else {
      const prevBlock = blocks[i - 1]!;

      // 3. Monotonic block_id check
      if (block.block_id !== prevBlock.block_id + 1) {
        return {
          is_valid: false,
          total_blocks: blocks.length,
          verified_blocks: i,
          broken_link_index: i,
          error_message: `Sequence discontinuity at index ${i}: expected block_id ${prevBlock.block_id + 1}, found ${block.block_id}.`,
          checked_at: now,
        };
      }

      // 4. Parent hash linkage
      if (block.previous_hash !== prevBlock.block_hash) {
        return {
          is_valid: false,
          total_blocks: blocks.length,
          verified_blocks: i,
          broken_link_index: i,
          error_message: `Hash chain broken at Block #${block.block_id}: previous_hash does not match parent Block #${prevBlock.block_id} hash.`,
          checked_at: now,
        };
      }
    }
  }

  // Phase 2: Cryptographic Payload Recomputation (if enabled)
  if (options.verifyPayloadHashes !== false) {
    const computedHashes = await Promise.all(blocks.map((block) => computeAuditBlockHash(block)));

    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i]!;
      const expectedHash = computedHashes[i]!;
      if (block.block_hash.toLowerCase() !== expectedHash.toLowerCase()) {
        return {
          is_valid: false,
          total_blocks: blocks.length,
          verified_blocks: i,
          broken_link_index: i,
          error_message: `Payload tamper detected at Block #${block.block_id}: computed SHA-256 hash does not match recorded block_hash.`,
          checked_at: now,
        };
      }
    }
  }

  return {
    is_valid: true,
    total_blocks: blocks.length,
    verified_blocks: blocks.length,
    checked_at: now,
  };
}

/**
 * Filter and sort audit blocks in memory.
 */
export function filterAndSortAuditBlocks(
  blocks: readonly AuditBlock[],
  search: string,
  statusFilter: AuditBlockStatus | "all",
  actorFilter = "all",
  opTypeFilter = "all",
  sortBy: "block_id" | "timestamp" = "block_id",
  sortAsc = false
): AuditBlock[] {
  const query = search.trim().toLowerCase();
  const hasQuery = query.length > 0;

  return blocks
    .filter((b) => {
      if (statusFilter !== "all" && b.status !== statusFilter) return false;
      if (actorFilter !== "all" && b.actor !== actorFilter) return false;
      if (opTypeFilter !== "all" && b.operation_type !== opTypeFilter) return false;

      if (!hasQuery) return true;

      return (
        b.block_hash.toLowerCase().includes(query) ||
        b.actor.toLowerCase().includes(query) ||
        b.operation_type.toLowerCase().includes(query) ||
        b.target_workbook.toLowerCase().includes(query) ||
        b.payload_summary.toLowerCase().includes(query)
      );
    })
    .sort((a, b) => {
      let comp = 0;
      if (sortBy === "block_id") {
        comp = a.block_id - b.block_id;
      } else if (sortBy === "timestamp") {
        comp = a.timestamp < b.timestamp ? -1 : a.timestamp > b.timestamp ? 1 : 0;
      }
      return sortAsc ? comp : -comp;
    });
}
