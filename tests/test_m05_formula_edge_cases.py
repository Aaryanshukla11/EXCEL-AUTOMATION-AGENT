"""Additional edge case tests for M05 Formula Lexer and Parser.

Tests unary chaining, case-insensitivity, scientific notation,
error literal handling, and boundary cell coordinates.
"""

import pytest

from excel_intel.formulas.models import (
    BinaryOpNode,
    CellReferenceNode,
    FormulaParseStatus,
    FunctionCallNode,
    LiteralNode,
    PostfixOpNode,
    UnaryOpNode,
)
from excel_intel.formulas.parser import FormulaParser


def test_unary_chaining_and_signs() -> None:
    """Test multiple unary operators chained together e.g. --5 or -+A1."""
    res = FormulaParser("=--5").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, UnaryOpNode)
    assert root.operator == "-"
    assert isinstance(root.operand, UnaryOpNode)
    assert root.operand.operator == "-"
    assert isinstance(root.operand.operand, LiteralNode)
    assert root.operand.operand.value == 5


def test_parenthesis_precedence_override() -> None:
    """Test parentheses override default arithmetic operator precedence: (1 + 2) * 3."""
    res = FormulaParser("=(1 + 2) * 3").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, BinaryOpNode)
    assert root.operator == "*"
    assert isinstance(root.left, BinaryOpNode)
    assert root.left.operator == "+"
    assert root.right.value == 3  # type: ignore[union-attr]


def test_case_insensitivity_functions_and_booleans() -> None:
    """Test function names and booleans are case-insensitive and normalized to uppercase."""
    res = FormulaParser("=if(true, sum(a1, b1), false)").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, FunctionCallNode)
    assert root.function_name == "IF"
    # True literal
    assert isinstance(root.arguments[0], LiteralNode)
    assert root.arguments[0].value is True
    # sum function
    assert isinstance(root.arguments[1], FunctionCallNode)
    assert root.arguments[1].function_name == "SUM"
    # False literal
    assert isinstance(root.arguments[2], LiteralNode)
    assert root.arguments[2].value is False


def test_scientific_notation_numbers() -> None:
    """Test scientific notation with negative and positive exponents."""
    res = FormulaParser("=1.5e-3 + 2.5E+4").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, BinaryOpNode)
    assert root.left.value == 0.0015  # type: ignore[union-attr]
    assert root.right.value == 25000.0  # type: ignore[union-attr]


def test_maximum_boundary_cell_coordinates() -> None:
    """Test maximum valid Excel coordinate XFD1048576."""
    res = FormulaParser("=$XFD$1048576").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, CellReferenceNode)
    assert root.col == 16384
    assert root.row == 1048576
    assert root.col_letter == "XFD"
    assert root.col_absolute is True
    assert root.row_absolute is True


def test_excel_error_literals_in_expressions() -> None:
    """Test Excel error values treated as literal error nodes."""
    res = FormulaParser("=IF(A1 = #N/A, #DIV/0!, #REF!)").parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    root = res.ast
    assert isinstance(root, FunctionCallNode)
    cond = root.arguments[0]
    assert isinstance(cond, BinaryOpNode)
    assert isinstance(cond.right, LiteralNode)
    assert cond.right.literal_kind == "ERROR"
    assert cond.right.value == "#N/A"

    assert isinstance(root.arguments[1], LiteralNode)
    assert root.arguments[1].value == "#DIV/0!"

    assert isinstance(root.arguments[2], LiteralNode)
    assert root.arguments[2].value == "#REF!"
