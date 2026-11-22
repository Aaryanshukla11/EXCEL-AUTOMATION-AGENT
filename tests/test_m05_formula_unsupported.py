"""Unit tests for M05 Formula Parser Recognized Unsupported Syntax.

Validates that dynamic array spill hash (A1#), lambda helper functions
(LAMBDA, MAP, REDUCE, etc.), and third-party UDFs (Bloomberg.BDP)
are recognized, preserved with character spans, classified accurately,
and strictly flagged as UNSUPPORTED_SYNTAX without fabricated AST semantics.
"""

import pytest

from excel_intel.formulas.models import (
    ASTNodeType,
    FormulaParseStatus,
    UnsupportedFormulaNode,
)
from excel_intel.formulas.parser import FormulaParser


def test_dynamic_array_spill_hash() -> None:
    """Test dynamic array spill operator # produces UNSUPPORTED_SYNTAX."""
    res = FormulaParser("=A1#").parse()
    assert res.status == FormulaParseStatus.UNSUPPORTED_SYNTAX
    assert res.syntax_category == "DYNAMIC_ARRAY_SPILL"
    assert res.is_success is False
    assert isinstance(res.ast, UnsupportedFormulaNode)
    assert res.ast.node_type == ASTNodeType.UNSUPPORTED
    assert res.ast.syntax_category == "DYNAMIC_ARRAY_SPILL"
    assert res.ast.raw_formula == "A1#"


def test_dynamic_array_spill_in_expression() -> None:
    """Test spill operator inside expression flags formula as UNSUPPORTED_SYNTAX."""
    res = FormulaParser("=SUM(Sheet1!B2#) * 10").parse()
    assert res.status == FormulaParseStatus.UNSUPPORTED_SYNTAX
    assert res.syntax_category == "DYNAMIC_ARRAY_SPILL"
    assert res.is_success is False


def test_lambda_helper_functions() -> None:
    """Test LAMBDA, MAP, REDUCE, SCAN, MAKEARRAY, BYROW, BYCOL are flagged."""
    helpers = ["LAMBDA", "MAP", "REDUCE", "SCAN", "MAKEARRAY", "BYROW", "BYCOL"]
    for helper in helpers:
        formula = f"={helper}(A1:A10, B1:B10)"
        res = FormulaParser(formula).parse()
        assert res.status == FormulaParseStatus.UNSUPPORTED_SYNTAX, f"Failed for {helper}"
        assert res.syntax_category == "LAMBDA_HELPER"
        assert res.is_success is False
        assert isinstance(res.ast, UnsupportedFormulaNode)
        assert res.ast.syntax_category == "LAMBDA_HELPER"


def test_third_party_udf_detection() -> None:
    """Test third-party UDFs with dot namespaces (e.g. Bloomberg.BDP) are flagged."""
    formula = '=Bloomberg.BDP("AAPL US Equity", "PX_LAST")'
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.UNSUPPORTED_SYNTAX
    assert res.syntax_category == "THIRD_PARTY_UDF"
    assert res.is_success is False
    assert isinstance(res.ast, UnsupportedFormulaNode)
    assert res.ast.syntax_category == "THIRD_PARTY_UDF"


def test_standard_dot_function_is_supported() -> None:
    """Test standard Excel functions with dots (e.g. WORKDAY.INTL, NORM.S.DIST) are parsed successfully."""
    # WORKDAY.INTL is in standard Excel catalog, not third party
    formula = "=WORKDAY.INTL(A1, 5, 1)"
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    assert res.is_success is True


def test_external_uri_chain_detection() -> None:
    """Test complex external network URI links are recognized as UNSUPPORTED_SYNTAX."""
    formula = "='https://sharepoint.corp.com/teams/[Budget.xlsx]Sheet1'!A1"
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.UNSUPPORTED_SYNTAX
    assert res.syntax_category == "EXTERNAL_URI_CHAIN"
    assert res.is_success is False
    assert isinstance(res.ast, UnsupportedFormulaNode)
    assert res.ast.syntax_category == "EXTERNAL_URI_CHAIN"
