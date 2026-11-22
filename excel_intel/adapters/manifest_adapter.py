"""Canonical DiscoveryManifest Synthesis Adapter for M05 (FR-6).

Synthesizes the root M01 DiscoveryManifest by losslessly combining verified semantic
type profiles from M05 Prompt 2, detected spatial table boundaries from M04, and
static formula dependency graph metadata from M05 Prompt 4.
"""

from __future__ import annotations

from typing import Optional
import uuid

from excel_intel.core.types import DiscoveryManifest, FormulaGraphMetadata, TableMetadata
from excel_intel.formulas.graph import FormulaGraphReport
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.models import SpatialDetectionReport
from excel_intel.types.models import RegionTypeReport


def build_discovery_manifest(
    workbook_path: str,
    sha256: str,
    file_size_bytes: int,
    detection_report: SpatialDetectionReport,
    region_type_reports: dict[str, RegionTypeReport],
    formula_graph_report: FormulaGraphReport,
    manifest_id: Optional[uuid.UUID] = None,
) -> DiscoveryManifest:
    """Assemble root canonical M01 DiscoveryManifest via downstream integration adapter.

    Args:
        workbook_path: Absolute or canonical path of the inspected spreadsheet.
        sha256: 64-character SHA-256 hex digest of the spreadsheet file.
        file_size_bytes: Size of the spreadsheet file in bytes.
        detection_report: Spatial table detection report from M04.
        region_type_reports: Dictionary mapping region_id to M05 RegionTypeReport.
        formula_graph_report: Formula calculation graph report from M05 Prompt 4.
        manifest_id: Optional UUID identifier; generated if omitted.

    Returns:
        Canonical M01 DiscoveryManifest data model instance.

    Raises:
        ValueError: If SHA-256 is invalid or verified types are missing.
        NotImplementedError: If M04 export fails due to unverified column types.
    """
    if len(sha256) != 64:
        raise ValueError(f"sha256 must be exactly 64 hexadecimal characters (got {len(sha256)})")

    # 1. Convert M05 RegionTypeReports to verified column types mapping
    inferred_types_by_region = {
        region_id: report.to_m01_inferred_types()
        for region_id, report in region_type_reports.items()
    }

    # 2. Bridge to M04 export_to_table_metadata_list (FR-6.1)
    spatial_detector = SpatialDetector()
    tables: list[TableMetadata] = spatial_detector.export_to_table_metadata_list(
        detection_report=detection_report,
        inferred_types_by_region=inferred_types_by_region,
    )

    # 3. Project FormulaGraphReport to M01 FormulaGraphMetadata (FR-6.2)
    formula_graph_meta: FormulaGraphMetadata = formula_graph_report.to_formula_graph_metadata()

    # 4. Assemble root DiscoveryManifest
    return DiscoveryManifest(
        manifest_id=manifest_id or uuid.uuid4(),
        workbook_path=workbook_path,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        tables=tables,
        formula_graph=formula_graph_meta,
    )
