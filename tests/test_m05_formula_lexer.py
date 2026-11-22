"""Unit tests for M05 Formula Lexer.

Validates tokenization of numbers, strings, booleans, error values,
cell references, structured table references, operators, and safety limits.
"""

import pytest

from excel_intel.formulas.lexer import (
    MAX_FORMULA_LENGTH,
    FormulaLexer,
    LexerError,
    TokenType,
    col_letter_to_index,
    index_to_col_letter,
)


def test_col_letter_conversion() -> None:
    """Test column letter to index and inverse mapping."""
    assert col_letter_to_index("A") == 1
    assert col_letter_to_index("Z") == 26
    assert col_letter_to_index("AA") == 27
    assert col_letter_to_index("XFD") == 16384

    assert index_to_col_letter(1) == "A"
    assert index_to_col_letter(26) == "Z"
    assert index_to_col_letter(27) == "AA"
    assert index_to_col_letter(16384) == "XFD"


def test_lexer_literals() -> None:
    """Test tokenization of numbers, strings, booleans, and error values."""
    formula = '=123 + 45.67 * 1e-4 & "Hello ""World""" = TRUE <> #N/A'
    lexer = FormulaLexer(formula)
    tokens = lexer.tokenize()

    types = [t.token_type for t in tokens]
    expected_types = [
        TokenType.NUMBER,
        TokenType.OP_ADD,
        TokenType.NUMBER,
        TokenType.OP_MUL,
        TokenType.NUMBER,
        TokenType.OP_CONCAT,
        TokenType.STRING,
        TokenType.OP_EQ,
        TokenType.BOOLEAN,
        TokenType.OP_NE,
        TokenType.ERROR,
        TokenType.EOF,
    ]
    assert types == expected_types
    # Verify string unescaped
    str_tok = tokens[6]
    assert str_tok.value == 'Hello "World"'


def test_lexer_cell_references() -> None:
    """Test tokenization of simple, qualified, and 3D cell references."""
    formula = "=A1 + $B$2 + Sheet1!C3 + 'Sales Summary'!$D$4 + [Budget.xlsx]Sheet2!E5"
    lexer = FormulaLexer(formula)
    tokens = lexer.tokenize()

    cell_tokens = [t for t in tokens if t.token_type == TokenType.CELL_REF]
    assert len(cell_tokens) == 5
    assert cell_tokens[0].raw_text == "A1"
    assert cell_tokens[1].raw_text == "$B$2"
    assert cell_tokens[2].raw_text == "Sheet1!C3"
    assert cell_tokens[3].raw_text == "'Sales Summary'!$D$4"
    assert cell_tokens[4].raw_text == "[Budget.xlsx]Sheet2!E5"


def test_lexer_structured_references() -> None:
    """Test tokenization of Excel table structured references."""
    formula = "=Table1[Sales] + Table1[[#Headers],[Sales]] + [@Quantity] + [@[Unit Price]]"
    lexer = FormulaLexer(formula)
    tokens = lexer.tokenize()

    struct_tokens = [t for t in tokens if t.token_type == TokenType.STRUCTURED_REF]
    assert len(struct_tokens) == 4
    assert struct_tokens[0].raw_text == "Table1[Sales]"
    assert struct_tokens[1].raw_text == "Table1[[#Headers],[Sales]]"
    assert struct_tokens[2].raw_text == "[@Quantity]"
    assert struct_tokens[3].raw_text == "[@[Unit Price]]"


def test_lexer_operators() -> None:
    """Test tokenization of arithmetic, comparison, and delimiter tokens."""
    formula = "=(1 + 2 - 3 * 4 / 5 ^ 6 % <= >= <> < > : , ; { })"
    lexer = FormulaLexer(formula)
    tokens = lexer.tokenize()

    op_types = [t.token_type for t in tokens if t.token_type != TokenType.EOF]
    assert TokenType.OP_ADD in op_types
    assert TokenType.OP_SUB in op_types
    assert TokenType.OP_MUL in op_types
    assert TokenType.OP_DIV in op_types
    assert TokenType.OP_EXP in op_types
    assert TokenType.OP_PERCENT in op_types
    assert TokenType.OP_LTE in op_types
    assert TokenType.OP_GTE in op_types
    assert TokenType.OP_NE in op_types
    assert TokenType.OP_LT in op_types
    assert TokenType.OP_GT in op_types
    assert TokenType.OP_COLON in op_types
    assert TokenType.OP_COMMA in op_types
    assert TokenType.OP_SEMICOLON in op_types
    assert TokenType.LBRACE in op_types
    assert TokenType.RBRACE in op_types


def test_lexer_spill_operator() -> None:
    """Test tokenization of spill operator '#' following a cell reference."""
    formula = "=A1#"
    lexer = FormulaLexer(formula)
    tokens = lexer.tokenize()

    assert tokens[0].token_type == TokenType.CELL_REF
    assert tokens[1].token_type == TokenType.OP_SPILL


def test_lexer_unclosed_string_error() -> None:
    """Test lexer throws LexerError on unclosed string."""
    with pytest.raises(LexerError, match="Unclosed string literal"):
        FormulaLexer('="hello world').tokenize()


def test_lexer_length_limit() -> None:
    """Test lexer rejects formulas exceeding MAX_FORMULA_LENGTH."""
    huge_formula = "=" + ("A1+" * 6000)
    assert len(huge_formula) > MAX_FORMULA_LENGTH
    with pytest.raises(LexerError, match="Formula length .* exceeds maximum allowed limit"):
        FormulaLexer(huge_formula).tokenize()
