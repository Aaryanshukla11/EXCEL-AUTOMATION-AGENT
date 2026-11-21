"""Compatibility re-export shim for canonical excel_intel.core.parser.

Maintains backward compatibility across import conventions while ensuring
a single canonical parser implementation in excel_intel.core.parser.
"""

from excel_intel.core.parser import (
    CorruptWorkbookError,
    DateOutOfRangeError,
    ParserError,
    PlatformResourceLimitError,
    StreamingWorkbookReader,
    UnsupportedFormatError,
    parse_excel_serial,
    validate_cell_string,
)

__all__ = [
    "CorruptWorkbookError",
    "DateOutOfRangeError",
    "ParserError",
    "PlatformResourceLimitError",
    "StreamingWorkbookReader",
    "UnsupportedFormatError",
    "parse_excel_serial",
    "validate_cell_string",
]
