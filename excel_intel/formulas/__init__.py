"""Excel Formula Analysis Subsystem — M05 Prompt 3: Formula Lexer, Parser & Strongly-Typed AST.

Provides deterministic lexical analysis, operator-precedence parsing,
strongly-typed immutable Pydantic v2 AST models, and recognized unsupported
syntax sentinels for Excel formulas.
"""

from __future__ import annotations

from excel_intel.formulas.lexer import (
    FormulaLexer,
    LexerError,
    Token,
    TokenType,
    col_letter_to_index,
    index_to_col_letter,
)
from excel_intel.formulas.models import (
    ASTNodeType,
    ArrayLiteralNode,
    BaseASTNode,
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
from excel_intel.formulas.parser import (
    MAX_AST_NODES,
    MAX_NESTING_DEPTH,
    FormulaParser,
    ParseException,
    parse_cell_reference_string,
    parse_structured_reference_string,
)

__all__ = [
    # AST Enums & Models
    "ASTNodeType",
    "FormulaParseStatus",
    "BaseASTNode",
    "LiteralNode",
    "CellReferenceNode",
    "RangeReferenceNode",
    "StructuredReferenceNode",
    "FunctionCallNode",
    "BinaryOpNode",
    "UnaryOpNode",
    "PostfixOpNode",
    "ArrayLiteralNode",
    "UnsupportedFormulaNode",
    "UnparsedFormulaNode",
    "FormulaParseResult",
    # Lexer
    "Token",
    "TokenType",
    "FormulaLexer",
    "LexerError",
    "col_letter_to_index",
    "index_to_col_letter",
    # Parser & Helpers
    "FormulaParser",
    "ParseException",
    "MAX_NESTING_DEPTH",
    "MAX_AST_NODES",
    "parse_cell_reference_string",
    "parse_structured_reference_string",
]
