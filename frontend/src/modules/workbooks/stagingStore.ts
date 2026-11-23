import * as React from "react";
import type {
  DiscoveryStatus,
  StagedWorkbook,
  ValidationStatus,
  WorkbookFormat,
} from "./workbookTypes";

const MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024; // 250 MiB process limit

function detectFormat(filename: string): WorkbookFormat {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".xlsx")) return "xlsx";
  if (lower.endsWith(".xlsm")) return "xlsm";
  return "unsupported";
}

/**
 * In-Memory Staging Store Hook.
 * Enforces memory-only file storage (never writes sensitive File objects to disk/storage).
 */
export function useStagingStore() {
  const [stagedFiles, setStagedFiles] = React.useState<StagedWorkbook[]>([]);

  const addFiles = React.useCallback((incomingFiles: FileList | File[]) => {
    const fileArray = Array.from(incomingFiles);

    setStagedFiles((prev) => {
      const updated = [...prev];

      for (const file of fileArray) {
        const format = detectFormat(file.name);
        const errors: string[] = [];
        let status: ValidationStatus = "valid";

        if (format === "unsupported") {
          status = "unsupported_format";
          errors.push(
            `Unsupported format for '${file.name}'. Only OpenXML formats (.xlsx, .xlsm) are supported.`
          );
        } else if (file.size > MAX_FILE_SIZE_BYTES) {
          status = "size_exceeded";
          errors.push(
            `File size (${(file.size / 1024 / 1024).toFixed(1)} MiB) exceeds the 250 MiB process ceiling.`
          );
        }

        // Duplicate check
        const isDuplicate = prev.some(
          (existing) =>
            existing.name === file.name &&
            existing.sizeBytes === file.size &&
            existing.lastModified === file.lastModified
        );

        if (isDuplicate && status === "valid") {
          status = "duplicate";
          errors.push(`Workbook '${file.name}' is already present in the staging queue.`);
        }

        const newStaged: StagedWorkbook = {
          id: `staged_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
          file,
          name: file.name,
          sizeBytes: file.size,
          format,
          lastModified: file.lastModified,
          validationStatus: status,
          validationErrors: errors,
          discoveryStatus: "not_started",
          stagedAt: new Date().toISOString(),
        };

        updated.push(newStaged);
      }

      return updated;
    });
  }, []);

  const removeWorkbook = React.useCallback((id: string) => {
    setStagedFiles((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearQueue = React.useCallback(() => {
    setStagedFiles([]);
  }, []);

  const setDiscoveryStatus = React.useCallback((id: string, status: DiscoveryStatus) => {
    setStagedFiles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, discoveryStatus: status } : item))
    );
  }, []);

  return {
    stagedFiles,
    addFiles,
    removeWorkbook,
    clearQueue,
    setDiscoveryStatus,
  };
}
