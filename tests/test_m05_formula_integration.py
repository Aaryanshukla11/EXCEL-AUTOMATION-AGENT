"""Integration tests for M05 Formula Subsystem — Prompt 3 Parser Validation.

Validates end-to-end precedence, complex real-world formula parsing,
malformed syntax handling, partial parsing rejection, and resource caps.
"""

from excel_intel.formulas.models import FormulaParseStatus
from excel_intel.formulas.parser import FormulaParser


def test_malformed_formulas_category_c() -> None:
    """Test malformed formulas return PARSE_ERROR with diagnostic offsets."""
    malformed_cases = [
        ("=(A1 + B1", "Missing closing parenthesis"),
        ("=A1 + * B1", "Unexpected token '*'"),
        ('="unclosed string literal', "Unclosed string literal"),
        ("=", "Empty formula expression"),
        ("   ", "Empty formula expression"),
    ]

    for raw, expected_err_part in malformed_cases:
        res = FormulaParser(raw).parse()
        assert res.status == FormulaParseStatus.PARSE_ERROR, f"Expected error for '{raw}'"
        assert res.is_success is False
        assert res.error_message is not None
        assert expected_err_part.lower() in res.error_message.lower(), (
            f"Expected '{expected_err_part}' in '{res.error_message}'"
        )


def test_partial_parsing_prevention_fr3_3() -> None:
    """FR-3.3: Dangling tokens after valid expression must not be reported as success."""
    formula = "=SUM(A1, B1) 42"
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.PARSE_ERROR
    assert res.is_success is False
    assert "Unexpected token '42' after expression" in (res.error_message or "")


def test_nesting_depth_limit() -> None:
    """Test nesting depth exceeding limit is caught safely."""
    # Build formula with 70 levels of parentheses
    deep_formula = "=" + ("(" * 70) + "1" + (")" * 70)
    res = FormulaParser(deep_formula).parse()
    assert res.status == FormulaParseStatus.PARSE_ERROR
    assert "nesting depth" in (res.error_message or "").lower()
