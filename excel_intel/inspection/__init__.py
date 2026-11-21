"""Workbook Inspection & Structural Analysis Subsystem (M03).

Provides domain-agnostic discovery and modeling of Excel workbook structures,
declared OpenXML facts, sheet topologies, content distributions, structural anomalies,
and candidate region hypotheses.
"""

from __future__ import annotations

from excel_intel.inspection.anomaly_detector import ContentAnomalyDetector
from excel_intel.inspection.content_profiler import ContentDistributionProfiler
from excel_intel.inspection.inspector import WorkbookInspector
from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    ColumnProfile,
    DeclaredDefinedName,
    DeclaredListObject,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
    EvidenceCode,
    HiddenInterval,
    InferredRegionHypothesis,
    LayoutClassification,
    RegionHypothesis,
    RegionRole,
    RegionType,
    SheetContentProfile,
    SheetInspectionReport,
    SheetVisibility,
    StructuralAnomaly,
    WorkbookInspectionReport,
    cell_ref_to_row_col,
    col_index_to_letter,
    col_letter_to_index,
    row_col_to_cell_ref,
)
from excel_intel.inspection.package_inspector import PackageStructureInspector
from excel_intel.inspection.topology_inspector import (
    SheetTopologyInspector,
    consolidate_intervals,
)

__all__ = [
    "AnomalySeverity",
    "BoundingBox",
    "ColumnProfile",
    "ContentAnomalyDetector",
    "ContentDistributionProfiler",
    "DeclaredDefinedName",
    "DeclaredListObject",
    "DeclaredMergeCell",
    "DeclaredOpenXmlFacts",
    "DeclaredSheetProperties",
    "EvidenceCode",
    "HiddenInterval",
    "InferredRegionHypothesis",
    "LayoutClassification",
    "PackageStructureInspector",
    "RegionHypothesis",
    "RegionRole",
    "RegionType",
    "SheetContentProfile",
    "SheetInspectionReport",
    "SheetTopologyInspector",
    "SheetVisibility",
    "StructuralAnomaly",
    "WorkbookInspectionReport",
    "WorkbookInspector",
    "cell_ref_to_row_col",
    "col_index_to_letter",
    "col_letter_to_index",
    "consolidate_intervals",
    "row_col_to_cell_ref",
]
