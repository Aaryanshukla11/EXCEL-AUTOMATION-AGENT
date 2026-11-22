"""Unit tests for M05 Semantic Type Inference Engine."""

import pytest

from excel_intel.core.types import ColumnType
from excel_intel.inspection.models import (
    BoundingBox,
    DeclaredMergeCell,
    DeclaredOpenXmlFacts,
    DeclaredSheetProperties,
)
from excel_intel.spatial.models import (
    SemanticZone,
    SemanticZoneType,
    SpatialRegionType,
    SpatialTableRegion,
)
from excel_intel.types.models import InferenceState, ValueCategory
from excel_intel.types.type_inferrer import TypeInferenceEngine


def _make_region(
    min_row: int,
    max_row: int,
    min_col: int,
    max_col: int,
    header_row: int = 1,
) -> SpatialTableRegion:
    """Helper to build a SpatialTableRegion with BODY zone."""
    r_box = BoundingBox(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col)
    body_box = BoundingBox(
        min_row=header_row + 1,
        max_row=max_row,
        min_col=min_col,
        max_col=max_col,
    )
    body_zone = SemanticZone(
        zone_type=SemanticZoneType.BODY,
        bounding_box=body_box,
        row_count=body_box.max_row - body_box.min_row + 1,
        cell_count=(body_box.max_row - body_box.min_row + 1) * (body_box.max_col - body_box.min_col + 1),
    )
    cell_count = (max_row - min_row + 1) * (max_col - min_col + 1)
    return SpatialTableRegion(
        region_id="reg_test_01",
        sheet_name="Sheet1",
        bounding_box=r_box,
        region_type=SpatialRegionType.INFERRED_TABLE,
        heuristic_confidence=1.0,
        cell_count=cell_count,
        populated_cell_count=cell_count,
        density=1.0,
        header_row=header_row,
        zones={SemanticZoneType.BODY: body_zone},
    )


