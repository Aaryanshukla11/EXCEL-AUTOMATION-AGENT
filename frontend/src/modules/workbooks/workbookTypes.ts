export type WorkbookFormat = "xlsx" | "xlsm" | "unsupported";

export type ValidationStatus = "valid" | "duplicate" | "unsupported_format" | "size_exceeded";

export type DiscoveryStatus =
  "not_started" | "in_progress" | "completed" | "completed_with_warnings" | "failed";

export interface StagedWorkbook {
  readonly id: string;
  readonly file: File;
  readonly name: string;
  readonly sizeBytes: number;
  readonly format: WorkbookFormat;
  readonly lastModified: number;
  readonly validationStatus: ValidationStatus;
  readonly validationErrors: readonly string[];
  readonly discoveryStatus: DiscoveryStatus;
  readonly stagedAt: string;
}

export interface WorkbookInventoryItem {
  readonly id: string;
  readonly name: string;
  readonly format: string;
  readonly sizeBytes: number;
  readonly sheetCount: number;
  readonly discoveryStatus: DiscoveryStatus;
  readonly source: "memory_staged" | "backend_fixture";
  readonly lastActivity: string;
}
