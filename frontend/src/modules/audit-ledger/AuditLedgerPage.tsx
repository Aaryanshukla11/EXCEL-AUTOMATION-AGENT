import { ShieldAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { LoadingState } from "../../components/ui/LoadingState";
import { ErrorState } from "../../components/ui/ErrorState";
import { useAuditLedger } from "./useAuditLedger";
import { AuditChainVerificationBanner } from "./AuditChainVerificationBanner";
import { AuditFilterBar } from "./AuditFilterBar";
import { AuditLedgerTable } from "./AuditLedgerTable";
import { AuditBlockDetailModal } from "./AuditBlockDetailModal";

export function AuditLedgerPage() {
  const {
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
    verifyChain,
    reload,
  } = useAuditLedger();

  if (isLoading) {
    return <LoadingState message="Loading immutable audit blocks and verifying SHA-256 chain..." />;
  }

  if (error && blocks.length === 0) {
    return <ErrorState title="Failed to Load Audit Ledger" message={error} onRetry={reload} />;
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Audit Ledger & Lineage Explorer
            </h1>
            <Badge variant="outline" className="text-xs">
              Phase F5
            </Badge>
            <Badge variant="success" className="text-xs">
              SHA-256 PROVENANCE
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">
            Transparent compliance inspection of historical operations with cryptographic
            parent-hash chain integrity verification.
          </p>
        </div>
      </div>

      {/* Security Notice */}
      <Alert variant="info">
        <ShieldAlert className="h-5 w-5 text-primary" />
        <AlertTitle>Immutable Cryptographic Audit Trail</AlertTitle>
        <AlertDescription>
          Every committed workbook operation, spatial detection, and human approval decision is
          journaled into a hash-chained block. Broken links or out-of-order records immediately
          trigger integrity warnings.
        </AlertDescription>
      </Alert>

      {/* Chain Verification Status Banner */}
      <AuditChainVerificationBanner
        result={verificationResult}
        isVerifying={isVerifying}
        onVerify={verifyChain}
      />

      {/* Filters */}
      <AuditFilterBar
        filters={filters}
        onFilterChange={(updated) => setFilters((prev) => ({ ...prev, ...updated }))}
        totalCount={filteredBlocks.length}
      />

      {/* Audit Blocks Table */}
      <AuditLedgerTable
        blocks={filteredBlocks}
        selectedBlockId={selectedBlock?.block_id || null}
        onSelectBlock={setSelectedBlock}
      />

      {/* Block Inspector Modal */}
      {selectedBlock && (
        <AuditBlockDetailModal block={selectedBlock} onClose={() => setSelectedBlock(null)} />
      )}
    </div>
  );
}