class TestTypeInferenceEngine:
    """Test suite verifying inference states, state precedence, and heuristic scores."""

    def test_precedence_1_unknown_state(self) -> None:
        engine = TypeInferenceEngine()
        region = _make_region(1, 10, 1, 1, header_row=1)
        # All body cells are None or blank
        cells = {
            (r, 1): {"value": None}
            for r in range(2, 11)
        }
        report = engine.infer_cells(cells, region)
        profile = report.columns[1]

        assert profile.state == InferenceState.UNKNOWN
        assert profile.candidate_type is None
        assert profile.inferred_type == ColumnType.STRING  # Safe carrier
        assert profile.heuristic_support_score == 0.0
        assert profile.nullability_ratio == 1.0
        assert profile.requires_human_review is True

    def test_precedence_2_insufficient_data(self) -> None:
        engine = TypeInferenceEngine()
        region = _make_region(1, 10, 1, 1, header_row=1)
        # Only 3 populated cells (1 <= N_pop < 5)
        cells = {
            (2, 1): {"value": 10},
            (3, 1): {"value": 20},
            (4, 1): {"value": 30},
            (5, 1): {"value": None},
        }
        report = engine.infer_cells(cells, region)
        profile = report.columns[1]

        assert profile.state == InferenceState.INSUFFICIENT_DATA
        assert profile.candidate_type == ColumnType.INTEGER
        assert profile.inferred_type == ColumnType.STRING  # Carrier
        assert profile.populated_cells == 3
        assert profile.requires_human_review is True
        assert "Insufficient sample count" in str(profile.ambiguity_reason)

    def test_precedence_3a_date_format_ambiguity(self) -> None:
        engine = TypeInferenceEngine()
        region = _make_region(1, 10, 1, 1, header_row=1)
        # 8 populated cells with "01/02/03" (all ambiguous date order)
        cells = {
            (r, 1): {"value": "01/02/03"}
            for r in range(2, 10)
        }
        report = engine.infer_cells(cells, region)
        profile = report.columns[1]

        assert profile.state == InferenceState.AMBIGUOUS
        assert profile.candidate_type is None
        assert profile.inferred_type == ColumnType.STRING  # Carrier
        assert profile.is_ambiguous is True
        assert profile.requires_human_review is True
        assert "Date format order ambiguity" in str(profile.ambiguity_reason)

    def test_precedence_3b_boolean_vs_integer_ambiguity(self) -> None:
        engine = TypeInferenceEngine()
        region = _make_region(1, 10, 1, 1, header_row=1)
        # 8 populated cells, all 0 and 1 with no boolean style
        cells = {
            (r, 1): {"value": 1 if r % 2 == 0 else 0}
            for r in range(2, 10)
        }
        report = engine.infer_cells(cells, region)
        profile = report.columns[1]

        assert profile.state == InferenceState.AMBIGUOUS
        assert profile.candidate_type is None
        assert profile.inferred_type == ColumnType.STRING  # Carrier
        assert profile.is_ambiguous is True
        assert profile.requires_human_review is True
        assert "Integer vs Boolean ambiguity" in str(profile.ambiguity_reason)

    def test_precedence_4_low_homogeneity(self) -> None:
        engine = TypeInferenceEngine()
        region = _make_region(1, 11, 1, 1, header_row=1)
        # 10 cells: 5 integers, 5 strings (H = 5/10 = 50% < 80%)
        cells = {}
        for r in range(2, 7):
            cells[(r, 1)] = {"value": 100 + r}
        for r in range(7, 12):
            cells[(r, 1)] = {"value": f"Text_{r}"}

        report = engine.infer_cells(cells, region)
        profile = report.columns[1]

        assert profile.state == InferenceState.AMBIGUOUS
        assert profile.candidate_type is None
        assert profile.inferred_type == ColumnType.STRING  # Carrier
        assert profile.is_ambiguous is True
        assert profile.heuristic_support_score < 0.80
        assert profile.requires_human_review is True
        assert "Low type homogeneity" in str(profile.ambiguity_reason)

    def test_precedence_5_confident_inferred_types(self) -> None:
        engine = TypeInferenceEngine()
        region = _make_region(1, 11, 1, 4, header_row=1)
        cells = {}
        for r in range(2, 12):
            # Col 1: Confident Integers (> 1, avoiding 0/1 ambiguity)
            cells[(r, 1)] = {"value": 100 * r}
            # Col 2: Confident Dates
            cells[(r, 2)] = {"value": "2024-05-15"}
            # Col 3: Confident Currency ($1,000.00) -> mapped to DECIMAL
            cells[(r, 3)] = {"value": f"${r * 50}.00"}
            # Col 4: Confident Strings
            cells[(r, 4)] = {"value": f"Description for item {r}"}

        report = engine.infer_cells(cells, region)

        # Col 1: INTEGER
        p1 = report.columns[1]
        assert p1.state == InferenceState.INFERRED
        assert p1.candidate_type == ColumnType.INTEGER
        assert p1.inferred_type == ColumnType.INTEGER
        assert p1.heuristic_support_score == 1.0
        assert p1.requires_human_review is False

        # Col 2: DATE
        p2 = report.columns[2]
        assert p2.state == InferenceState.INFERRED
        assert p2.candidate_type == ColumnType.DATE
        assert p2.inferred_type == ColumnType.DATE
        assert p2.heuristic_support_score == 1.0

        # Col 3: CURRENCY -> DECIMAL
        p3 = report.columns[3]
        assert p3.state == InferenceState.INFERRED
        assert p3.candidate_type == ColumnType.DECIMAL
        assert p3.inferred_type == ColumnType.DECIMAL
        assert p3.heuristic_support_score == 1.0

        # Col 4: STRING
        p4 = report.columns[4]
        assert p4.state == InferenceState.INFERRED
        assert p4.candidate_type == ColumnType.STRING
        assert p4.inferred_type == ColumnType.STRING

    def test_merged_cell_semantics_no_column_inflation(self) -> None:
        """Verify horizontal merged non-anchors do NOT inflate other columns and are not counted as nulls."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 6, 1, 2, header_row=1)
        # Merge covers rows 2..3 in col 1 and 2: "A2:B3"
        merge_fact = DeclaredMergeCell.from_ref("A2:B3")
        properties = DeclaredSheetProperties(sheet_id=1, name="Sheet1")
        facts = DeclaredOpenXmlFacts(
            properties=properties,
            merge_cells=[merge_fact],
        )
        # Only anchor cell (2, 1) has value "MergedTitle"
        cells = {
            (2, 1): {"value": "MergedTitle"},
            # Rows 4, 5, 6 in Col 1: Integers
            (4, 1): {"value": 100},
            (5, 1): {"value": 200},
            (6, 1): {"value": 300},
            # Rows 4, 5, 6 in Col 2: Currency
            (4, 2): {"value": "$10.00"},
            (5, 2): {"value": "$20.00"},
            (6, 2): {"value": "$30.00"},
        }

        report = engine.infer_cells(cells, region, facts=facts)

        # Col 1: Vertical merge continuation at row 3 is NOT duplicated
        p1 = report.columns[1]
        assert p1.merged_non_anchor_cells == 1  # Row 3 is vertical non-anchor
        assert p1.effective_cells == 4  # 5 - 1 = 4
        assert p1.populated_cells == 4  # 1 anchor ("MergedTitle") + 3 integers = 4

        # Col 2: Non-anchor rows 2 and 3 do NOT inherit "MergedTitle" (no type inflation)
        p2 = report.columns[2]
        assert p2.merged_non_anchor_cells == 2  # Covered by horizontal merge
        assert p2.effective_cells == 3  # 5 - 2 = 3
        assert p2.populated_cells == 3  # Exactly the 3 currency rows
        assert p2.null_cells == 0  # NOT penalized as nulls!
        assert p2.nullability_ratio == 0.0
        assert p2.inferred_type == ColumnType.STRING  # 3 cells -> INSUFFICIENT_DATA carrier
        assert p2.candidate_type == ColumnType.DECIMAL  # Detected currency -> DECIMAL candidate!

    def test_vertical_merge_multiple_rows_single_observation(self) -> None:
        """Verify vertical merge spanning multiple rows creates exactly ONE semantic observation."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 6, 1, 1, header_row=1)
        # A2:A6 (5 rows merged vertically in BODY)
        merge_fact = DeclaredMergeCell.from_ref("A2:A6")
        properties = DeclaredSheetProperties(sheet_id=1, name="Sheet1")
        facts = DeclaredOpenXmlFacts(properties=properties, merge_cells=[merge_fact])

        cells = {(2, 1): {"value": "NorthRegion"}}  # Anchor cell

        report = engine.infer_cells(cells, region, facts=facts)
        p = report.columns[1]

        assert p.populated_cells == 1  # Exactly ONE semantic observation, NOT 5!
        assert p.merged_non_anchor_cells == 4  # 4 continuation coordinates
        assert p.effective_cells == 1
        assert p.null_cells == 0
        assert p.nullability_ratio == 0.0
        assert p.sample_values == ["NorthRegion"]
        assert report.sampling.semantic_observation_count == 1

    def test_horizontal_merge_multiple_columns_isolation(self) -> None:
        """Verify horizontal merge spanning multiple columns does not inflate adjacent columns."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 4, 1, 3, header_row=1)
        # A2:C2 (3 columns merged horizontally in row 2)
        merge_fact = DeclaredMergeCell.from_ref("A2:C2")
        properties = DeclaredSheetProperties(sheet_id=1, name="Sheet1")
        facts = DeclaredOpenXmlFacts(properties=properties, merge_cells=[merge_fact])

        cells = {
            (2, 1): {"value": "HeaderBanner"},
            # Rows 3 and 4 have unique data per column
            (3, 1): {"value": 10}, (4, 1): {"value": 20},
            (3, 2): {"value": 30}, (4, 2): {"value": 40},
            (3, 3): {"value": 50}, (4, 3): {"value": 60},
        }

        report = engine.infer_cells(cells, region, facts=facts)

        # Col 1 owns the anchor in row 2
        p1 = report.columns[1]
        assert p1.populated_cells == 3  # "HeaderBanner" + 10 + 20
        assert p1.merged_non_anchor_cells == 0

        # Cols 2 and 3 must NOT have "HeaderBanner"
        for c in (2, 3):
            pc = report.columns[c]
            assert pc.merged_non_anchor_cells == 1  # Row 2 is horizontal non-anchor
            assert pc.populated_cells == 2  # Only rows 3 and 4
            assert pc.effective_cells == 2
            assert pc.null_cells == 0
            assert "HeaderBanner" not in pc.sample_values

    def test_mixed_ordinary_and_merged_observations_in_one_column(self) -> None:
        """Verify mixed ordinary and merged cells in one column."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 9, 1, 1, header_row=1)
        # A2:A4 merged (Cat_1), A5 ordinary (Cat_2), A6 ordinary (Cat_3), A7:A8 merged (Cat_4), A9 blank
        m1 = DeclaredMergeCell.from_ref("A2:A4")
        m2 = DeclaredMergeCell.from_ref("A7:A8")
        properties = DeclaredSheetProperties(sheet_id=1, name="Sheet1")
        facts = DeclaredOpenXmlFacts(properties=properties, merge_cells=[m1, m2])

        cells = {
            (2, 1): {"value": "Cat_1"},
            (5, 1): {"value": "Cat_2"},
            (6, 1): {"value": "Cat_3"},
            (7, 1): {"value": "Cat_4"},
            (9, 1): {"value": None},
        }

        report = engine.infer_cells(cells, region, facts=facts)
        p = report.columns[1]

        # 8 body rows total (2..9)
        # Non-anchor coordinates: A3, A4 (from m1) + A8 (from m2) = 3 non-anchors
        assert p.merged_non_anchor_cells == 3
        assert p.effective_cells == 5  # 8 - 3 = 5
        assert p.populated_cells == 4  # Cat_1, Cat_2, Cat_3, Cat_4
        assert p.null_cells == 1  # A9 is null
        assert p.nullability_ratio == 0.20  # 1 / 5 = 0.20

    def test_merged_regions_intersecting_sampling_boundaries(self) -> None:
        """Verify vertical merge where anchor row was not in the sampled coordinates."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 11, 1, 1, header_row=1)
        # A2:A11 merged across 10 rows
        merge_fact = DeclaredMergeCell.from_ref("A2:A11")
        properties = DeclaredSheetProperties(sheet_id=1, name="Sheet1")
        facts = DeclaredOpenXmlFacts(properties=properties, merge_cells=[merge_fact])

        # Cell data: anchor (2, 1) has value "BoundaryValue"
        cells = {(2, 1): {"value": "BoundaryValue"}}

        # Custom sampling diag simulating sampling only rows 5 and 9 (anchor row 2 is omitted)
        from excel_intel.types.models import SamplingDiagnostics
        custom_diag = SamplingDiagnostics(
            total_rows=10,
            total_cols=1,
            sampled_rows=2,
            sampled_cols=1,
            sampled_cells=2,
            sampled_row_indices=[5, 9],
            sampled_col_indices=[1],
        )

        report = engine.infer_cells(cells, region, facts=facts, sampling_diag=custom_diag)
        p = report.columns[1]

        # Row 5 resolved from anchor (2, 1) once. Row 9 saw anchor already resolved and became non-anchor.
        assert p.populated_cells == 1
        assert p.merged_non_anchor_cells == 1
        assert p.effective_cells == 1
        assert p.sample_values == ["BoundaryValue"]

    def test_deterministic_results_across_repeated_runs(self) -> None:
        """Verify deterministic output across repeated inference runs with merged cells."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 8, 1, 2, header_row=1)
        m = DeclaredMergeCell.from_ref("A2:A4")
        properties = DeclaredSheetProperties(sheet_id=1, name="Sheet1")
        facts = DeclaredOpenXmlFacts(properties=properties, merge_cells=[m])

        cells = {
            (2, 1): {"value": "GroupAlpha"},
            (5, 1): {"value": "GroupBeta"},
            (6, 1): {"value": "GroupBeta"},
            (7, 1): {"value": "GroupBeta"},
            (8, 1): {"value": "GroupBeta"},
            (2, 2): {"value": 100},
            (3, 2): {"value": 200},
            (4, 2): {"value": 300},
            (5, 2): {"value": 400},
            (6, 2): {"value": 500},
            (7, 2): {"value": 600},
            (8, 2): {"value": 700},
        }

        reports = [engine.infer_cells(cells, region, facts=facts) for _ in range(5)]
        first_rep = reports[0]

        for rep in reports[1:]:
            assert rep.columns[1].model_dump() == first_rep.columns[1].model_dump()
            assert rep.columns[2].model_dump() == first_rep.columns[2].model_dump()
            assert rep.sampling.model_dump() == first_rep.sampling.model_dump()

    def test_exclusively_null_markers_is_ambiguous(self) -> None:
        """Verify column containing exclusively textual null markers ('-', 'N/A') is AMBIGUOUS, not UNKNOWN."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 10, 1, 1, header_row=1)
        # 9 rows of "-"
        cells = {
            (r, 1): {"value": "-"}
            for r in range(2, 11)
        }
        report = engine.infer_cells(cells, region)
        p = report.columns[1]

        assert p.state == InferenceState.AMBIGUOUS
        assert p.candidate_type is None
        assert p.inferred_type == ColumnType.STRING  # Safe carrier
        assert p.is_ambiguous is True
        assert p.requires_human_review is True
        assert p.null_marker_count == 9
        assert "exclusively textual null markers" in str(p.ambiguity_reason)

    def test_high_score_cannot_override_date_ambiguity(self) -> None:
        """Verify that high support score (S=1.0) cannot override semantic ambiguity."""
        engine = TypeInferenceEngine()
        region = _make_region(1, 11, 1, 1, header_row=1)
        # 10 identical ambiguous dates "01/02/03"
        cells = {
            (r, 1): {"value": "01/02/03"}
            for r in range(2, 12)
        }
        report = engine.infer_cells(cells, region)
        p = report.columns[1]

        assert p.heuristic_support_score == 1.0  # Perfect support score
        assert p.state == InferenceState.AMBIGUOUS  # But state is AMBIGUOUS!
        assert p.candidate_type is None  # Never authoritative
        assert p.inferred_type == ColumnType.STRING
        assert p.requires_human_review is True

    def test_original_currency_and_percentage_provenance(self) -> None:
        """Verify NormalizedValue preserves original currency symbols and percentage factors."""
        from excel_intel.types.pattern_detector import PatternDetector

        curr = PatternDetector.detect_value("($2,500.00)")
        assert curr.category == ValueCategory.CURRENCY
        assert curr.currency_symbol == "$"
        assert curr.normalized_value == -2500.00
        assert curr.is_accounting_negative is True

        pct = PatternDetector.detect_value("12.75%")
        assert pct.category == ValueCategory.PERCENTAGE
        assert pct.normalized_value == 12.75
        assert pct.percentage_factor == 0.1275

    def test_empty_region_zero_body_rows(self) -> None:
        engine = TypeInferenceEngine()
        # Region has min_row=1, max_row=1, header_row=1 -> 0 body rows
        r_box = BoundingBox(min_row=1, max_row=1, min_col=1, max_col=3)
        region = SpatialTableRegion(
            region_id="reg_empty_01",
            sheet_name="Sheet1",
            bounding_box=r_box,
            region_type=SpatialRegionType.INFERRED_TABLE,
            heuristic_confidence=1.0,
            cell_count=3,
            populated_cell_count=3,
            density=1.0,
            header_row=1,
        )
        report = engine.infer_cells({}, region)
        assert len(report.columns) == 3
        for col_idx in (1, 2, 3):
            assert report.columns[col_idx].state == InferenceState.UNKNOWN
            assert report.columns[col_idx].inferred_type == ColumnType.STRING
            assert report.columns[col_idx].heuristic_support_score == 0.0
