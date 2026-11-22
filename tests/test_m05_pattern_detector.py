"""Unit tests for M05 PatternDetector."""

import datetime
import pytest

from excel_intel.types.models import ValueCategory
from excel_intel.types.pattern_detector import PatternDetector


class TestPatternDetector:
    """Test suite verifying fine-grained value classification and normalization."""

    def test_detect_null_values(self) -> None:
        # Truly empty/blank values
        for val in [None, "", "   ", "\t\n"]:
            norm = PatternDetector.detect_value(val)
            assert norm.category == ValueCategory.NULL
            assert norm.is_null_marker is False

        # Textual null markers with treat_null_markers_as_null=True
        for val in ["N/A", "n/a", "NA", "-", "--", "None", "null", "NULL"]:
            norm = PatternDetector.detect_value(val, treat_null_markers_as_null=True)
            assert norm.category == ValueCategory.NULL
            assert norm.is_null_marker is True
            assert norm.null_marker_text == val.strip()

    def test_distinguish_legitimate_text_tokens(self) -> None:
        """Verify that '-' and 'N/A' can be treated as legitimate text when requested."""
        dash = PatternDetector.detect_value("-", treat_null_markers_as_null=False)
        assert dash.category == ValueCategory.STRING
        assert dash.normalized_value == "-"
        assert dash.is_null_marker is True

        na = PatternDetector.detect_value("N/A", treat_null_markers_as_null=False)
        assert na.category == ValueCategory.STRING
        assert na.normalized_value == "N/A"
        assert na.is_null_marker is True

    def test_distinguish_excel_error_from_text_null(self) -> None:
        """Verify #N/A is an Excel formula error, distinct from textual 'N/A'."""
        err = PatternDetector.detect_value("#N/A")
        assert err.category == ValueCategory.ERROR
        assert err.error_code == "#N/A"
        assert err.is_null_marker is False

        text_na = PatternDetector.detect_value("N/A")
        assert text_na.category == ValueCategory.NULL
        assert text_na.is_null_marker is True

    def test_detect_error_values(self) -> None:
        for val in ["#N/A", "#VALUE!", "#REF!", "#DIV/0!", "#NUM!", "#NAME?", "#NULL!"]:
            norm = PatternDetector.detect_value(val)
            assert norm.category == ValueCategory.ERROR
            assert norm.error_code == val

    def test_detect_boolean_values(self) -> None:
        for val in [True, False, "TRUE", "false", "True", "False", "Yes", "NO", "y", "n"]:
            norm = PatternDetector.detect_value(val)
            assert norm.category == ValueCategory.BOOLEAN, f"Failed for {val!r}"

    def test_detect_numeric_integers(self) -> None:
        assert PatternDetector.detect_value(42).category == ValueCategory.INTEGER
        assert PatternDetector.detect_value(-999).category == ValueCategory.INTEGER
        assert PatternDetector.detect_value("12345").category == ValueCategory.INTEGER
        assert PatternDetector.detect_value("1,000,000").category == ValueCategory.INTEGER
        assert PatternDetector.detect_value("-2,500").category == ValueCategory.INTEGER

    def test_detect_numeric_decimals(self) -> None:
        assert PatternDetector.detect_value(3.14159).category == ValueCategory.DECIMAL
        assert PatternDetector.detect_value("-0.005").category == ValueCategory.DECIMAL
        assert PatternDetector.detect_value("1,234.56").category == ValueCategory.DECIMAL
        assert PatternDetector.detect_value("1.25e-3").category == ValueCategory.DECIMAL

    def test_detect_currency_values(self) -> None:
        c1 = PatternDetector.detect_value("$1,250.50")
        assert c1.category == ValueCategory.CURRENCY
        assert c1.currency_symbol == "$"
        assert c1.normalized_value == 1250.50
        assert c1.is_accounting_negative is False

        # Accounting negative with parentheses
        c2 = PatternDetector.detect_value("($150.00)")
        assert c2.category == ValueCategory.CURRENCY
        assert c2.currency_symbol == "$"
        assert c2.normalized_value == -150.00
        assert c2.is_accounting_negative is True

        # Euro and Pound
        assert PatternDetector.detect_value("€500").category == ValueCategory.CURRENCY
        assert PatternDetector.detect_value("£99.95").category == ValueCategory.CURRENCY

    def test_detect_percentage_values(self) -> None:
        p1 = PatternDetector.detect_value("15.5%")
        assert p1.category == ValueCategory.PERCENTAGE
        assert p1.normalized_value == 15.5
        assert p1.percentage_factor == 0.155

        p2 = PatternDetector.detect_value("-2.5%")
        assert p2.category == ValueCategory.PERCENTAGE
        assert p2.normalized_value == -2.5

    def test_detect_date_values(self) -> None:
        # ISO-8601
        d1 = PatternDetector.detect_value("2024-01-15")
        assert d1.category == ValueCategory.DATE
        assert d1.parsed_date == datetime.date(2024, 1, 15)

        # Standard US Date
        d2 = PatternDetector.detect_value("01/15/2024")
        assert d2.category == ValueCategory.DATE
        assert d2.parsed_date == datetime.date(2024, 1, 15)

        # Python date object directly
        d3 = PatternDetector.detect_value(datetime.date(2024, 6, 1))
        assert d3.category == ValueCategory.DATE
        assert d3.parsed_date == datetime.date(2024, 6, 1)

    def test_detect_date_ambiguity(self) -> None:
        # "01/02/03" has ambiguous order (is 03 year? is 01 day or month?)
        d = PatternDetector.detect_value("01/02/03")
        assert d.category == ValueCategory.DATE
        assert d.has_date_order_ambiguity is True

    def test_detect_date_serial_with_format(self) -> None:
        d = PatternDetector.detect_value(45458, format_code="yyyy-mm-dd")
        assert d.category == ValueCategory.DATE
        assert d.is_date_serial is True
        assert d.parsed_date == datetime.date(2024, 6, 15)

    def test_detect_boolean_candidate_integers(self) -> None:
        z = PatternDetector.detect_value(0)
        assert z.category == ValueCategory.INTEGER
        assert z.is_boolean_candidate is True

        o = PatternDetector.detect_value(1)
        assert o.category == ValueCategory.INTEGER
        assert o.is_boolean_candidate is True

        two = PatternDetector.detect_value(2)
        assert two.category == ValueCategory.INTEGER
        assert two.is_boolean_candidate is False

    def test_detect_formulas(self) -> None:
        f = PatternDetector.detect_value("=SUM(A1:B10)")
        assert f.category == ValueCategory.FORMULA
        assert f.raw_value == "=SUM(A1:B10)"

    def test_detect_plain_strings(self) -> None:
        s = PatternDetector.detect_value("Product SKU ABC-123")
        assert s.category == ValueCategory.STRING
        assert s.normalized_value == "Product SKU ABC-123"
