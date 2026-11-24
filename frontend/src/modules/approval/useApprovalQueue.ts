import * as React from "react";
import type {
  ApprovalFilterState,
  ApprovalRequest,
  DecisionSubmitPayload,
  RevisionSubmitPayload,
} from "./approvalTypes";
import { filterAndSortApprovalRequests } from "./approvalStateMachine";
import { approvalAdapter } from "./approvalAdapter";
import { ApiError } from "../../api/client";

function formatApprovalError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return "Version Conflict (409): This approval request was updated concurrently or state changed. Please reload to inspect the latest state.";
    }
    if (err.status === 401) {
      return "Authentication Required (401): Session expired or missing credentials. Please re-authenticate.";
    }
    if (err.status === 403) {
      const body = err.body as { detail?: string } | undefined;
      return body?.detail || "Authorization Denied (403): You lack permission or Two-Man Rule prohibits approving your own submission.";
    }
    if (err.status === 404) {
      return "Not Found (404): The approval request was not found or belongs to another tenant.";
    }
    if (err.status === 410) {
      return "Expired (410): The approval request deadline has expired and can no longer be modified.";
    }
    const body = err.body as { detail?: string } | undefined;
    if (body?.detail) {
      return body.detail;
    }
  }
  return err instanceof Error ? err.message : fallback;
}

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
      setError(formatApprovalError(err, "Failed to load approval requests."));
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
      setError(null);
      try {
        const updated = await approvalAdapter.submitDecision({
          ...payload,
          requestId: selectedRequestId,
        });
        setRequests((prev) => prev.map((r) => (r.request_id === updated.request_id ? updated : r)));
      } catch (err) {
        const msg = formatApprovalError(err, "Failed to submit decision.");
        setError(msg);
        throw err;
      }
    },
    [selectedRequestId]
  );

  const handleRevision = React.useCallback(
    async (payload: RevisionSubmitPayload) => {
      if (!selectedRequestId) return;
      setError(null);
      try {
        const updated = await approvalAdapter.reviseRequest({
          ...payload,
          requestId: selectedRequestId,
        });
        setRequests((prev) => prev.map((r) => (r.request_id === updated.request_id ? updated : r)));
      } catch (err) {
        const msg = formatApprovalError(err, "Failed to revise request.");
        setError(msg);
        throw err;
      }
    },
    [selectedRequestId]
  );

  const handleCancel = React.useCallback(
    async (rationale?: string) => {
      if (!selectedRequest) return;
      setError(null);
      try {
        const updated = await approvalAdapter.cancelRequest({
          requestId: selectedRequest.request_id,
          target_version: selectedRequest.version,
          rationale,
        });
        setRequests((prev) => prev.map((r) => (r.request_id === updated.request_id ? updated : r)));
      } catch (err) {
        const msg = formatApprovalError(err, "Failed to cancel request.");
        setError(msg);
        throw err;
      }
    },
    [selectedRequest]
  );

  const handleSubmitForReview = React.useCallback(async () => {
    if (!selectedRequest) return;
    setError(null);
    try {
      const updated = await approvalAdapter.submitForReview({
        requestId: selectedRequest.request_id,
        target_version: selectedRequest.version,
      });
      setRequests((prev) => prev.map((r) => (r.request_id === updated.request_id ? updated : r)));
    } catch (err) {
      const msg = formatApprovalError(err, "Failed to submit request for review.");
      setError(msg);
      throw err;
    }
  }, [selectedRequest]);

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
    handleCancel,
    handleSubmitForReview,
  };
}
