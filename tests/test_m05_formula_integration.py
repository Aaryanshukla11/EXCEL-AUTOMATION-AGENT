"""Integration tests for M05 Formula Subsystem — Prompt 4 Precedent Extraction.

Validates end-to-end AST reference traversal and precedent extraction across
cells, ranges, whole-column ranges, and structured table references.
"""

from excel_intel.formulas.graph import extract_precedents
from excel_intel.formulas.models import (
    CellReferenceNode,
    FormulaParseStatus,
    RangeReferenceNode,
    StructuredReferenceNode,
)
from excel_intel.formulas.parser import FormulaParser


def test_extract_precedents_mixed_formula() -> None:
    """Test extracting precedents across cells, ranges, and structured references."""
    formula = "=SUM(A1:B10) + Table1[Sales] - Sheet2!$C$5 + VLOOKUP(D1, 'Rate Table'!A:B, 2, FALSE)"
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    assert res.ast is not None

    precedents = extract_precedents(res.ast)
    assert len(precedents) == 5

    # 1. Range A1:B10
    assert isinstance(precedents[0], RangeReferenceNode)
    assert precedents[0].start_cell.col == 1 and precedents[0].start_cell.row == 1
    assert precedents[0].end_cell.col == 2 and precedents[0].end_cell.row == 10

    # 2. Structured reference Table1[Sales]
    assert isinstance(precedents[1], StructuredReferenceNode)
    assert precedents[1].table_name == "Table1"
    assert precedents[1].column_name == "Sales"

    # 3. Cell Sheet2!$C$5
    assert isinstance(precedents[2], CellReferenceNode)
    assert precedents[2].sheet_name == "Sheet2"
    assert precedents[2].col == 3 and precedents[2].row == 5

    # 4. Cell D1
    assert isinstance(precedents[3], CellReferenceNode)
    assert precedents[3].col == 4 and precedents[3].row == 1

    # 5. Whole column range 'Rate Table'!A:B
    assert isinstance(precedents[4], RangeReferenceNode)
    assert precedents[4].sheet_name == "Rate Table"
    assert precedents[4].is_full_col is True


def test_complex_index_match_formula() -> None:
    """Test complex real-world INDEX/MATCH formula parsing."""
    formula = "=INDEX(Data!A1:Z100, MATCH(B1, Data!A1:A100, 0), MATCH(C1, Data!A1:Z1, 0))"
    res = FormulaParser(formula).parse()
    assert res.status == FormulaParseStatus.PARSED_COMPLETE
    assert res.is_success is True

    precs = extract_precedents(res.ast)
    assert len(precs) == 5
