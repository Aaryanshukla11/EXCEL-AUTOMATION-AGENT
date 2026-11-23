import * as React from "react";
import type { AuditBlock, AuditChainVerificationResult, AuditFilterState } from "./auditTypes";
import { filterAndSortAuditBlocks, verifyAuditChain } from "./auditLedgerUtils";
import { auditAdapter } from "./auditAdapter";

export function useAuditLedger(initialBlocks?: readonly AuditBlock[]) {
  const [blocks, setBlocks] = React.useState<readonly AuditBlock[]>(initialBlocks || []);
  const [selectedBlock, setSelectedBlock] = React.useState<AuditBlock | null>(null);
  const [isLoading, setIsLoading] = React.useState(!initialBlocks);
  const [isVerifying, setIsVerifying] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [verificationResult, setVerificationResult] =
    React.useState<AuditChainVerificationResult | null>(null);

  const [filters, setFilters] = React.useState<AuditFilterState>({
    search: "",
    status: "all",
    actor: "all",
    operationType: "all",
    sortBy: "block_id",
    sortAsc: true,
  });

  const loadBlocks = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await auditAdapter.getAuditBlocks();
      setBlocks(data);
      // Automatically verify chain on initial load using actual SHA-256
      const res = await verifyAuditChain(data);
      setVerificationResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit blocks.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!initialBlocks) {
      void loadBlocks();
    } else {
      void verifyAuditChain(initialBlocks).then(setVerificationResult);
    }
  }, [initialBlocks, loadBlocks]);

  const handleManualVerify = React.useCallback(async () => {
    setIsVerifying(true);
    try {
      const res = await auditAdapter.verifyChain();
      setVerificationResult(res);
    } finally {
      setIsVerifying(false);
    }
  }, []);

  const filteredBlocks = React.useMemo(() => {
    return filterAndSortAuditBlocks(
      blocks,
      filters.search,
      filters.status,
      filters.actor,
      filters.operationType,
      filters.sortBy,
      filters.sortAsc
    );
  }, [blocks, filters]);

  return {
    blocks,
    filteredBlocks,
    selectedBlock,
    setSelectedBlock,
    filters,
    setFilters,
    isLoading,
    isVerifying,
    error,
    verificationResult,
    verifyChain: handleManualVerify,
    reload: loadBlocks,
  };
}
