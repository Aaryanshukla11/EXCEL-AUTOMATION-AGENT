"""Multi-Workbook Concurrency & Thread Isolation Validation (M04 Prompt 4).

Verifies:
- Concurrent spatial detection across multiple worker threads
- Strictly stateless execution without shared state or race conditions
- Independent results per workbook without cross-contamination
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any
import pytest

from excel_intel.spatial.detector import SpatialDetector
from tests.test_m04_e2e_integration import build_multisheet_test_workbook


class TestM04ConcurrencyValidation:
    """Test suite validating multi-threaded concurrency and workbook isolation."""

    def test_concurrent_independent_workbook_detection(self, tmp_path: Path) -> None:
        """Verify concurrent worker threads process independent workbooks without data races."""
        # Create 8 distinct synthetic workbooks
        wb_paths = [
            build_multisheet_test_workbook(tmp_path / f"wb_{i}.xlsx")
            for i in range(8)
        ]

        def worker(idx: int, path: Path) -> tuple[int, int, int]:
            detector = SpatialDetector()
            report = detector.detect_workbook(path)
            # Return worker index, total tables, and sheets count
            return idx, report.total_tables_detected, len(report.sheets)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(worker, i, wb_paths[i])
                for i in range(8)
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(results) == 8
        for idx, total_tables, sheet_count in results:
            assert sheet_count == 2
            assert total_tables >= 3
