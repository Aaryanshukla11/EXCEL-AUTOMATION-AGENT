"""Unit tests for M03 Inspection Data Models (models.py).

Verifies:
1. Coordinate conversion accuracy (A1, Z1, AA1, XFD1048576, $, invalid bounds).
2. BoundingBox constructors, validation, intersection, containment, immutability.
3. HiddenInterval validation and consolidation.
4. DeclaredOpenXmlFacts immutability and lack of probabilistic confidence fields.
5. InferredRegionHypothesis normalized confidence score bounds [0.0, 1.0].
6. StructuralAnomaly fields and immutability.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from excel_intel.inspection.models import (
    AnomalySeverity,
    BoundingBox,
    DeclaredDefinedName,
    DeclaredListObject,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
    EvidenceCode,
    HiddenInterval,
    InferredRegionHypothesis,
    RegionHypothesis,
    RegionType,
    SheetVisibility,
    StructuralAnomaly,
    cell_ref_to_row_col,
    col_index_to_letter,
    col_letter_to_index,
    row_col_to_cell_ref,
)
from excel_intel.inspection.topology_inspector import consolidate_intervals


class TestCoordinateUtilities:
    def test_col_letter_to_index(self) -> None:
        assert col_letter_to_index("A") == 1
        assert col_letter_to_index("Z") == 26
        assert col_letter_to_index("AA") == 27
        assert col_letter_to_index("AZ") == 52
        assert col_letter_to_index("BA") == 53
        assert col_letter_to_index("XFD") == 16384

    def test_col_letter_case_insensitivity(self) -> None:
        assert col_letter_to_index("a") == 1
        assert col_letter_to_index("xfd") == 16384

    def test_invalid_col_letter_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid column character"):
            col_letter_to_index("A1")
        with pytest.raises(ValueError, match="out of Excel range"):
            col_letter_to_index("XFE")

    def test_col_index_to_letter(self) -> None:
        assert col_index_to_letter(1) == "A"
        assert col_index_to_letter(26) == "Z"
        assert col_index_to_letter(27) == "AA"
        assert col_index_to_letter(16384) == "XFD"

    def test_invalid_col_index_raises(self) -> None:
        with pytest.raises(ValueError, match="out of Excel range"):
            col_index_to_letter(0)
        with pytest.raises(ValueError, match="out of Excel range"):
            col_index_to_letter(16385)

    def test_cell_ref_to_row_col(self) -> None:
        assert cell_ref_to_row_col("A1") == (1, 1)
        assert cell_ref_to_row_col("Z100") == (100, 26)
        assert cell_ref_to_row_col("$B$5") == (5, 2)
        assert cell_ref_to_row_col("XFD1048576") == (1048576, 16384)

    def test_invalid_cell_ref_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid cell reference"):
            cell_ref_to_row_col("INVALID")
        with pytest.raises(ValueError, match="Row 1048577 out of Excel range"):
            cell_ref_to_row_col("A1048577")

    def test_row_col_to_cell_ref(self) -> None:
        assert row_col_to_cell_ref(1, 1) == "A1"
        assert row_col_to_cell_ref(100, 26) == "Z100"
        assert row_col_to_cell_ref(1048576, 16384) == "XFD1048576"


class TestBoundingBox:
    def test_valid_box(self) -> None:
        box = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=5)
        assert box.row_count == 10
        assert box.col_count == 5
        assert box.cell_count == 50
        assert box.to_a1_ref() == "A1:E10"

    def test_single_cell_box(self) -> None:
        box = BoundingBox(min_row=5, max_row=5, min_col=3, max_col=3)
        assert box.row_count == 1
        assert box.col_count == 1
        assert box.cell_count == 1
        assert box.to_a1_ref() == "C5"

    def test_from_a1_ref(self) -> None:
        box = BoundingBox.from_a1_ref("B2:D6")
        assert box.min_row == 2
        assert box.max_row == 6
        assert box.min_col == 2
        assert box.max_col == 4

        # Inverted coordinates in ref are automatically normalized
        box_inv = BoundingBox.from_a1_ref("D6:B2")
        assert box_inv == box

        box_single = BoundingBox.from_a1_ref("A1")
        assert box_single == BoundingBox(min_row=1, max_row=1, min_col=1, max_col=1)

    def test_invalid_bounds_raise(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(min_row=10, max_row=5, min_col=1, max_col=5)
        with pytest.raises(ValidationError):
            BoundingBox(min_row=1, max_row=5, min_col=10, max_col=5)

    def test_immutability(self) -> None:
        box = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=5)
        with pytest.raises(ValidationError):
            box.min_row = 2  # type: ignore[misc]

    def test_contains_and_intersects(self) -> None:
        box1 = BoundingBox(min_row=1, max_row=10, min_col=1, max_col=10)
        assert box1.contains_coord(5, 5)
        assert not box1.contains_coord(11, 5)

        box2 = BoundingBox(min_row=5, max_row=15, min_col=5, max_col=15)
        assert box1.intersects(box2)

        box3 = BoundingBox(min_row=20, max_row=30, min_col=20, max_col=30)
        assert not box1.intersects(box3)


class TestHiddenInterval:
    def test_valid_interval(self) -> None:
        interval = HiddenInterval(dimension="row", start=5, end=10)
        assert interval.count == 6
        assert interval.dimension == "row"

    def test_invalid_interval_raises(self) -> None:
        with pytest.raises(ValidationError):
            HiddenInterval(dimension="invalid", start=1, end=5)
        with pytest.raises(ValidationError):
            HiddenInterval(dimension="col", start=10, end=5)

    def test_interval_consolidation(self) -> None:
        raw_rows = [1, 2, 3, 7, 8, 12]
        intervals = consolidate_intervals(raw_rows, dimension="row")
        assert len(intervals) == 3
        assert intervals[0] == HiddenInterval(dimension="row", start=1, end=3)
        assert intervals[1] == HiddenInterval(dimension="row", start=7, end=8)
        assert intervals[2] == HiddenInterval(dimension="row", start=12, end=12)

    def test_empty_consolidation(self) -> None:
        assert consolidate_intervals([], dimension="col") == []


class TestDeclaredOpenXmlFacts:
    def test_facts_immutability_and_lack_of_confidence(self) -> None:
        props = DeclaredSheetProperties(
            sheet_id=1,
            name="Sheet1",
            visibility=SheetVisibility.VISIBLE,
            declared_dimension_ref="A1:Z50",
            declared_dimension_box=BoundingBox.from_a1_ref("A1:Z50"),
        )
        merge = DeclaredMergeCell.from_ref("A1:B2")
        facts = DeclaredOpenXmlFacts(
            properties=props,
            declared_dimension=props.declared_dimension_box,
            merge_cells=[merge],
        )

        assert facts.properties.name == "Sheet1"
        assert len(facts.merge_cells) == 1
        assert facts.merge_cells[0].top_left_cell == "A1"

        # Declared facts MUST NOT have probabilistic confidence attributes
        assert not hasattr(facts, "confidence")
        assert not hasattr(facts, "score")

        # Frozen immutability check
        with pytest.raises(ValidationError):
            facts.properties = props  # type: ignore[misc]


class TestInferredRegionHypothesis:
    def test_hypothesis_confidence_bounds(self) -> None:
        box = BoundingBox.from_a1_ref("A1:D20")
        hypo = InferredRegionHypothesis(
            hypothesis_id="hypo_001",
            region_type=RegionType.TABULAR_DATA,
            box=box,
            confidence_score=0.85,
            evidence_codes=[EvidenceCode.HOMOGENEOUS_TYPE, EvidenceCode.HEADER_CONTRAST],
            evidence_descriptions=["Column 1-4 are homogeneous integer/string."],
        )
        assert hypo.confidence_score == 0.85
        assert hypo.region_type == RegionType.TABULAR_DATA

        # Reject score < 0.0
        with pytest.raises(ValidationError):
            InferredRegionHypothesis(
                hypothesis_id="hypo_err",
                region_type=RegionType.TABULAR_DATA,
                box=box,
                confidence_score=-0.1,
            )

        # Reject score > 1.0
        with pytest.raises(ValidationError):
            InferredRegionHypothesis(
                hypothesis_id="hypo_err",
                region_type=RegionType.TABULAR_DATA,
                box=box,
                confidence_score=1.01,
            )

    def test_region_hypothesis_alias(self) -> None:
        assert RegionHypothesis is InferredRegionHypothesis


class TestStructuralAnomaly:
    def test_anomaly_fields_and_immutability(self) -> None:
        anom = StructuralAnomaly(
            anomaly_id="anom_001",
            severity=AnomalySeverity.WARNING,
            code="ANOM_MIXED_TYPE",
            message="Column 3 has competing types (int vs string)",
            cell_ref="C5",
            box=BoundingBox.from_a1_ref("C1:C10"),
        )
        assert anom.severity == AnomalySeverity.WARNING
        assert anom.code == "ANOM_MIXED_TYPE"
        with pytest.raises(ValidationError):
            anom.severity = AnomalySeverity.CRITICAL  # type: ignore[misc]
