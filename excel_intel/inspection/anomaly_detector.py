"""Generic Content-Level Anomaly Detection & Region Inference Engine (M03).

Detects content-derived anomalies (type competition, jagged structures, blank gaps,
formula inconsistencies, understated dimensions) and generates heuristic region hypotheses
using the approved weighted scoring formula.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    DeclaredOpenXmlFacts,
    EvidenceCode,
    InferredRegionHypothesis,
    RegionRole,
    RegionType,
    SheetContentProfile,
    StructuralAnomaly,
)

if TYPE_CHECKING:
    from excel_intel.inspection.content_profiler import PopulatedBlock

MAX_ANOMALIES_PER_SHEET = 500
MAX_HYPOTHESES_PER_SHEET = 100


class ContentAnomalyDetector:
    """Detects content anomalies and infers structural region candidates."""

    def detect_anomalies(
        self,
        sheet_name: str,
        profile: SheetContentProfile,
        facts: DeclaredOpenXmlFacts,
        blocks: list[PopulatedBlock],
    ) -> list[StructuralAnomaly]:
        """Detect generic content-derived anomalies without duplicating topology checks.

        Args:
            sheet_name: Name of the worksheet.
            profile: Computed SheetContentProfile.
            facts: Declared OpenXML facts.
            blocks: Candidate populated row blocks.

        Returns:
            List of detected StructuralAnomaly objects.
        """
        anomalies: list[StructuralAnomaly] = []

        # 1. Understated Dimension Check
        if facts.declared_dimension is not None and profile.actual_bounding_box is not None:
            decl = facts.declared_dimension
            act = profile.actual_bounding_box
            if (
                act.min_row < decl.min_row
                or act.max_row > decl.max_row
                or act.min_col < decl.min_col
                or act.max_col > decl.max_col
            ):
                anomalies.append(
                    StructuralAnomaly(
                        anomaly_id=f"anom_understated_dim_{sheet_name}",
                        severity=AnomalySeverity.WARNING,
                        code="ANOM_UNDERSTATED_DIMENSION",
                        message=(
                            f"Worksheet contains populated cells outside declared OpenXML dimension "
                            f"(declared {decl.to_a1_ref()}, actual {act.to_a1_ref()})"
                        ),
                        box=act,
                        evidence=f"Declared: {decl.to_a1_ref()} | Actual: {act.to_a1_ref()}",
                    )
                )

        # 2. Mixed Column Types Check
        for col_idx, col_prof in profile.column_profiles.items():
            if col_prof.populated_count >= 5:
                # If predominant type represents less than 75% of populated values
                if col_prof.homogeneity_ratio < 0.75:
                    types_summary = ", ".join(
                        f"{k}: {v}"
                        for k, v in col_prof.type_counts.items()
                        if v > 0
                    )
                    anomalies.append(
                        StructuralAnomaly(
                            anomaly_id=f"anom_mixed_type_{sheet_name}_c{col_idx}",
                            severity=AnomalySeverity.INFO,
                            code="ANOM_MIXED_COLUMN_TYPES",
                            message=(
                                f"Column {col_idx} contains competing data types "
                                f"(predominant '{col_prof.predominant_type}' only {col_prof.homogeneity_ratio*100:.1f}%)"
                            ),
                            evidence=f"Counts: {types_summary}",
                        )
                    )

        # 3. Formula Inconsistency Check
        for col_idx, col_prof in profile.column_profiles.items():
            if col_prof.populated_count >= 6 and col_prof.formula_count > 0:
                formula_ratio = col_prof.formula_count / col_prof.populated_count
                # If column is mostly formulas (>= 50%) but has hardcoded constants
                if 0.50 <= formula_ratio < 1.0:
                    hardcoded_count = col_prof.populated_count - col_prof.formula_count
                    anomalies.append(
                        StructuralAnomaly(
                            anomaly_id=f"anom_formula_inconsistency_{sheet_name}_c{col_idx}",
                            severity=AnomalySeverity.WARNING,
                            code="ANOM_FORMULA_INCONSISTENCY",
                            message=(
                                f"Column {col_idx} has {col_prof.formula_count} formula cells "
                                f"interspersed with {hardcoded_count} hardcoded constants"
                            ),
                            evidence=f"Formula ratio: {formula_ratio*100:.1f}%",
                        )
                    )

        # 4. Jagged Row Structure Check
        for b_idx, block in enumerate(blocks):
            if len(block.row_widths) >= 4:
                avg_w = sum(block.row_widths) / len(block.row_widths)
                variance = sum((w - avg_w) ** 2 for w in block.row_widths) / len(
                    block.row_widths
                )
                std_dev = variance ** 0.5
                if avg_w > 0 and (std_dev / avg_w) > 0.40:
                    anomalies.append(
                        StructuralAnomaly(
                            anomaly_id=f"anom_jagged_rows_{sheet_name}_b{b_idx}",
                            severity=AnomalySeverity.INFO,
                            code="ANOM_JAGGED_ROW_STRUCTURE",
                            message=(
                                f"Candidate block rows {block.start_row}..{block.end_row} "
                                f"exhibit high width variance ({std_dev/avg_w*100:.1f}% variance)"
                            ),
                            box=block.box,
                        )
                    )

        # 5. Fragmented Content Regions Check
        if len(blocks) >= 2:
            anomalies.append(
                StructuralAnomaly(
                    anomaly_id=f"anom_fragmented_regions_{sheet_name}",
                    severity=AnomalySeverity.INFO,
                    code="ANOM_FRAGMENTED_REGIONS",
                    message=(
                        f"Worksheet contains {len(blocks)} disconnected content blocks "
                        f"separated by empty rows"
                    ),
                    evidence=f"{len(blocks)} candidate blocks discovered",
                )
            )

        # Cap anomalies to resource limit
        return anomalies[:MAX_ANOMALIES_PER_SHEET]

    def infer_region_hypotheses(
        self,
        sheet_name: str,
        profile: SheetContentProfile,
        facts: DeclaredOpenXmlFacts,
        blocks: list[PopulatedBlock],
    ) -> list[InferredRegionHypothesis]:
        """Generate heuristic region hypotheses and evaluate approved confidence formula.

        Formula:
        score = 0.40 * type_homogeneity + 0.30 * header_distinctness +
                0.20 * boundary_separation + 0.10 * density - irregularity_penalty
        Clamped to [0.0, 1.0].
        """
        hypotheses: list[InferredRegionHypothesis] = []

        # 1. Map declared OpenXML ListObjects into 1.0 confidence hypotheses
        for tbl in facts.list_objects:
            hypo = InferredRegionHypothesis(
                hypothesis_id=f"hypo_decl_tbl_{sheet_name}_{tbl.id}_{tbl.name}",
                region_type=RegionType.TABULAR_DATA,
                role=RegionRole.DECLARED_LIST_OBJECT,
                box=tbl.box,
                confidence_score=1.0,
                evidence_codes=[EvidenceCode.LIST_OBJECT_DECLARED],
                evidence_descriptions=[
                    f"Explicit OpenXML ListObject definition '{tbl.display_name}' declared at {tbl.ref}. "
                    "Confidence 1.0 represents certainty of structural declaration presence, "
                    "not data correctness or schema validity."
                ],
                source_provenance="openxml_declared_list_object",
            )
            hypotheses.append(hypo)

        # 2. Heuristic inference across discovered candidate blocks
        for b_idx, block in enumerate(blocks):
            box = block.box
            if box is None:
                continue

            # Check if this block is already covered by a declared table
            is_covered_by_table = False
            for tbl in facts.list_objects:
                if box.intersects(tbl.box) and (
                    box == tbl.box
                    or (box.contains_coord(tbl.box.min_row, tbl.box.min_col)
                    and box.contains_coord(tbl.box.max_row, tbl.box.max_col))
                ):
                    is_covered_by_table = True
                    break

            if is_covered_by_table:
                continue

            # Component 1: Type Homogeneity (0.40)
            col_homogeneities: list[float] = []
            for c_idx in range(box.min_col, box.max_col + 1):
                if c_idx in profile.column_profiles:
                    col_homogeneities.append(
                        profile.column_profiles[c_idx].homogeneity_ratio
                    )
            avg_homogeneity = (
                sum(col_homogeneities) / len(col_homogeneities)
                if col_homogeneities
                else 0.50
            )

            # Component 2: Header Distinctness (0.30)
            # Check if candidate first row contains strings while data rows contain numbers/dates
            header_distinctness = 0.50
            first_row_strings = 0
            body_non_strings = 0
            for c_idx in range(box.min_col, box.max_col + 1):
                col_p = profile.column_profiles.get(c_idx)
                if col_p and col_p.predominant_type in ("integer", "float", "date"):
                    body_non_strings += 1
                if col_p and col_p.type_counts.get("string", 0) >= 1:
                    first_row_strings += 1

            if box.row_count >= 2 and body_non_strings >= 1 and first_row_strings >= 1:
                header_distinctness = 0.90
            elif box.row_count >= 2:
                header_distinctness = 0.60
            else:
                header_distinctness = 0.30

            # Component 3: Boundary Separation (0.20)
            # Blocks discovered by empty row gaps have natural isolation
            boundary_sep = 0.85 if len(blocks) > 1 else 0.70

            # Component 4: Cell Density (0.10)
            density = min(1.0, block.cell_count / max(1, box.cell_count))

            # Irregularity Penalties
            penalties = 0.0
            penalty_notes: list[str] = []

            # Jagged row lengths penalty (-0.15)
            if len(block.row_widths) >= 4:
                avg_w = sum(block.row_widths) / len(block.row_widths)
                variance = sum((w - avg_w) ** 2 for w in block.row_widths) / len(
                    block.row_widths
                )
                if avg_w > 0 and ((variance ** 0.5) / avg_w) > 0.30:
                    penalties += 0.15
                    penalty_notes.append("Jagged row lengths variance > 30% (-0.15)")

            # Internal merged cell penalty (-0.15)
            for merge in facts.merge_cells:
                if box.contains_coord(merge.box.min_row, merge.box.min_col):
                    penalties += 0.15
                    penalty_notes.append("Internal merged cells present (-0.15)")
                    break

            # Calculate approved heuristic confidence score
            raw_score = (
                0.40 * avg_homogeneity
                + 0.30 * header_distinctness
                + 0.20 * boundary_sep
                + 0.10 * density
                - penalties
            )
            score = round(max(0.0, min(1.0, raw_score)), 4)

            # Role and RegionType selection
            if box.col_count == 2 and box.row_count >= 3:
                r_type = RegionType.KEY_VALUE_BLOCK
                role = RegionRole.KEY_VALUE_BLOCK
            elif density < 0.15 and box.cell_count > 50:
                r_type = RegionType.IRREGULAR_GRID
                role = RegionRole.SPARSE_ISLAND
            else:
                r_type = RegionType.TABULAR_DATA
                role = RegionRole.INFERRED_TABULAR_CANDIDATE

            # Evidence codes
            evidence_codes: list[EvidenceCode] = []
            evidence_desc: list[str] = []

            if avg_homogeneity >= 0.80:
                evidence_codes.append(EvidenceCode.HOMOGENEOUS_TYPE)
                evidence_desc.append(
                    f"Columns exhibit high type homogeneity ({avg_homogeneity*100:.1f}%)"
                )
            if header_distinctness >= 0.80:
                evidence_codes.append(EvidenceCode.HEADER_CONTRAST)
                evidence_desc.append("Candidate header row contrasts with data body types")
            if boundary_sep >= 0.80:
                evidence_codes.append(EvidenceCode.BOUNDARY_SEPARATION)
                evidence_desc.append("Block is isolated by empty row margins")
            if density >= 0.80:
                evidence_codes.append(EvidenceCode.DENSE_CELL_CLUSTER)
                evidence_desc.append(f"High populated cell density ({density*100:.1f}%)")

            hypo = InferredRegionHypothesis(
                hypothesis_id=f"hypo_inferred_{sheet_name}_b{b_idx}",
                region_type=r_type,
                role=role,
                box=box,
                confidence_score=score,
                evidence_codes=evidence_codes,
                evidence_descriptions=evidence_desc,
                deduction_penalties=penalty_notes,
                source_provenance="heuristic_content_inference",
            )
            hypotheses.append(hypo)

            if len(hypotheses) >= MAX_HYPOTHESES_PER_SHEET:
                break

        return hypotheses
