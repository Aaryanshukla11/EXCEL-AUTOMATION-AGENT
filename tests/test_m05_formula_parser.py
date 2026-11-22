"""Unit tests for M05 Formula Parser.

Validates operator precedence, left associativity, unary and postfix binding,
ranges (2D, 3D, full row, full column), function calls, structured references,
and array constant rectangularity.
"""

import pytest

from excel_intel.formulas.models import (
    ASTNodeType,
    ArrayLiteralNode,
    BinaryOpNode,
    CellReferenceNode,
    FormulaParseStatus,
    FunctionCallNode,
    LiteralNode,
    PostfixOpNode,
    RangeReferenceNode,
    StructuredReferenceNode,
    UnaryOpNode,
)
from excel_intel.formulas.parser import FormulaParser


def test_operator_precedence_arithmetic() -> None:
    """Test standard Excel precedence: * binds tighter than +."""
    # 1 + 2 * 3 -> 1 + (2 * 3)
    res = FormulaParser("=1 + 2 * 3").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, BinaryOpNode)
    assert root.operator == "+"
    assert isinstance(root.left, LiteralNode)
    assert root.left.value == 1
    assert isinstance(root.right, BinaryOpNode)
    assert root.right.operator == "*"
    assert root.right.left.value == 2  # type: ignore[union-attr]
    assert root.right.right.value == 3  # type: ignore[union-attr]


def test_operator_precedence_comparison_lowest() -> None:
    """Test comparison operators have lower precedence than arithmetic."""
    # A1 + 2 = 5 -> (A1 + 2) = 5
    res = FormulaParser("=A1 + 2 = 5").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, BinaryOpNode)
    assert root.operator == "="
    assert isinstance(root.left, BinaryOpNode)
    assert root.left.operator == "+"
    assert isinstance(root.right, LiteralNode)
    assert root.right.value == 5


def test_power_operator_left_associativity() -> None:
    """Test power operator ^ is left-associative in Excel: 2^3^2 = (2^3)^2."""
    res = FormulaParser("=2 ^ 3 ^ 2").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, BinaryOpNode)
    assert root.operator == "^"
    assert isinstance(root.left, BinaryOpNode)
    assert root.left.operator == "^"
    assert root.left.left.value == 2  # type: ignore[union-attr]
    assert root.left.right.value == 3  # type: ignore[union-attr]
    assert root.right.value == 2  # type: ignore[union-attr]


def test_unary_and_postfix_operators() -> None:
    """Test unary prefix - and postfix %."""
    res = FormulaParser("=-A1 + 50%").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, BinaryOpNode)
    assert root.operator == "+"
    assert isinstance(root.left, UnaryOpNode)
    assert root.left.operator == "-"
    assert isinstance(root.right, PostfixOpNode)
    assert root.right.operator == "%"


def test_2d_and_3d_range_references() -> None:
    """Test parsing of 2D ranges, sheet-qualified ranges, and 3D ranges."""
    # Simple 2D range
    res = FormulaParser("=A1:B10").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, RangeReferenceNode)
    assert root.start_cell.col == 1 and root.start_cell.row == 1
    assert root.end_cell.col == 2 and root.end_cell.row == 10
    assert root.is_3d is False

    # 3D sheet range
    res_3d = FormulaParser("=Sheet1:Sheet3!A1:B10").parse()
    assert res_3d.status == FormulaParseStatus.PARSED_COMPLETE
    root_3d = res_3d.ast
    assert isinstance(root_3d, RangeReferenceNode)
    assert root_3d.is_3d is True
    assert root_3d.sheet_name == "Sheet1"
    assert root_3d.sheet_end == "Sheet3"


def test_whole_column_and_whole_row_ranges() -> None:
    """Test parsing of whole column A:A and whole row 1:1 ranges."""
    # Whole column A:B
    res_col = FormulaParser("=A:B").parse()
    assert res_col.status == FormulaParseStatus.PARSED_COMPLETE
    root_col = res_col.ast
    assert isinstance(root_col, RangeReferenceNode)
    assert root_col.is_full_col is True
    assert root_col.start_cell.col == 1 and root_col.start_cell.row == 1
    assert root_col.end_cell.col == 2 and root_col.end_cell.row == 1048576

    # Whole row 1:5
    res_row = FormulaParser("=1:5").parse()
    assert res_row.status == FormulaParseStatus.PARSED_COMPLETE
    root_row = res_row.ast
    assert isinstance(root_row, RangeReferenceNode)
    assert root_row.is_full_row is True
    assert root_row.start_cell.col == 1 and root_row.start_cell.row == 1
    assert root_row.end_cell.col == 16384 and root_row.end_cell.row == 5


def test_nested_function_calls() -> None:
    """Test nested function calls with expressions as arguments."""
    formula = "=IF(A1 > 0, SUM(B1:B10), AVERAGE(C1:C10))"
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, FunctionCallNode)
    assert root.function_name == "IF"
    assert len(root.arguments) == 3
    # arg 0: A1 > 0
    assert isinstance(root.arguments[0], BinaryOpNode)
    # arg 1: SUM(B1:B10)
    assert isinstance(root.arguments[1], FunctionCallNode)
    assert root.arguments[1].function_name == "SUM"
    # arg 2: AVERAGE(C1:C10)
    assert isinstance(root.arguments[2], FunctionCallNode)
    assert root.arguments[2].function_name == "AVERAGE"


