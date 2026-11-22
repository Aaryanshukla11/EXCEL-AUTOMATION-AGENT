"""Unified Spatial Detection Facade (M04).

Orchestrates 2D whitespace corridor grid segmentation, hierarchical header resolution,
semantic zone classification, and ADR-005 append boundary sentinel evaluation.
Provides high-level APIs for worksheet and workbook spatial analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from excel_intel.inspection.models import BoundingBox, DeclaredOpenXmlFacts
from excel_intel.spatial.boundary_sentinel import BoundarySentinel
from excel_intel.spatial.grid_segmenter import GridSegmenter
from excel_intel.spatial.header_resolver import HeaderResolver
from excel_intel.spatial.models import (
    MarginClearance,
    SemanticZoneType,
    SpatialAnalysisReport,
    SpatialDetectionReport,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialTableRegion,
)
from excel_intel.spatial.zone_classifier import ZoneClassifier

if TYPE_CHECKING:
    from excel_intel.core.parser import StreamingWorkbookReader
    from excel_intel.core.types import TableMetadata


class SpatialDetector:
    """Unified facade orchestrating the complete M04 spatial detection pipeline."""

    def __init__(
        self,
        *,
        segmenter: Optional[GridSegmenter] = None,
        header_resolver: Optional[HeaderResolver] = None,
        zone_classifier: Optional[ZoneClassifier] = None,
        boundary_sentinel: Optional[BoundarySentinel] = None,
    ) -> None:
        """Initialize SpatialDetector with configurable subsystem engines."""
        self.segmenter = segmenter or GridSegmenter()
        self.header_resolver = header_resolver or HeaderResolver()
        self.zone_classifier = zone_classifier or ZoneClassifier()
        self.boundary_sentinel = boundary_sentinel or BoundarySentinel()

    def detect_sheet(
        self,
        reader: StreamingWorkbookReader,
        sheet_name: str,
        facts: Optional[DeclaredOpenXmlFacts] = None,
    ) -> SpatialDetectionReport:
        """Perform end-to-end spatial detection on a single worksheet.

        Orchestrates:
        1. 2D whitespace corridor segmentation & island clustering.
        2. Multi-row hierarchical header resolution.
        3. Semantic zone decomposition (Title, Header, Body, Summary, Totals, Footnotes).
        4. ADR-005 boundary collision detection & margin clearance analysis.
        5. Cross-boundary merge conflict detection and region overlap checks.

        Args:
            reader: StreamingWorkbookReader instance.
            sheet_name: Target sheet name.
            facts: Optional DeclaredOpenXmlFacts from M03 inspection.

        Returns:
            Fully enriched SpatialDetectionReport.
        """
        # Step 1: Initial 2D grid segmentation
        initial_report = self.segmenter.segment_sheet(reader, sheet_name, facts=facts)

        merge_cells = facts.merge_cells if facts else []
        list_objects = facts.list_objects if facts else []

        # Step 2 & 3 & 4: Process each detected table region
        enriched_regions: list[SpatialTableRegion] = []

        for region in initial_report.regions:
            # Step 2: Hierarchical header resolution
            # Resolve headers using bounded lookahead stream
            hdr_reports = self.header_resolver.resolve_sheet(
                reader,
                sheet_name,
                [region],
                merge_cells=merge_cells,
                list_objects=list_objects,
            )
            hdr_rep = hdr_reports[0] if hdr_reports else None

            # Attach resolved headers to region
            reg_with_hdr = region.model_copy(
                update={
                    "header_row": hdr_rep.header_row_start if hdr_rep else None,
                    "header_resolution": hdr_rep,
                }
            )

            # Step 3: Semantic zone decomposition
            # Stream rows to decompose into Title, Header, Body, Summary, Totals, Footnotes
            classified_reg = self.zone_classifier.classify_region(
                reg_with_hdr,
                reader.stream_sheet(sheet_name),
                header_report=hdr_rep,
                merge_cells=merge_cells,
                list_objects=list_objects,
            )

            # Step 4: ADR-005 append boundary margin evaluation
            final_reg = self.boundary_sentinel.attach_margin_clearance(
                classified_reg,
                reader.stream_sheet(sheet_name),
                facts=facts,
                other_regions=initial_report.regions,
            )

            # Step 5a: Cross-boundary merge cell conflict detection (FR-5.2)
            if merge_cells:
                for mc in merge_cells:
                    mc_box = mc.box
                    intersects = mc_box.intersects(final_reg.bounding_box)
                    if intersects:
                        # Check if merge cell is completely contained
                        r_box = final_reg.bounding_box
                        is_contained = (
                            r_box.min_row <= mc_box.min_row
                            and r_box.max_row >= mc_box.max_row
                            and r_box.min_col <= mc_box.min_col
                            and r_box.max_col >= mc_box.max_col
                        )
                        if not is_contained:
                            # Cross-boundary merge detected!
                            cb_ev = SpatialEvidence(
                                evidence_type=SpatialEvidenceType.CROSS_BOUNDARY_MERGE,
                                description=(
                                    f"Merge range {mc.ref} straddles region boundary "
                                    f"({r_box.to_a1_ref()}). Risk of data truncation."
                                ),
                                heuristic_score=0.90,
                                provenance="excel_intel.spatial.detector",
                                coordinates=mc_box,
                            )
                            final_reg = final_reg.model_copy(
                                update={"evidence": list(final_reg.evidence) + [cb_ev]}
                            )

            enriched_regions.append(final_reg)

        # Step 5b: Inter-region overlap detection (FR-5.1)
        for i, reg_a in enumerate(enriched_regions):
            overlapping_ids: list[str] = []
            overlap_evs: list[SpatialEvidence] = []
            for j, reg_b in enumerate(enriched_regions):
                if i != j and reg_a.bounding_box.intersects(reg_b.bounding_box):
                    overlapping_ids.append(reg_b.region_id)
                    overlap_box = BoundingBox(
                        min_row=max(reg_a.bounding_box.min_row, reg_b.bounding_box.min_row),
                        max_row=min(reg_a.bounding_box.max_row, reg_b.bounding_box.max_row),
                        min_col=max(reg_a.bounding_box.min_col, reg_b.bounding_box.min_col),
                        max_col=min(reg_a.bounding_box.max_col, reg_b.bounding_box.max_col),
                    )
                    overlap_evs.append(
                        SpatialEvidence(
                            evidence_type=SpatialEvidenceType.OVERLAPPING_REGION_WARNING,
                            description=f"Region coordinates overlap with region '{reg_b.region_id}'.",
                            heuristic_score=0.85,
                            provenance="excel_intel.spatial.detector",
                            coordinates=overlap_box,
                        )
                    )
            if overlapping_ids:
                enriched_regions[i] = reg_a.model_copy(
                    update={
                        "overlapping_region_ids": overlapping_ids,
                        "evidence": list(reg_a.evidence) + overlap_evs,
                    }
                )

        return initial_report.model_copy(update={"regions": enriched_regions})

    def detect_workbook(
        self,
        reader_or_path: Union[str, Path, StreamingWorkbookReader],
        facts_by_sheet: Optional[dict[str, DeclaredOpenXmlFacts]] = None,
    ) -> SpatialAnalysisReport:
        """Perform spatial detection across all sheets in a workbook."""
        from excel_intel.core.parser import StreamingWorkbookReader

        if isinstance(reader_or_path, (str, Path)):
            reader = StreamingWorkbookReader(reader_or_path)
            workbook_path_str = str(reader_or_path)
        else:
            reader = reader_or_path
            workbook_path_str = str(reader.path)

        sheets_dict: dict[str, SpatialDetectionReport] = {}
        total_tables = 0
        total_islands = 0
        has_collisions = False
        anomalies: list[dict[str, Any]] = []

        for sheet_name in reader.sheet_names:
            sheet_facts = facts_by_sheet.get(sheet_name) if facts_by_sheet else None
            sheet_report = self.detect_sheet(reader, sheet_name, sheet_facts)
            sheets_dict[sheet_name] = sheet_report
            total_tables += len(sheet_report.regions)
            total_islands += len(sheet_report.sparse_islands)

            for reg in sheet_report.regions:
                if reg.margin and not reg.margin.safe_for_append:
                    has_collisions = True
                    anomalies.append({
                        "sheet_name": sheet_name,
                        "region_id": reg.region_id,
                        "reason": reg.margin.collision_reason,
                        "spare_rows_below": reg.margin.spare_rows_below,
                    })

        return SpatialAnalysisReport(
            workbook_path=workbook_path_str,
            sheets=sheets_dict,
            total_tables_detected=total_tables,
            total_sparse_islands=total_islands,
            has_boundary_collisions=has_collisions,
            boundary_anomalies=anomalies,
        )

    def export_to_table_metadata_list(
        self,
        detection_report: SpatialDetectionReport,
        inferred_types_by_region: dict[str, dict[int, Any]],
    ) -> list[TableMetadata]:
        """Losslessly convert detected regions to canonical M01 TableMetadata.

        Args:
            detection_report: SpatialDetectionReport containing detected tables.
            inferred_types_by_region: Verified column types mapped by region_id and column index.

        Returns:
            List of canonical M01 TableMetadata objects.

        Raises:
            NotImplementedError: If verified types are missing for any detected table.
        """
        table_meta_list = []
        for reg in detection_report.regions:
            if reg.region_id not in inferred_types_by_region:
                raise NotImplementedError(
                    f"Region '{reg.region_id}' requires verified column types for TableMetadata conversion."
                )
            verified_types = inferred_types_by_region[reg.region_id]
            if reg.header_resolution:
                col_metas = reg.header_resolution.to_column_metadata_list(verified_types)
                reg_with_cols = reg.model_copy(update={"columns": col_metas})
                table_meta_list.append(reg_with_cols.to_table_metadata())
            else:
                raise NotImplementedError(
                    f"Region '{reg.region_id}' lacks header resolution report."
                )
        return table_meta_list
