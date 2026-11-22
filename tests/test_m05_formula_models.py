"""Unit tests for M05 Formula AST Models.

Validates immutability, data contract fields, canonical A1 serialization,
array rectangularity enforcement, and result status properties.
"""

import pytest
from pydantic import ValidationError

from excel_intel.formulas.models import (
    ASTNodeType,
    ArrayLiteralNode,
    BinaryOpNode,
    CellReferenceNode,
    FormulaParseResult,
    FormulaParseStatus,
    FunctionCallNode,
    LiteralNode,
    PostfixOpNode,
    RangeReferenceNode,
    StructuredReferenceNode,
    UnaryOpNode,
    UnparsedFormulaNode,
    UnsupportedFormulaNode,
)


def test_cell_reference_node_properties_and_serialization() -> None:
    """Test CellReferenceNode fields, validation bounds, and canonical to_a1()."""
    node = CellReferenceNode(
        span=(0, 2),
        col=1,
        row=10,
        col_letter="A",
        col_absolute=True,
        row_absolute=False,
        raw_reference="$A10",
    )
    assert node.node_type == ASTNodeType.CELL_REFERENCE
    assert node.to_a1() == "$A10"

    # With sheet and workbook
    node_full = CellReferenceNode(
        span=(0, 20),
        col=27,
        row=100,
        col_letter="AA",
        col_absolute=True,
        row_absolute=True,
        sheet_name="Summary Q1",
        workbook_name="Budget 2024.xlsx",
        raw_reference="[Budget 2024.xlsx]'Summary Q1'!$AA$100",
    )
    assert node_full.to_a1() == "[Budget 2024.xlsx]'Summary Q1'!$AA$100"

    # Immutability
    with pytest.raises(ValidationError):
        node.row = 20  # type: ignore[misc]

    # Out of bounds row / col
    with pytest.raises(ValidationError):
        CellReferenceNode(
            span=(0, 2),
            col=0,  # col < 1
            row=1,
            col_letter="A",
            raw_reference="A1",
        )

    with pytest.raises(ValidationError):
        CellReferenceNode(
            span=(0, 2),
            col=1,
            row=1048577,  # row > 1048576
            col_letter="A",
            raw_reference="A1048577",
        )


def test_literal_node_immutability() -> None:
    """Test LiteralNode attributes and immutability."""
    lit = LiteralNode(
        span=(0, 5),
        value=42.5,
        literal_kind="NUMBER",
        raw_text="42.5",
    )
    assert lit.node_type == ASTNodeType.LITERAL
    assert lit.value == 42.5

    with pytest.raises(ValidationError):
        lit.value = 100  # type: ignore[misc]


def test_array_literal_rectangular_enforcement() -> None:
    """Test ArrayLiteralNode validator enforcing strict rectangular matrix."""
    elem1 = LiteralNode(span=(1, 2), value=1, literal_kind="NUMBER", raw_text="1")
    elem2 = LiteralNode(span=(3, 4), value=2, literal_kind="NUMBER", raw_text="2")
    elem3 = LiteralNode(span=(5, 6), value=3, literal_kind="NUMBER", raw_text="3")
    elem4 = LiteralNode(span=(7, 8), value=4, literal_kind="NUMBER", raw_text="4")

    # Valid 2x2
    arr = ArrayLiteralNode(
        span=(0, 9),
        rows=[[elem1, elem2], [elem3, elem4]],
        row_count=2,
        col_count=2,
    )
    assert arr.row_count == 2
    assert arr.col_count == 2
    assert arr.is_rectangular is True

    # Invalid ragged array: row 0 has 2 elements, row 1 has 1 element
    with pytest.raises(ValueError, match="Array literal is not rectangular"):
        ArrayLiteralNode(
            span=(0, 7),
            rows=[[elem1, elem2], [elem3]],
            row_count=2,
            col_count=2,
        )

    # Empty array literal
    with pytest.raises(ValueError, match="Array literal cannot have zero rows"):
        ArrayLiteralNode(
            span=(0, 2),
            rows=[],
            row_count=1,
            col_count=1,
        )


def test_formula_parse_result_status_and_properties() -> None:
    """Test FormulaParseResult success and error properties."""
    lit = LiteralNode(span=(1, 3), value=10, literal_kind="NUMBER", raw_text="10")
    success_res = FormulaParseResult(
        raw_formula="=10",
        status=FormulaParseStatus.PARSED_COMPLETE,
        ast=lit,
    )
    assert success_res.is_success is True

    err_res = FormulaParseResult(
        raw_formula="=10+",
        status=FormulaParseStatus.PARSE_ERROR,
        ast=UnparsedFormulaNode(
            span=(3, 4),
            raw_formula="=10+",
            error_message="Unexpected end of input",
            error_position=3,
        ),
        error_message="Unexpected end of input",
        error_position=3,
    )
    assert err_res.is_success is False


def test_unsupported_formula_node() -> None:
    """Test UnsupportedFormulaNode preserves category and span."""
    unsup = UnsupportedFormulaNode(
        span=(0, 3),
        raw_formula="A1#",
        syntax_category="DYNAMIC_ARRAY_SPILL",
        details="Dynamic array spill hash is unsupported",
    )
    assert unsup.node_type == ASTNodeType.UNSUPPORTED
    assert unsup.syntax_category == "DYNAMIC_ARRAY_SPILL"
    assert unsup.span == (0, 3)
