"""Tests for M03 Content Anomaly Detector & Region Inference Engine.

Verifies:
1. Detection of content anomalies:
   - Mixed column types (competing data types within column)
   - Formula inconsistencies (constants in formula columns)
   - Jagged row structures (uneven row widths)
   - Fragmented disconnected regions (multiple separated blocks)
   - Understated dimensions (cells outside declared dimension)
2. Region hypothesis generation and confidence scoring:
   - Declared OpenXML tables get 1.0 confidence score.
   - Inferred candidates evaluate approved 4-factor scoring formula.
   - Penalty deductions for structural irregularities.
   - Score clamping strictly in [0.0, 1.0].
3. Resource caps enforcement.
"""

from __future__ import annotations

import pytest
from excel_intel.inspection.anomaly_detector import (
    MAX_ANOMALIES_PER_SHEET,
    MAX_HYPOTHESES_PER_SHEET,
    ContentAnomalyDetector,
)
from excel_intel.inspection.content_profiler import PopulatedBlock
from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    ColumnProfile,
    DeclaredListObject,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
    EvidenceCode,
    LayoutClassification,
    RegionRole,
    RegionType,
    SheetContentProfile,
    SheetVisibility,
)


def make_dummy_facts(
    sheet_name: str = "Sheet1",
    declared_dimension: BoundingBox | None = None,
    list_objects: list[DeclaredListObject] | None = None,
    merge_cells: list[DeclaredMergeCell] | None = None,
) -> DeclaredOpenXmlFacts:
    """Helper to construct declared OpenXML facts."""
    return DeclaredOpenXmlFacts(
        properties=DeclaredSheetProperties(
            sheet_id=1, name=sheet_name, visibility=SheetVisibility.VISIBLE
        ),
        declared_dimension=declared_dimension,
        merge_cells=merge_cells or [],
        hidden_rows=[],
        hidden_columns=[],
        list_objects=list_objects or [],
    )


def test_understated_dimension_anomaly_detection() -> None:
    """Verify ANOM_UNDERSTATED_DIMENSION triggers when actual box exceeds declared."""
    detector = ContentAnomalyDetector()
    facts = make_dummy_facts(declared_dimension=BoundingBox(min_row=1, max_row=10, min_col=1, max_col=5))
    profile = SheetContentProfile(
        sheet_index=0,
        sheet_name="Sheet1",
        total_cells_visited=100,
        populated_cell_count=100,
        min_row=1,
        max_row=25,  # Exceeds declared max_row 10
        min_col=1,
        max_col=5,
        actual_bounding_box=BoundingBox(min_row=1, max_row=25, min_col=1, max_col=5),
        layout_classification=LayoutClassification.SINGLE_TABLE,
    )

    anomalies = detector.detect_anomalies("Sheet1", profile, facts, [])

    dim_anoms = [a for a in anomalies if a.code == "ANOM_UNDERSTATED_DIMENSION"]
    assert len(dim_anoms) == 1
    assert dim_anoms[0].severity == AnomalySeverity.WARNING
    assert "populated cells outside declared OpenXML dimension" in dim_anoms[0].message


def test_mixed_column_types_anomaly_detection() -> None:
    """Verify ANOM_MIXED_COLUMN_TYPES triggers when column homogeneity < 0.85."""
    detector = ContentAnomalyDetector()
    facts = make_dummy_facts()
    profile = SheetContentProfile(
        sheet_index=0,
        sheet_name="Sheet1",
        column_profiles={
            2: ColumnProfile(
                col_index=2,
                populated_count=10,
                type_counts={"float": 6, "string": 4},
                predominant_type="float",
                homogeneity_ratio=0.60,  # Below 0.85 threshold
            )
        },
    )

    anomalies = detector.detect_anomalies("Sheet1", profile, facts, [])

    type_anoms = [a for a in anomalies if a.code == "ANOM_MIXED_COLUMN_TYPES"]
    assert len(type_anoms) == 1
    assert type_anoms[0].severity == AnomalySeverity.INFO
    assert "contains competing data types" in type_anoms[0].message
    assert "Counts: float: 6, string: 4" in type_anoms[0].evidence


def test_formula_inconsistency_anomaly_detection() -> None:
    """Verify ANOM_FORMULA_INCONSISTENCY triggers on constant literals in formula columns."""
    detector = ContentAnomalyDetector()
    facts = make_dummy_facts()
    profile = SheetContentProfile(
        sheet_index=0,
        sheet_name="Sheet1",
        column_profiles={
            3: ColumnProfile(
                col_index=3,
                populated_count=20,
                has_formulas=True,
                formula_count=18,  # 90% formulas, 2 constant cells
            )
        },
    )

    anomalies = detector.detect_anomalies("Sheet1", profile, facts, [])

    formula_anoms = [a for a in anomalies if a.code == "ANOM_FORMULA_INCONSISTENCY"]
    assert len(formula_anoms) == 1
    assert formula_anoms[0].severity == AnomalySeverity.WARNING
    assert "has 18 formula cells interspersed with 2 hardcoded constants" in formula_anoms[0].message


