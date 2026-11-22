"""Unit tests for M05 Semantic Type Data Contracts and Schemas."""

import pytest
from pydantic import ValidationError

from excel_intel.core.types import ColumnType
from excel_intel.inspection.models import BoundingBox
from excel_intel.types.models import (
    ColumnTypeProfile,
    InferenceState,
    NormalizedValue,
    RegionTypeReport,
    SamplingDiagnostics,
    ValueCategory,
)


class TestM05TypeModels:
    """Test suite verifying frozen schemas, validation, and mappings."""

    def test_inference_state_enum(self) -> None:
        assert InferenceState.INFERRED == "INFERRED"
        assert InferenceState.UNKNOWN == "UNKNOWN"
        assert InferenceState.AMBIGUOUS == "AMBIGUOUS"
        assert InferenceState.INSUFFICIENT_DATA == "INSUFFICIENT_DATA"

    def test_value_category_mapping(self) -> None:
        assert ValueCategory.INTEGER.to_column_type() == ColumnType.INTEGER
        assert ValueCategory.DECIMAL.to_column_type() == ColumnType.DECIMAL
        assert ValueCategory.CURRENCY.to_column_type() == ColumnType.DECIMAL
        assert ValueCategory.PERCENTAGE.to_column_type() == ColumnType.DECIMAL
        assert ValueCategory.DATE.to_column_type() == ColumnType.DATE
        assert ValueCategory.BOOLEAN.to_column_type() == ColumnType.BOOLEAN
        assert ValueCategory.FORMULA.to_column_type() == ColumnType.FORMULA
        assert ValueCategory.STRING.to_column_type() == ColumnType.STRING
        assert ValueCategory.ERROR.to_column_type() == ColumnType.STRING
        assert ValueCategory.NULL.to_column_type() == ColumnType.STRING

    def test_normalized_value_immutability(self) -> None:
        norm = NormalizedValue(
            raw_value="$100.00",
            category=ValueCategory.CURRENCY,
            normalized_value=100.0,
            currency_symbol="$",
        )
        assert norm.raw_value == "$100.00"
        assert norm.category == ValueCategory.CURRENCY
        with pytest.raises(ValidationError):
            norm.category = ValueCategory.STRING  # type: ignore

    def test_sampling_diagnostics_validation(self) -> None:
        diag = SamplingDiagnostics(
            total_rows=1000,
            total_cols=20,
            sampled_rows=100,
            sampled_cols=20,
            sampled_cells=2000,
            is_truncated=True,
            truncation_details="2D cap applied",
            sampled_row_indices=[1, 2, 3],
            sampled_col_indices=[1, 2],
        )
        assert diag.sampled_cells == 2000
        assert diag.is_truncated is True

        # Validation: sampled_cells > 10000 must raise ValidationError
        with pytest.raises(ValidationError):
            SamplingDiagnostics(
                total_rows=10000,
                total_cols=100,
                sampled_rows=500,
                sampled_cols=50,
                sampled_cells=25000,  # exceeds le=10000
            )

    def test_column_type_profile_model(self) -> None:
        profile = ColumnTypeProfile(
            col_index=1,
            state=InferenceState.INFERRED,
            candidate_type=ColumnType.INTEGER,
            total_cells=10,
            populated_cells=10,
            null_cells=0,
            nullability_ratio=0.0,
            category_counts={"INTEGER": 10},
            inferred_type=ColumnType.INTEGER,
            heuristic_support_score=1.0,
            is_ambiguous=False,
            requires_human_review=False,
            sample_values=[1, 2, 3],
        )
        assert profile.col_index == 1
        assert profile.state == InferenceState.INFERRED
        assert profile.inferred_type == ColumnType.INTEGER
        assert profile.heuristic_support_score == 1.0

        # Immutability
        with pytest.raises(ValidationError):
            profile.heuristic_support_score = 0.5  # type: ignore

    def test_region_type_report_m01_export(self) -> None:
        diag = SamplingDiagnostics(
            total_rows=5,
            total_cols=2,
            sampled_rows=5,
            sampled_cols=2,
            sampled_cells=10,
        )
        c1 = ColumnTypeProfile(
            col_index=1,
            state=InferenceState.INFERRED,
            candidate_type=ColumnType.INTEGER,
            total_cells=5,
            populated_cells=5,
            null_cells=0,
            nullability_ratio=0.0,
            category_counts={"INTEGER": 5},
            inferred_type=ColumnType.INTEGER,
            heuristic_support_score=1.0,
        )
        c2 = ColumnTypeProfile(
            col_index=2,
            state=InferenceState.AMBIGUOUS,
            candidate_type=None,
            total_cells=5,
            populated_cells=5,
            null_cells=0,
            nullability_ratio=0.0,
            category_counts={"INTEGER": 3, "STRING": 2},
            inferred_type=ColumnType.STRING,  # projected carrier
            heuristic_support_score=0.45,
            is_ambiguous=True,
            requires_human_review=True,
        )
        report = RegionTypeReport(
            region_id="reg_01",
            sheet_name="Sheet1",
            body_row_start=2,
            body_row_end=6,
            body_col_start=1,
            body_col_end=2,
            columns={1: c1, 2: c2},
            has_ambiguous_columns=True,
            sampling=diag,
        )
        m01_types = report.to_m01_inferred_types()
        assert m01_types == {1: ColumnType.INTEGER, 2: ColumnType.STRING}
