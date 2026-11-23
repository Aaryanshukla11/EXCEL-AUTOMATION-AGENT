"""Discovery and Semantic Manifest Service (Milestone B3).

Coordinates:
- Workbook structural inspection (M03 WorkbookInspector).
- Spatial table region and semantic zone detection (M04 SpatialDetector).
- Semantic type inference (M05 TypeInferenceEngine).
- Formula calculation dependency graph analysis (M05 FormulaDependencyGraph).
- Canonical DiscoveryManifest assembly (M01 / M05 build_discovery_manifest).

Enforces:
- Strict path sanitization (never exposing physical host paths in API responses).
- Domain-agnostic processing reusing deterministic core algorithms without duplication.
- Multi-tier safety and memory limits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence
import uuid

from fastapi import HTTPException, status

from excel_intel.adapters.manifest_adapter import build_discovery_manifest
from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.core.types import DiscoveryManifest
from excel_intel.formulas.graph import (
    FormulaDependencyGraph,
    FormulaGraphReport,
    _canonical_cell_id,
)
from excel_intel.inspection.inspector import WorkbookInspector
from excel_intel.inspection.models import DeclaredOpenXmlFacts, WorkbookInspectionReport
from excel_intel.logging import StructuredLogger, get_logger
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.models import (
    SpatialAnalysisReport,
    SpatialDetectionReport,
    SpatialTableRegion,
)
from excel_intel.types.models import RegionTypeReport, SamplingDiagnostics
from excel_intel.types.type_inferrer import TypeInferenceEngine

logger: StructuredLogger = get_logger("DiscoveryService")


class DiscoveryService:
    """Orchestrates workbook inspection, spatial discovery, type inference, and manifest synthesis."""

    def __init__(
        self,
        *,
        spatial_detector: Optional[SpatialDetector] = None,
        type_inferrer: Optional[TypeInferenceEngine] = None,
    ) -> None:
        self.spatial_detector = spatial_detector or SpatialDetector()
        self.type_inferrer = type_inferrer or TypeInferenceEngine()

    def inspect_workbook(
        self,
        file_path: Path,
        sanitized_filename: str,
    ) -> WorkbookInspectionReport:
        """Runs M03 inspection facade and sanitizes storage paths from response."""
        with StreamingWorkbookReader(file_path) as reader:
            inspector = WorkbookInspector(reader)
            report = inspector.inspect_workbook()

        # Sanitize internal filesystem paths before returning to client
        return report.model_copy(update={"workbook_path": sanitized_filename})

    def detect_sheet_spatial(
        self,
        file_path: Path,
        sheet_name: str,
        sanitized_filename: str,
    ) -> list[SpatialTableRegion]:
        """Runs M04 spatial detection on a single worksheet."""
        with StreamingWorkbookReader(file_path) as reader:
            if sheet_name not in reader.sheet_names:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sheet '{sheet_name}' was not found in workbook.",
                )

            # Retrieve declared facts via M03 inspector
            inspector = WorkbookInspector(reader)
            sheet_inspection = inspector.inspect_sheet(sheet_name)
            facts = sheet_inspection.facts

            # Execute spatial detection
            detection_report = self.spatial_detector.detect_sheet(
                reader=reader,
                sheet_name=sheet_name,
                facts=facts,
            )

        return detection_report.regions

    def infer_sheet_types(
        self,
        file_path: Path,
        sheet_name: str,
        region_id: Optional[str] = None,
    ) -> RegionTypeReport:
        """Runs M05 semantic type inference on detected table regions of a worksheet."""
        with StreamingWorkbookReader(file_path) as reader:
            if sheet_name not in reader.sheet_names:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Sheet '{sheet_name}' was not found in workbook.",
                )

            # Retrieve declared facts and detect regions
            inspector = WorkbookInspector(reader)
            sheet_inspection = inspector.inspect_sheet(sheet_name)
            facts = sheet_inspection.facts

            detection_report = self.spatial_detector.detect_sheet(
                reader=reader,
                sheet_name=sheet_name,
                facts=facts,
            )

            if not detection_report.regions:
                # Return empty RegionTypeReport if sheet has no detected tabular regions
                return RegionTypeReport(
                    region_id=f"{sheet_name}_empty",
                    sheet_name=sheet_name,
                    body_row_start=1,
                    body_row_end=1,
                    body_col_start=1,
                    body_col_end=1,
                    columns={},
                    has_ambiguous_columns=False,
                    sampling=SamplingDiagnostics(
                        total_rows=0,
                        total_cols=0,
                        sampled_rows=0,
                        sampled_cols=0,
                        sampled_cells=0,
                        is_truncated=False,
                        truncation_details=None,
                        merged_cell_count=0,
                    ),
                    is_tentative=False,
                )

            # Infer column types for regions
            reports = self.type_inferrer.infer_sheet(
                reader=reader,
                sheet_name=sheet_name,
                table_regions=detection_report.regions,
                facts=facts,
            )

        if region_id:
            for rep in reports:
                if rep.region_id == region_id:
                    return rep
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Region '{region_id}' was not found on sheet '{sheet_name}'.",
            )

        # Default to primary region
        return reports[0]

    def analyze_formulas(
        self,
        file_path: Path,
    ) -> FormulaGraphReport:
        """Constructs calculation dependency graph across all worksheets and executes cycle/dependency analysis."""
        with StreamingWorkbookReader(file_path) as reader:
            inspector = WorkbookInspector(reader)
            inspection_rep = inspector.inspect_workbook()

            defined_names_map: dict[str, Any] = {}
            for dn in inspection_rep.defined_names:
                if dn.sheet_name:
                    if dn.sheet_name not in defined_names_map:
                        defined_names_map[dn.sheet_name] = {}
                    defined_names_map[dn.sheet_name][dn.name] = dn.target
                else:
                    defined_names_map[dn.name] = dn.target

            graph = FormulaDependencyGraph(defined_names=defined_names_map)
            for sheet_name in reader.sheet_names:
                for chunk in reader.stream_sheet(sheet_name, chunk_size=1000):
                    for row_record in chunk:
                        row_idx = row_record["row"]
                        for cell in row_record["cells"]:
                            formula = cell.get("formula")
                            if formula:
                                col_idx = cell["col"]
                                cell_id = _canonical_cell_id(sheet_name, col_idx, row_idx)
                                graph.add_formula(cell_id, formula)

            return graph.analyze()

    def generate_manifest(
        self,
        file_path: Path,
        sanitized_filename: str,
        sha256: str,
        file_size_bytes: int,
    ) -> DiscoveryManifest:
        """Synthesizes root canonical DiscoveryManifest combining M03, M04, and M05."""
        with StreamingWorkbookReader(file_path) as reader:
            # 1. Structural inspection & facts extraction
            inspector = WorkbookInspector(reader)
            inspection_rep = inspector.inspect_workbook()
            facts_by_sheet: dict[str, DeclaredOpenXmlFacts] = {
                s.sheet_name: s.facts for s in inspection_rep.sheets
            }

            # 2. Spatial detection across all sheets
            spatial_analysis = self.spatial_detector.detect_workbook(
                reader,
                facts_by_sheet=facts_by_sheet,
            )

            # 3. Type inference across all detected regions
            type_reports: dict[str, RegionTypeReport] = {}
            valid_table_regions: list[SpatialTableRegion] = []

            for sheet_name, sheet_rep in spatial_analysis.sheets.items():
                sheet_facts = facts_by_sheet.get(sheet_name)
                reports = self.type_inferrer.infer_sheet(
                    reader=reader,
                    sheet_name=sheet_name,
                    table_regions=sheet_rep.regions,
                    facts=sheet_facts,
                )
                for r in reports:
                    type_reports[r.region_id] = r

                # Filter regions that possess resolved headers suitable for TableMetadata
                for reg in sheet_rep.regions:
                    if reg.header_row is not None and reg.header_resolution is not None:
                        valid_table_regions.append(reg)

            # 4. Formula dependency graph extraction
            # Pass workbook and sheet-scoped defined names to graph
            defined_names_map: dict[str, Any] = {}
            for dn in inspection_rep.defined_names:
                if dn.sheet_name:
                    if dn.sheet_name not in defined_names_map:
                        defined_names_map[dn.sheet_name] = {}
                    defined_names_map[dn.sheet_name][dn.name] = dn.target
                else:
                    defined_names_map[dn.name] = dn.target

            graph = FormulaDependencyGraph(defined_names=defined_names_map)
            for sheet_name in reader.sheet_names:
                for chunk in reader.stream_sheet(sheet_name, chunk_size=1000):
                    for row_record in chunk:
                        row_idx = row_record["row"]
                        for cell in row_record["cells"]:
                            formula = cell.get("formula")
                            if formula:
                                col_idx = cell["col"]
                                cell_id = _canonical_cell_id(sheet_name, col_idx, row_idx)
                                graph.add_formula(cell_id, formula)

            formula_graph_report = graph.analyze()

        # 5. Assemble canonical DiscoveryManifest
        combined_detection = SpatialDetectionReport(
            workbook_path=sanitized_filename,
            sheet_name="all",
            regions=valid_table_regions,
            detection_timestamp=inspection_rep.inspection_timestamp,
        )

        manifest = build_discovery_manifest(
            workbook_path=sanitized_filename,
            sha256=sha256,
            file_size_bytes=file_size_bytes,
            detection_report=combined_detection,
            region_type_reports=type_reports,
            formula_graph_report=formula_graph_report,
            manifest_id=uuid.uuid4(),
        )

        logger.info(
            "DiscoveryManifestGenerated",
            message=f"Synthesized discovery manifest for {sanitized_filename}",
            context={
                "sha256": sha256,
                "table_count": len(manifest.tables),
                "formula_nodes": manifest.formula_graph.node_count,
                "has_cycles": manifest.formula_graph.has_cycles,
            },
        )

        return manifest