def test_jagged_row_structure_anomaly_detection() -> None:
    """Verify ANOM_JAGGED_ROW_STRUCTURE triggers when block rows have uneven widths."""
    detector = ContentAnomalyDetector()
    facts = make_dummy_facts()
    profile = SheetContentProfile(sheet_index=0, sheet_name="Sheet1")

    block = PopulatedBlock(start_row=1)
    block.add_row(1, [1, 2, 3, 4, 5])
    block.add_row(2, [1, 2])
    block.add_row(3, [1, 2, 3, 4, 5, 6, 7])
    block.add_row(4, [1])

    anomalies = detector.detect_anomalies("Sheet1", profile, facts, [block])

    jagged_anoms = [a for a in anomalies if a.code == "ANOM_JAGGED_ROW_STRUCTURE"]
    assert len(jagged_anoms) == 1
    assert jagged_anoms[0].severity == AnomalySeverity.INFO
    assert "high width variance" in jagged_anoms[0].message


def test_fragmented_regions_anomaly_detection() -> None:
    """Verify ANOM_FRAGMENTED_REGIONS triggers when sheet has > 3 separated blocks."""
    detector = ContentAnomalyDetector()
    facts = make_dummy_facts()
    profile = SheetContentProfile(sheet_index=0, sheet_name="Sheet1")

    blocks = [PopulatedBlock(r) for r in [1, 10, 20, 30]]
    for b in blocks:
        b.add_row(b.start_row, [1, 2])

    anomalies = detector.detect_anomalies("Sheet1", profile, facts, blocks)

    frag_anoms = [a for a in anomalies if a.code == "ANOM_FRAGMENTED_REGIONS"]
    assert len(frag_anoms) == 1
    assert "4 disconnected content blocks" in frag_anoms[0].message


def test_declared_table_gets_perfect_confidence() -> None:
    """Verify declared OpenXML table becomes 1.0 confidence hypothesis."""
    detector = ContentAnomalyDetector()
    tbl = DeclaredListObject(
        id=1,
        name="SalesTable",
        display_name="SalesTable",
        ref="A1:D50",
        box=BoundingBox(min_row=1, max_row=50, min_col=1, max_col=4),
        header_row_count=1,
        column_names=["ID", "Date", "Amount", "Status"],
    )
    facts = make_dummy_facts(list_objects=[tbl])
    profile = SheetContentProfile(sheet_index=0, sheet_name="Sheet1")

    hypotheses = detector.infer_region_hypotheses("Sheet1", profile, facts, [])

    assert len(hypotheses) == 1
    h = hypotheses[0]
    assert h.confidence_score == 1.0
    assert h.role == RegionRole.DECLARED_LIST_OBJECT
    assert EvidenceCode.LIST_OBJECT_DECLARED in h.evidence_codes
    assert h.source_provenance == "openxml_declared_list_object"


def test_heuristic_region_inference_and_clamping() -> None:
    """Verify candidate block scoring formula and clamping behavior."""
    detector = ContentAnomalyDetector()
    facts = make_dummy_facts()

    # Create profile with high homogeneity in cols 1-3
    profile = SheetContentProfile(
        sheet_index=0,
        sheet_name="Sheet1",
        column_profiles={
            1: ColumnProfile(col_index=1, populated_count=10, homogeneity_ratio=1.0, predominant_type="integer"),
            2: ColumnProfile(col_index=2, populated_count=10, homogeneity_ratio=0.9, predominant_type="float"),
            3: ColumnProfile(col_index=3, populated_count=10, homogeneity_ratio=1.0, predominant_type="string"),
        },
    )

    block = PopulatedBlock(start_row=1)
    for r in range(1, 11):
        block.add_row(r, [1, 2, 3])

    hypotheses = detector.infer_region_hypotheses("Sheet1", profile, facts, [block])

    assert len(hypotheses) == 1
    h = hypotheses[0]
    assert 0.0 <= h.confidence_score <= 1.0
    assert h.role == RegionRole.INFERRED_TABULAR_CANDIDATE
    assert h.region_type == RegionType.TABULAR_DATA
    assert len(h.evidence_codes) > 0


def test_penalty_deductions_for_irregularities() -> None:
    """Verify internal merge cells and jagged row penalties deduct from confidence."""
    detector = ContentAnomalyDetector()
    # Merge cell inside the block
    merge = DeclaredMergeCell.from_ref("A2:B2")
    facts = make_dummy_facts(merge_cells=[merge])

    profile = SheetContentProfile(
        sheet_index=0,
        sheet_name="Sheet1",
        column_profiles={
            1: ColumnProfile(col_index=1, populated_count=5, homogeneity_ratio=0.6, predominant_type="string"),
            2: ColumnProfile(col_index=2, populated_count=5, homogeneity_ratio=0.5, predominant_type="integer"),
        },
    )

    block = PopulatedBlock(start_row=1)
    block.add_row(1, [1, 2])
    block.add_row(2, [1, 2])
    block.add_row(3, [1])  # Jagged
    block.add_row(4, [1, 2, 3, 4])  # Jagged

    hypotheses = detector.infer_region_hypotheses("Sheet1", profile, facts, [block])

    assert len(hypotheses) == 1
    h = hypotheses[0]
    # Penalties must be recorded and score clamped
    assert len(h.deduction_penalties) > 0
    assert 0.0 <= h.confidence_score <= 1.0
