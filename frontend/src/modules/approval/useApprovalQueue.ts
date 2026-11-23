import * as React from "react";
import type {
  ApprovalFilterState,
  ApprovalRequest,
  DecisionSubmitPayload,
  RevisionSubmitPayload,
} from "./approvalTypes";
import { filterAndSortApprovalRequests } from "./approvalStateMachine";
import { approvalAdapter } from "./approvalAdapter";

export function useApprovalQueue(initialRequests?: readonly ApprovalRequest[]) {
  const [requests, setRequests] = React.useState<readonly ApprovalRequest[]>(initialRequests || []);
  const [selectedRequestId, setSelectedRequestId] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(!initialRequests);
  const [error, setError] = React.useState<string | null>(null);

  const [filters, setFilters] = React.useState<ApprovalFilterState>({
    search: "",
    state: "all",
    riskCategory: "all",
    riskLevel: "all",
    sortBy: "created_at",
    sortAsc: false,
  });

  const loadRequests = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await approvalAdapter.getRequests();
      setRequests(data);
      setSelectedRequestId((prev) => (prev ? prev : data.length > 0 ? data[0]!.request_id : null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load approval requests.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!initialRequests) {
      void loadRequests();
    } else {
      setSelectedRequestId((prev) =>
        prev ? prev : initialRequests.length > 0 ? initialRequests[0]!.request_id : null
      );
    }
  }, [initialRequests, loadRequests]);

  const filteredRequests = React.useMemo(() => {
    return filterAndSortApprovalRequests(
      requests,
      filters.search,
      filters.state,
      filters.riskCategory,
      filters.riskLevel,
      filters.sortBy,
      filters.sortAsc
    );
  }, [requests, filters]);

  const selectedRequest = React.useMemo(() => {
    return requests.find((r) => r.request_id === selectedRequestId) || null;
  }, [requests, selectedRequestId]);

  const handleDecision = React.useCallback(
    async (payload: DecisionSubmitPayload) => {
      if (!selectedRequestId) return;
      try {
        const updated = await approvalAdapter.submitDecision({
          ...payload,
          requestId: selectedRequestId,
        });
        setRequests((prev) => prev.map((r) => (r.request_id === updated.request_id ? updated : r)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit decision.");
        throw err;
      }
    },
    [selectedRequestId]
  );

  const handleRevision = React.useCallback(
    async (payload: RevisionSubmitPayload) => {
      if (!selectedRequestId) return;
      try {
        const updated = await approvalAdapter.reviseRequest({
          ...payload,
          requestId: selectedRequestId,
        });
        setRequests((prev) => prev.map((r) => (r.request_id === updated.request_id ? updated : r)));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to revise request.");
        throw err;
      }
    },
    [selectedRequestId]
  );

  return {
    requests,
    filteredRequests,
    selectedRequest,
    selectedRequestId,
    setSelectedRequestId,
    filters,
    setFilters,
    isLoading,
    error,
    reload: loadRequests,
    handleDecision,
    handleRevision,
  };
}
