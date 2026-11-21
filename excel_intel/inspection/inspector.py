"""Workbook Inspector Facade (M03).

Provides the unified, high-level inspection facade coordinating package structure,
sheet topology, streaming content profiling, and content-derived anomaly detection.
Generates immutable WorkbookInspectionReport and SheetInspectionReport data contracts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.inspection.anomaly_detector import ContentAnomalyDetector
from excel_intel.inspection.content_profiler import ContentDistributionProfiler
from excel_intel.inspection.models import (
    SheetInspectionReport,
    WorkbookInspectionReport,
)
from excel_intel.inspection.package_inspector import PackageStructureInspector
from excel_intel.inspection.topology_inspector import SheetTopologyInspector


class WorkbookInspector:
    """Unified facade orchestrating workbook and sheet inspection engines.

    Coordinates:
    - PackageStructureInspector (package metadata, defined names, calcPr)
    - SheetTopologyInspector (dimensions, merge cells, hidden rows/cols, OpenXML tables)
    - ContentDistributionProfiler (single-pass bounded-memory cell & column profiling)
    - ContentAnomalyDetector (content anomalies and heuristic region inference)

    Thread-safe and deterministic.
    """

    def __init__(
        self,
        target: Union[StreamingWorkbookReader, str, Path],
    ) -> None:
        """Initialize inspector with an existing reader or workbook file path.

        Args:
            target: StreamingWorkbookReader instance or path to workbook file.
        """
        if isinstance(target, StreamingWorkbookReader):
            self._reader = target
            self._owns_reader = False
        else:
            self._reader = StreamingWorkbookReader(target)
            self._owns_reader = True

        self._package_inspector = PackageStructureInspector(self._reader)
        self._topology_inspector = SheetTopologyInspector(self._reader)
        self._content_profiler = ContentDistributionProfiler(self._reader)
        self._anomaly_detector = ContentAnomalyDetector()

    def close(self) -> None:
        """Close reader if owned by this inspector instance."""
        if self._owns_reader and self._reader is not None:
            self._reader.close()

    def __enter__(self) -> WorkbookInspector:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    @property
    def reader(self) -> StreamingWorkbookReader:
        """Access underlying StreamingWorkbookReader."""
        return self._reader

    @classmethod
    def inspect(
        cls,
        target: Union[StreamingWorkbookReader, str, Path],
    ) -> WorkbookInspectionReport:
        """Inspect a workbook in a single self-closing invocation.

        Args:
            target: StreamingWorkbookReader instance or path to workbook file.

        Returns:
            Fully assembled WorkbookInspectionReport.
        """
        inspector = cls(target)
        try:
            return inspector.inspect_workbook()
        finally:
            inspector.close()

    def inspect_sheet(self, sheet: Union[str, int]) -> SheetInspectionReport:
        """Inspect a single worksheet's topology, content profile, and anomalies.

        Args:
            sheet: Sheet name (str) or 0-indexed position (int).

        Returns:
            SheetInspectionReport with deterministic facts, content profile,
            inferred region hypotheses, and detected anomalies.
        """
        # Resolve sheet name & index
        names = self._reader.sheet_names
        if isinstance(sheet, int):
            if sheet < 0 or sheet >= len(names):
                raise ValueError(
                    f"Sheet index {sheet} out of range (0..{len(names)-1})"
                )
            sheet_name = names[sheet]
            sheet_index = sheet
        else:
            sheet_name = str(sheet)
            if sheet_name not in names:
                raise ValueError(f"Sheet '{sheet_name}' not found in workbook")
            sheet_index = names.index(sheet_name)

        # 1. Topology & Declared OpenXML Facts
        facts, topo_anomalies = self._topology_inspector.inspect_topology(
            sheet_name
        )

        # 2. Bounded-Memory Streaming Content Profile
        profile = self._content_profiler.profile_sheet(sheet_name)
        blocks = self._content_profiler.get_candidate_blocks(sheet_name)

        # 3. Content-Derived Anomalies
        content_anomalies = self._anomaly_detector.detect_anomalies(
            sheet_name=sheet_name,
            profile=profile,
            facts=facts,
            blocks=blocks,
        )

        # 4. Inferred Region Hypotheses
        hypotheses = self._anomaly_detector.infer_region_hypotheses(
            sheet_name=sheet_name,
            profile=profile,
            facts=facts,
            blocks=blocks,
        )

        # Combine anomalies preserving discovery order
        combined_anomalies = list(topo_anomalies) + list(content_anomalies)

        return SheetInspectionReport(
            sheet_index=sheet_index,
            sheet_name=sheet_name,
            facts=facts,
            profile=profile,
            layout_classification=profile.layout_classification,
            region_hypotheses=hypotheses,
            anomalies=combined_anomalies,
            actual_cell_count=profile.populated_cell_count,
        )

    def inspect_workbook(self) -> WorkbookInspectionReport:
        """Perform complete inspection of the workbook package and all worksheets.

        Returns:
            Complete immutable WorkbookInspectionReport.
        """
        # 1. Package properties
        calc_pr = self._package_inspector.inspect_calc_pr()
        defined_names, pkg_anomalies = (
            self._package_inspector.inspect_defined_names(self._reader.sheet_names)
        )

        # 2. Inspect each sheet catalog entry
        catalog = self._package_inspector.inspect_sheet_catalog()
        sheet_reports: list[SheetInspectionReport] = []

        for sheet_prop in catalog:
            sheet_report = self.inspect_sheet(sheet_prop.name)
            sheet_reports.append(sheet_report)

        # 3. Timestamp in UTC ISO 8601
        timestamp = datetime.now(timezone.utc).isoformat()

        return WorkbookInspectionReport(
            workbook_path=str(self._reader.path),
            package_type=self._reader.package_type,
            is_1904=self._reader.is_1904,
            has_macros=self._reader.has_macros,
            calc_pr=calc_pr,
            defined_names=defined_names,
            sheets=sheet_reports,
            workbook_anomalies=pkg_anomalies,
            inspection_timestamp=timestamp,
        )
