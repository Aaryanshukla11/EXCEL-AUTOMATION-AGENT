"""Quality Audit and Finding Aggregation Service (Milestone B4).

Consolidates deterministic findings across:
1. Structural anomalies (M03 WorkbookInspector + ContentAnomalyDetector).
2. Spatial boundary and margin anomalies (M04 SpatialDetector + BoundarySentinel).
3. Column type ambiguities and unverified states (M05 TypeInferenceEngine).
4. Calculation cycles, unsupported formulas, unresolved dependencies, volatile functions,
   and dynamic array spills (M05 FormulaDependencyGraph).

Conforms strictly to FRONTEND_BACKEND_API_CONTRACT.md Section 3.4.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional, Sequence
import uuid

from pydantic import BaseModel, ConfigDict, Field

from excel_intel.core.parser import StreamingWorkbookReader
from excel_intel.formulas.graph import (
    FormulaDependencyGraph,
    FormulaGraphReport,
    _canonical_cell_id,
)
from excel_intel.inspection.inspector import WorkbookInspector
from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    DeclaredOpenXmlFacts,
    StructuralAnomaly,
    WorkbookInspectionReport,
)
from excel_intel.logging import StructuredLogger, get_logger
from excel_intel.server.services.discovery_service import DiscoveryService
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.models import (
    SemanticZoneType,
    SpatialAnalysisReport,
    SpatialTableRegion,
)
from excel_intel.types.models import ColumnTypeProfile, InferenceState, RegionTypeReport
from excel_intel.types.type_inferrer import TypeInferenceEngine

logger: StructuredLogger = get_logger("QualityService")


class QualityFindingCategory(str, Enum):
    """Categorization of data quality and integrity findings."""

    STRUCTURAL_ANOMALY = "structural_anomaly"
    TYPE_AMBIGUITY = "type_ambiguity"
    FORMULA_CYCLE = "formula_cycle"
    UNSUPPORTED_FORMULA = "unsupported_formula"
    UNRESOLVED_DEPENDENCY = "unresolved_dependency"
    VOLATILE_FUNCTION = "volatile_function"
    DYNAMIC_SPILL = "dynamic_spill"


class QualityFinding(BaseModel):
    """Evidence-backed data quality finding."""

    finding_id: str = Field(description="Unique finding identifier")
    category: QualityFindingCategory = Field(description="Finding category")
    severity: AnomalySeverity = Field(description="Finding severity ('info' | 'warning' | 'critical')")
    code: str = Field(description="Machine-readable diagnostic code")
    message: str = Field(description="Human-readable explanation of the finding")
    workbook_path: Optional[str] = Field(default=None, description="Sanitized workbook filename")
    sheet_name: Optional[str] = Field(default=None, description="Target worksheet name if applicable")
    cell_ref: Optional[str] = Field(default=None, description="A1-style cell reference if applicable")
    region_id: Optional[str] = Field(default=None, description="Spatial table region ID if applicable")
    box: Optional[BoundingBox] = Field(default=None, description="Bounding coordinates if applicable")
    column_index: Optional[int] = Field(default=None, description="1-indexed column number if applicable")
    column_name: Optional[str] = Field(default=None, description="Resolved column header name if applicable")
    confidence: Optional[float] = Field(default=None, description="Detection confidence score in [0.0, 1.0]")
    detection_source: str = Field(description="Subsystem provenance (e.g. M03_INSPECTION, M04_SPATIAL, M05_TYPE_INFERENCE, M05_FORMULA_GRAPH)")
    evidence: Optional[str] = Field(default=None, description="Underlying structural evidence summary")
    details: Optional[dict[str, Any]] = Field(default=None, description="Additional context parameters")

    model_config = ConfigDict(frozen=True)


class QualityAuditReport(BaseModel):
    """Consolidated workbook data quality audit report."""

    report_id: str = Field(description="Unique report execution identifier (UUID)")
    workbook_path: str = Field(description="Sanitized workbook filename")
    total_findings: int = Field(ge=0, description="Total count of quality findings")
    findings: list[QualityFinding] = Field(default_factory=list, description="Ordered collection of quality findings")
    formula_graph: Optional[FormulaGraphReport] = Field(default=None, description="Associated calculation graph analysis")
    is_mock_fixture: bool = Field(default=False, description="Flag indicating mock test data vs real audit")

    model_config = ConfigDict(frozen=True)


class QualityService:
    """Consolidates findings across M03 inspection, M04 spatial detection, and M05 formulas/types."""

    def __init__(
        self,
        *,
        discovery_service: Optional[DiscoveryService] = None,
    ) -> None:
        self.discovery_service = discovery_service or DiscoveryService()

    def audit_workbook_quality(
        self,
        file_path: Path,
        sanitized_filename: str,
    ) -> QualityAuditReport:
        """Executes full quality triage across all four core intelligence modules."""
        findings: list[QualityFinding] = []

        with StreamingWorkbookReader(file_path) as reader:
            # 1. M03 Inspection anomalies
            inspector = WorkbookInspector(reader)
            inspection_rep = inspector.inspect_workbook()
            facts_by_sheet = {s.sheet_name: s.facts for s in inspection_rep.sheets}

            # Top-level workbook anomalies
            for anom in inspection_rep.workbook_anomalies:
                findings.append(
                    QualityFinding(
                        finding_id=f"wb_anom_{uuid.uuid4().hex[:8]}",
                        category=QualityFindingCategory.STRUCTURAL_ANOMALY,
                        severity=anom.severity,
                        code=anom.code,
                        message=anom.message,
                        workbook_path=sanitized_filename,
                        cell_ref=anom.cell_ref,
                        box=anom.box,
                        detection_source="M03_INSPECTION",
                        evidence=anom.evidence,
                    )
                )

            # Sheet-level inspection anomalies
            for sheet in inspection_rep.sheets:
                for anom in sheet.anomalies:
                    findings.append(
                        QualityFinding(
                            finding_id=f"sheet_anom_{uuid.uuid4().hex[:8]}",
                            category=QualityFindingCategory.STRUCTURAL_ANOMALY,
                            severity=anom.severity,
                            code=anom.code,
                            message=anom.message,
                            workbook_path=sanitized_filename,
                            sheet_name=sheet.sheet_name,
                            cell_ref=anom.cell_ref,
                            box=anom.box,
                            detection_source="M03_INSPECTION",
                            evidence=anom.evidence,
                        )
                    )

            # 2. M04 Spatial boundary & margin collisions
            spatial_detector = self.discovery_service.spatial_detector
            spatial_analysis = spatial_detector.detect_workbook(reader, facts_by_sheet=facts_by_sheet)

            for sheet_name, sheet_rep in spatial_analysis.sheets.items():
                for reg in sheet_rep.regions:
                    # Margin append safety collisions
                    if reg.margin and not reg.margin.safe_for_append:
                        findings.append(
                            QualityFinding(
                                finding_id=f"margin_{uuid.uuid4().hex[:8]}",
                                category=QualityFindingCategory.STRUCTURAL_ANOMALY,
                                severity=AnomalySeverity.WARNING,
                                code="MARGIN_APPEND_COLLISION",
                                message=reg.margin.collision_reason or "Boundary clearance violation: unsafe for row append.",
                                workbook_path=sanitized_filename,
                                sheet_name=sheet_name,
                                region_id=reg.region_id,
                                box=reg.bounding_box,
                                detection_source="M04_SPATIAL_DETECTOR",
                                details={
                                    "spare_rows_below": reg.margin.spare_rows_below,
                                    "adjacent_formulas": list(reg.margin.adjacent_formulas),
                                },
                            )
                        )

            # 3. M05 Semantic type inference ambiguities & review requirements
            type_inferrer = self.discovery_service.type_inferrer
            for sheet_name, sheet_rep in spatial_analysis.sheets.items():
                sheet_facts = facts_by_sheet.get(sheet_name)
                type_reports = type_inferrer.infer_sheet(
                    reader=reader,
                    sheet_name=sheet_name,
                    table_regions=sheet_rep.regions,
                    facts=sheet_facts,
                )
                for type_rep in type_reports:
                    for col_idx, profile in type_rep.columns.items():
                        if profile.is_ambiguous or profile.requires_human_review or profile.state in (InferenceState.AMBIGUOUS, InferenceState.UNKNOWN):
                            col_header = None
                            # Match header name if region has resolved headers
                            target_reg = next((r for r in sheet_rep.regions if r.region_id == type_rep.region_id), None)
                            if target_reg and target_reg.header_resolution:
                                matched_col = next((c for c in target_reg.header_resolution.columns if c.col_index == col_idx), None)
                                if matched_col:
                                    col_header = matched_col.disambiguated_name or matched_col.resolved_name

                            findings.append(
                                QualityFinding(
                                    finding_id=f"type_{uuid.uuid4().hex[:8]}",
                                    category=QualityFindingCategory.TYPE_AMBIGUITY,
                                    severity=AnomalySeverity.WARNING if profile.is_ambiguous else AnomalySeverity.INFO,
                                    code=f"TYPE_{profile.state.value}",
                                    message=profile.ambiguity_reason or f"Column {col_idx} has ambiguous or unverified semantic type ({profile.inferred_type.value}).",
                                    workbook_path=sanitized_filename,
                                    sheet_name=sheet_name,
                                    region_id=type_rep.region_id,
                                    column_index=col_idx,
                                    column_name=col_header,
                                    confidence=profile.heuristic_support_score,
                                    detection_source="M05_TYPE_INFERRER",
                                    details={
                                        "inferred_type": profile.inferred_type.value,
                                        "nullability_ratio": profile.nullability_ratio,
                                        "populated_cells": profile.populated_cells,
                                        "total_cells": profile.total_cells,
                                    },
                                )
                            )

            # 4. M05 Formula graph calculation findings
            formula_graph_report = self.discovery_service.analyze_formulas(file_path)

            # 4a. Circular calculation cycles
            if formula_graph_report.has_cycles:
                for path in formula_graph_report.circular_paths:
                    findings.append(
                        QualityFinding(
                            finding_id=f"cycle_{uuid.uuid4().hex[:8]}",
                            category=QualityFindingCategory.FORMULA_CYCLE,
                            severity=AnomalySeverity.CRITICAL,
                            code="CIRCULAR_REFERENCE_CYCLE",
                            message=f"Circular calculation dependency cycle detected: {' -> '.join(path)}",
                            workbook_path=sanitized_filename,
                            cell_ref=path[0] if path else None,
                            detection_source="M05_FORMULA_GRAPH",
                            evidence=f"Cycle path length: {len(path)} cells",
                            details={"cycle_path": path},
                        )
                    )

            # 4b. Unsupported formula syntax
            for cell_id in formula_graph_report.unsupported_cells:
                sheet = cell_id.split("!")[0] if "!" in cell_id else None
                cell = cell_id.split("!")[1] if "!" in cell_id else cell_id
                findings.append(
                    QualityFinding(
                        finding_id=f"unsup_{uuid.uuid4().hex[:8]}",
                        category=QualityFindingCategory.UNSUPPORTED_FORMULA,
                        severity=AnomalySeverity.WARNING,
                        code="UNSUPPORTED_FORMULA_SYNTAX",
                        message=f"Formula at {cell_id} contains unsupported Excel functions or syntax constructs.",
                        workbook_path=sanitized_filename,
                        sheet_name=sheet,
                        cell_ref=cell,
                        detection_source="M05_FORMULA_GRAPH",
                    )
                )

            # 4c. Unparsed formula errors
            for cell_id in formula_graph_report.unparsed_cells:
                sheet = cell_id.split("!")[0] if "!" in cell_id else None
                cell = cell_id.split("!")[1] if "!" in cell_id else cell_id
                findings.append(
                    QualityFinding(
                        finding_id=f"unparsed_{uuid.uuid4().hex[:8]}",
                        category=QualityFindingCategory.UNSUPPORTED_FORMULA,
                        severity=AnomalySeverity.WARNING,
                        code="UNPARSED_FORMULA_SYNTAX",
                        message=f"Formula at {cell_id} failed lexical or AST parsing.",
                        workbook_path=sanitized_filename,
                        sheet_name=sheet,
                        cell_ref=cell,
                        detection_source="M05_FORMULA_GRAPH",
                    )
                )

            # 4d. Unresolved dependencies
            for dep in formula_graph_report.unresolved_dependencies:
                findings.append(
                    QualityFinding(
                        finding_id=f"unres_{uuid.uuid4().hex[:8]}",
                        category=QualityFindingCategory.UNRESOLVED_DEPENDENCY,
                        severity=AnomalySeverity.WARNING,
                        code="UNRESOLVED_DEPENDENCY",
                        message=f"Calculation dependency target '{dep}' could not be resolved within the workbook scope.",
                        workbook_path=sanitized_filename,
                        cell_ref=dep if "!" in dep else None,
                        detection_source="M05_FORMULA_GRAPH",
                    )
                )

            # 4e. Volatile functions
            for cell_id in formula_graph_report.volatile_cells:
                sheet = cell_id.split("!")[0] if "!" in cell_id else None
                cell = cell_id.split("!")[1] if "!" in cell_id else cell_id
                findings.append(
                    QualityFinding(
                        finding_id=f"vol_{uuid.uuid4().hex[:8]}",
                        category=QualityFindingCategory.VOLATILE_FUNCTION,
                        severity=AnomalySeverity.INFO,
                        code="VOLATILE_FUNCTION_CALL",
                        message=f"Formula at {cell_id} invokes a volatile function recalculated on every workbook change.",
                        workbook_path=sanitized_filename,
                        sheet_name=sheet,
                        cell_ref=cell,
                        detection_source="M05_FORMULA_GRAPH",
                    )
                )

            # 4f. Dynamic spills
            if formula_graph_report.has_dynamic_spills:
                findings.append(
                    QualityFinding(
                        finding_id=f"spill_{uuid.uuid4().hex[:8]}",
                        category=QualityFindingCategory.DYNAMIC_SPILL,
                        severity=AnomalySeverity.INFO,
                        code="DYNAMIC_SPILL_REFERENCES",
                        message="Calculation graph contains dynamic array spill references (#).",
                        workbook_path=sanitized_filename,
                        detection_source="M05_FORMULA_GRAPH",
                    )
                )

        report = QualityAuditReport(
            report_id=str(uuid.uuid4()),
            workbook_path=sanitized_filename,
            total_findings=len(findings),
            findings=findings,
            formula_graph=formula_graph_report,
            is_mock_fixture=False,
        )

        logger.info(
            "QualityAuditCompleted",
            message=f"Quality audit completed for {sanitized_filename}: {len(findings)} findings",
            context={
                "total_findings": len(findings),
                "has_cycles": formula_graph_report.has_cycles,
                "node_count": formula_graph_report.node_count,
            },
        )

        return report
