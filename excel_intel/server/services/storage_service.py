"""Secure streaming storage service for workbook staging.

Enforces:
1. Streaming multipart ingestion in 64 KiB chunks (strict O(1) memory footprint).
2. Continuous on-the-fly SHA-256 fingerprinting.
3. 250 MiB file upload size ceiling.
4. Magic bytes validation (PK\x03\x04 required; legacy OLE .xls rejected).
5. ZIP central directory traversal defense (rejecting `..`, absolute paths).
6. Rust streaming engine verification (ZipPackageReader decompression ratio and quota guards).
7. Server-generated storage filenames with atomic move completion.
8. Ephemeral file cleanup via try...finally.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import hashlib
import os
from pathlib import Path
from typing import Any, Optional
import uuid
import zipfile

from fastapi import UploadFile

from excel_intel._rs import (
    CorruptWorkbookError as RustCorruptWorkbookError,
    ParserError as RustParserError,
    PlatformResourceLimitError as RustResourceLimitError,
    UnsupportedFormatError as RustUnsupportedFormatError,
)
from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.exceptions import (
    PlatformError,
    PlatformResourceLimitError,
    UnsupportedFormatError,
)
from excel_intel.logging import StructuredLogger, get_logger

logger: StructuredLogger = get_logger("StorageService")

# Signatures
_ZIP_LOCAL_HEADER = b"PK\x03\x04"
_OLE_HEADER = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
_DEFAULT_MAX_UPLOAD_BYTES = 250 * 1024 * 1024  # 250 MiB


class CorruptWorkbookError(PlatformError):
    """Raised when an uploaded workbook is malformed, truncated, or structurally corrupt."""

    exit_code = 400
    category = "ERR_CORRUPT_WORKBOOK"


class ZipBombError(PlatformError):
    """Raised when an archive exceeds decompression ratio or uncompressed byte ceilings."""

    exit_code = 400
    category = "ERR_ZIP_BOMB"


@dataclass(frozen=True)
class StagedWorkbookMetadata:
    """Immutable metadata describing a successfully staged workbook."""

    workbook_id: str
    filename: str
    file_size_bytes: int
    sha256: str
    package_type: str  # "xlsx" | "xlsm"
    has_macros: bool
    is_1904: bool
    sheet_count: int
    sheet_names: list[str]
    storage_path: str  # Relative storage path
    staged_at: datetime.datetime


class StorageService:
    """Manages physical file staging, validation, and lifecycle."""

    def __init__(
        self,
        storage_root: Path,
        max_upload_bytes: int = _DEFAULT_MAX_UPLOAD_BYTES,
    ) -> None:
        self._storage_root = Path(storage_root).resolve()
        self._staging_dir = self._storage_root / "staging"
        self._staging_dir.mkdir(parents=True, exist_ok=True)
        self._max_upload_bytes = max_upload_bytes

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    @property
    def staging_dir(self) -> Path:
        return self._staging_dir

    def _get_tenant_staging_dir(self, tenant_id: str) -> Path:
        """Returns the isolated staging directory for a specific tenant."""
        # Sanitize tenant_id to prevent directory traversal
        safe_tenant = "".join(c for c in tenant_id if c.isalnum() or c in ("-", "_")) or "default"
        tenant_dir = (self._staging_dir / safe_tenant).resolve()
        if not str(tenant_dir).startswith(str(self._staging_dir)):
            raise PlatformError("Invalid tenant identifier", exit_code=400)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir

    async def store_uploaded_workbook(
        self,
        file: UploadFile,
        tenant_id: str = "default",
    ) -> StagedWorkbookMetadata:
        """Streams, validates, and stages an uploaded Excel workbook."""
        tenant_dir = self._get_tenant_staging_dir(tenant_id)
        temp_filename = f".tmp_upload_{uuid.uuid4().hex}"
        temp_path = tenant_dir / temp_filename

        hasher = hashlib.sha256()
        total_bytes = 0
        header_bytes = b""
        chunk_size = 64 * 1024  # 64 KiB chunks

        # 1. Stream file directly to temporary file
        try:
            with open(temp_path, "wb") as f_out:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break

                    total_bytes += len(chunk)
                    if total_bytes > self._max_upload_bytes:
                        raise PlatformResourceLimitError(
                            f"Uploaded file exceeds maximum permitted size of {self._max_upload_bytes // (1024*1024)} MiB.",
                            exit_code=413,
                            context={"max_bytes": self._max_upload_bytes, "uploaded_bytes": total_bytes},
                        )

                    if len(header_bytes) < 8:
                        needed = 8 - len(header_bytes)
                        header_bytes += chunk[:needed]

                    hasher.update(chunk)
                    f_out.write(chunk)

                f_out.flush()
                os.fsync(f_out.fileno())

            if total_bytes == 0:
                raise CorruptWorkbookError("Uploaded workbook file is empty (0 bytes).")

            # 2. Magic-byte inspection
            if len(header_bytes) >= 8 and header_bytes[:8] == _OLE_HEADER:
                raise UnsupportedFormatError(
                    "Unsupported legacy binary format (.xls / OLE Compound File). Please convert to OpenXML (.xlsx or .xlsm).",
                    exit_code=400,
                )

            if len(header_bytes) < 4 or header_bytes[:4] != _ZIP_LOCAL_HEADER:
                raise UnsupportedFormatError(
                    "Invalid workbook file signature. Expected OpenXML PK zip container.",
                    exit_code=400,
                )

            # 3. Archive member path traversal and member quota check
            try:
                with zipfile.ZipFile(temp_path, "r") as zf:
                    infolist = zf.infolist()
                    if len(infolist) > 10000:
                        raise ZipBombError(
                            f"ZIP archive member count ({len(infolist)}) exceeds safety ceiling of 10,000 entries."
                        )

                    total_uncompressed = 0
                    for member in infolist:
                        name = member.filename
                        if ".." in name or name.startswith("/") or name.startswith("\\"):
                            raise CorruptWorkbookError(
                                f"Unsafe archive member path detected: {name}"
                            )

                        total_uncompressed += member.file_size
                        if member.file_size > 10 * 1024 * 1024 and member.compress_size > 0:
                            ratio = member.file_size / member.compress_size
                            if ratio > 10.0:
                                raise ZipBombError(
                                    f"Decompression ratio ({ratio:.1f}x) exceeds safety limit of 10.0x."
                                )

                    if total_uncompressed > 1_073_741_824:  # 1.0 GiB
                        raise ZipBombError(
                            f"Cumulative uncompressed size ({total_uncompressed} bytes) exceeds 1.0 GiB quota."
                        )
            except zipfile.BadZipFile as e:
                raise CorruptWorkbookError(f"Malformed or truncated ZIP archive: {e}") from e

            # 4. Deep structural & decompression ratio verification via Rust core
            try:
                with StreamingWorkbookReader(temp_path) as reader:
                    sheet_names = list(reader.sheet_names)
                    has_macros = bool(reader.has_macros)
                    is_1904 = bool(reader.is_1904)
            except RustResourceLimitError as e:
                err_str = str(e)
                if "ratio" in err_str.lower() or "bomb" in err_str.lower() or "decompression" in err_str.lower():
                    raise ZipBombError(f"Decompression bomb detected: {err_str}") from e
                raise PlatformResourceLimitError(err_str, exit_code=422) from e
            except RustUnsupportedFormatError as e:
                raise UnsupportedFormatError(str(e), exit_code=400) from e
            except (RustCorruptWorkbookError, RustParserError) as e:
                raise CorruptWorkbookError(f"Corrupt or invalid OpenXML workbook: {e}") from e

            # 5. Atomic placement in tenant storage
            workbook_id = f"wb-{uuid.uuid4()}"
            package_type = "xlsm" if has_macros else "xlsx"
            final_filename = f"{workbook_id}.{package_type}"
            final_path = tenant_dir / final_filename

            # Atomic rename
            os.replace(temp_path, final_path)

            # Compute relative storage reference for persistence
            storage_rel = str(final_path.relative_to(self._storage_root)).replace("\\", "/")

            raw_client_filename = Path(file.filename or "workbook.xlsx").name
            clean_filename = raw_client_filename if raw_client_filename else f"workbook.{package_type}"

            staged_at = datetime.datetime.now(datetime.timezone.utc)

            logger.info(
                "WorkbookStagedSuccessfully",
                message=f"Workbook staged successfully: {clean_filename} as {workbook_id}",
                context={
                    "workbook_id": workbook_id,
                    "filename": clean_filename,
                    "file_size_bytes": total_bytes,
                    "package_type": package_type,
                    "sheet_count": len(sheet_names),
                    "tenant_id": tenant_id,
                },
            )

            return StagedWorkbookMetadata(
                workbook_id=workbook_id,
                filename=clean_filename,
                file_size_bytes=total_bytes,
                sha256=hasher.hexdigest(),
                package_type=package_type,
                has_macros=has_macros,
                is_1904=is_1904,
                sheet_count=len(sheet_names),
                sheet_names=sheet_names,
                storage_path=storage_rel,
                staged_at=staged_at,
            )

        finally:
            # Ephemeral cleanup in case of any failure prior to os.replace
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def delete_staged_file(self, storage_rel_path: str) -> None:
        """Safely removes a staged workbook file from disk."""
        target_path = (self._storage_root / storage_rel_path).resolve()
        # Path traversal guard
        if not str(target_path).startswith(str(self._staging_dir)):
            raise PlatformError("Unauthorized file deletion path", exit_code=403)

        if target_path.exists():
            target_path.unlink()
            logger.info(
                "StagedFileDeleted",
                message=f"Physical file deleted: {storage_rel_path}",
                context={"storage_path": storage_rel_path},
            )
