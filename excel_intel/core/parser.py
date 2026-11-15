"""High-performance streaming OpenXML Excel parser interface (M02).

Exposes streaming workbook ingestion powered by the compiled Rust _rs extension.
Enforces domain-agnostic tabular ingestion with bounded memory consumption.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator, Iterator, Optional, Union

from excel_intel._rs import (
    CorruptWorkbookError,
    DateOutOfRangeError,
    ParserError,
    PlatformResourceLimitError,
    SheetChunkIterator,
    UnsupportedFormatError,
    WorkbookStreamReader as _NativeReader,
    py_parse_excel_serial,
    py_validate_cell_string,
)


class StreamingWorkbookReader:
    """Domain-agnostic streaming workbook reader with bounded memory complexity."""

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.path = Path(file_path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"Workbook file not found: {self.path}")
        self._native = _NativeReader(str(self.path))

    @property
    def sheet_names(self) -> list[str]:
        """List of human-readable sheet names in workbook order."""
        return self._native.get_sheet_names()

    @property
    def is_1904(self) -> bool:
        """True if the workbook uses the 1904 date system."""
        return self._native.is_1904_system()

    @property
    def has_macros(self) -> bool:
        """True if workbook contains VBA macros (.xlsm)."""
        return self._native.has_macros()

    @property
    def package_type(self) -> str:
        """Type of the package container: 'xlsx' or 'xlsm'."""
        return "xlsm" if self._native.has_macros() else "xlsx"

    def inspect(self) -> dict[str, Any]:
        """Inspect workbook metadata without streaming worksheets."""
        return self._native.inspect()

    def stream_sheet(
        self,
        sheet: Union[str, int] = 0,
        *,
        chunk_size: int = 1000,
    ) -> Iterator[list[dict[str, Any]]]:
        """Stream worksheet rows in discrete chunk batches without materializing the sheet.

        Args:
            sheet: Sheet name (str) or 0-indexed sheet position (int).
            chunk_size: Number of row records to yield per batch (default 1000).

        Yields:
            Lists of row records: [{'row': int, 'cells': [{'col': int, 'value': Any, 'formula': Optional[str]}]}]
        """
        iterator: SheetChunkIterator = self._native.stream_sheet(sheet, chunk_size)
        for chunk in iterator:
            yield chunk


def parse_excel_serial(serial: float, *, is_1904: bool = False) -> Any:
    """Convert an Excel numeric serial into a Python datetime, date, or time object.

    Follows piecewise Lotus 1-2-3 defect semantics for the 1900 date system
    and independent calendar arithmetic for the 1904 system.
    """
    return py_parse_excel_serial(serial, is_1904)


def validate_cell_string(text: str) -> None:
    """Validate cell text against Excel's 32,767 UTF-16 code units and 131,072 byte safety limits."""
    py_validate_cell_string(text)


__all__ = [
    "StreamingWorkbookReader",
    "parse_excel_serial",
    "validate_cell_string",
    "ParserError",
    "PlatformResourceLimitError",
    "DateOutOfRangeError",
    "CorruptWorkbookError",
    "UnsupportedFormatError",
]