def test_structured_table_references() -> None:
    """Test parsing of structured references with headers, totals, @."""
    res1 = FormulaParser("=Table1[Sales]").parse()
    assert res1.status == FormulaParseStatus.PARSED_COMPLETE
    assert isinstance(res1.ast, StructuredReferenceNode)
    assert res1.ast.table_name == "Table1"
    assert res1.ast.column_name == "Sales"

    res2 = FormulaParser("=Table1[[#Headers],[Sales]]").parse()
    assert res2.status == FormulaParseStatus.PARSED_COMPLETE
    assert isinstance(res2.ast, StructuredReferenceNode)
    assert "#Headers" in res2.ast.specifiers
    assert res2.ast.column_name == "Sales"

    res3 = FormulaParser("=[@Quantity] * [@[Unit Price]]").parse()
    assert res3.status == FormulaParseStatus.PARSED_COMPLETE
    root = res3.ast
    assert isinstance(root, BinaryOpNode)
    assert isinstance(root.left, StructuredReferenceNode)
    assert root.left.is_this_row is True
    assert root.left.column_name == "Quantity"
    assert isinstance(root.right, StructuredReferenceNode)
    assert root.right.is_this_row is True
    assert root.right.column_name == "Unit Price"


def test_array_constant_rectangular() -> None:
    """Test valid 2D array constants."""
    res = FormulaParser("={1, 2, 3; 4, 5, 6}").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, ArrayLiteralNode)
    assert root.row_count == 2
    assert root.col_count == 3
    assert root.is_rectangular is True


def test_array_constant_ragged_error() -> None:
    """Test ragged array constant is rejected with PARSE_ERROR."""
    res = FormulaParser("={1, 2; 3}").parse()
    assert res.status == FormulaParseStatus.PARSE_ERROR
    assert "not rectangular" in (res.error_message or "")


def test_array_constant_formula_element_error() -> None:
    """Test array constant containing cell reference is rejected with PARSE_ERROR."""
    res = FormulaParser("={1, A1}").parse()
    assert res.status == FormulaParseStatus.PARSE_ERROR
    assert "Array constants cannot contain" in (res.error_message or "")


def test_unauthorized_functions_parse_normally() -> None:
    """Test syntactically valid functions that are not on allowlists parse with PARSED_COMPLETE.
    
    Security allowlisting is strictly decoupled from syntactic parsing.
    """
    for formula, expected_name, arg_count in [
        ('=CMD("calc.exe")', "CMD", 1),
        ('=WEBSERVICE("http://insecure.local/api")', "WEBSERVICE", 1),
        ("=ARBITRARY_CUSTOM_FUNCTION(A1, B2, 100)", "ARBITRARY_CUSTOM_FUNCTION", 3),
        ("=INDIRECT(CONCATENATE(A1, B1))", "INDIRECT", 1),
    ]:
        res = FormulaParser(formula).parse()
        assert res.status == FormulaParseStatus.PARSED_COMPLETE, f"Failed for {formula}"
        assert res.is_success is True
        assert isinstance(res.ast, FunctionCallNode)
        assert res.ast.function_name == expected_name
        assert len(res.ast.arguments) == arg_count


def test_resource_limits_nesting_depth_exceeded() -> None:
    """Test nesting depth exceeding 64 returns PARSE_ERROR safely."""
    # 65 levels of nested parens
    formula = "=" + "(" * 65 + "1" + ")" * 65
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.PARSE_ERROR
    assert "nesting depth exceeds" in (res.error_message or "").lower()


def test_resource_limits_formula_length_exceeded() -> None:
    """Test formula length exceeding MAX_FORMULA_LENGTH (16,384) returns PARSE_ERROR safely."""
    huge_formula = "=A1 + " + "1 + " * 4100  # > 16,400 chars
    res = FormulaParser(huge_formula).parse()
    assert res.status == FormulaParseStatus.PARSE_ERROR
    assert "exceeds maximum allowed limit" in (res.error_message or "").lower()


def test_deterministic_repeatability() -> None:
    """Test parser produces 100% byte-for-byte identical AST outputs across multiple runs."""
    formula = "=SUM(A1:B10) * 1.05 + INDEX(Data!$C$1:$Z$100, MATCH(B1, Data!$A$1:$A$100, 0), 2)"
    baseline = FormulaParser(formula).parse()
    assert baseline.status == FormulaParseStatus.PARSED_COMPLETE

    for _ in range(50):
        iteration = FormulaParser(formula).parse()
        assert iteration.status == baseline.status
        assert iteration.ast == baseline.ast
        assert iteration.raw_formula == baseline.raw_formula


def test_adversarial_malformed_inputs_handled_safely() -> None:
    """Test adversarial malformed inputs produce structured PARSE_ERROR without unhandled exceptions."""
    adversarial_cases = [
        "=(",
        "=SUM(",
        "=A1+",
        '=1 + "unclosed string',
        "={1, 2; 3, }",
        "=((((((1))))",
        "=+*&",
        "=A1:",
        "=:B2",
        "=",
        "",
        "   ",
        "=Sheet1!",
        "='Unclosed Sheet!A1",
    ]
    for case in adversarial_cases:
        res = FormulaParser(case).parse()
        assert res.status == FormulaParseStatus.PARSE_ERROR, f"Expected PARSE_ERROR for: {case!r}"
        assert res.is_success is False
        assert res.error_message is not None
