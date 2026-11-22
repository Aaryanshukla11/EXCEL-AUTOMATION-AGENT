"""Immutable Abstract Syntax Tree (AST) Data Contracts for Excel Formulas (M05).

Defines frozen Pydantic v2 models representing all supported syntactic constructs
in Excel formulas, explicit parse statuses, source-span provenance, and typed
error/unsupported diagnostic nodes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FormulaParseStatus(str, Enum):
    """Status of formula parsing result."""

    PARSED_COMPLETE = "PARSED_COMPLETE"
    UNSUPPORTED_SYNTAX = "UNSUPPORTED_SYNTAX"
    PARSE_ERROR = "PARSE_ERROR"


class ASTNodeType(str, Enum):
    """Categorization of formula AST nodes."""

    LITERAL = "LITERAL"
    CELL_REFERENCE = "CELL_REFERENCE"
    RANGE_REFERENCE = "RANGE_REFERENCE"
    STRUCTURED_REFERENCE = "STRUCTURED_REFERENCE"
    FUNCTION_CALL = "FUNCTION_CALL"
    UNARY_OP = "UNARY_OP"
    BINARY_OP = "BINARY_OP"
    POSTFIX_OP = "POSTFIX_OP"
    ARRAY_LITERAL = "ARRAY_LITERAL"
    UNSUPPORTED = "UNSUPPORTED"
    UNPARSED = "UNPARSED"


class BaseASTNode(BaseModel):
    """Base immutable AST node with source character span provenance."""

    node_type: ASTNodeType
    span: tuple[int, int] = Field(
        description="Character start and end offsets (0-indexed, half-open [start, end)) in raw formula"
    )

    model_config = ConfigDict(frozen=True)


class LiteralNode(BaseASTNode):
    """Literal constant node (numeric, string, boolean, or Excel error)."""

    node_type: ASTNodeType = ASTNodeType.LITERAL
    value: Any
    literal_kind: str = Field(
        description="Category: 'NUMBER', 'STRING', 'BOOLEAN', or 'ERROR'"
    )
    raw_text: str = Field(description="Exact verbatim literal text as parsed")

    model_config = ConfigDict(frozen=True)


class CellReferenceNode(BaseASTNode):
    """Single cell reference node with coordinate and qualification details."""

    node_type: ASTNodeType = ASTNodeType.CELL_REFERENCE
    col: int = Field(ge=1, le=16384, description="1-indexed column number")
    row: int = Field(ge=1, le=1048576, description="1-indexed row number")
    col_letter: str = Field(description="Column letter string, e.g. 'A', 'Z', 'AA'")
    col_absolute: bool = Field(default=False, description="True if column is anchored with $")
    row_absolute: bool = Field(default=False, description="True if row is anchored with $")
    sheet_name: Optional[str] = Field(default=None, description="Sheet qualification name if present")
    workbook_name: Optional[str] = Field(default=None, description="External workbook reference if present")
    raw_reference: str = Field(description="Verbatim source reference text")

    model_config = ConfigDict(frozen=True)

    def to_a1(self) -> str:
        """Format as canonical A1-style reference string."""
        col_part = f"${self.col_letter}" if self.col_absolute else self.col_letter
        row_part = f"${self.row}" if self.row_absolute else str(self.row)
        sheet_part = f"'{self.sheet_name}'!" if self.sheet_name else ""
        wb_part = f"[{self.workbook_name}]" if self.workbook_name else ""
        return f"{wb_part}{sheet_part}{col_part}{row_part}"


class RangeReferenceNode(BaseASTNode):
    """Rectangular 2D or 3D range reference node bounded by start and end cells."""

    node_type: ASTNodeType = ASTNodeType.RANGE_REFERENCE
    start_cell: CellReferenceNode
    end_cell: CellReferenceNode
    sheet_name: Optional[str] = Field(default=None, description="Starting or single sheet name")
    sheet_end: Optional[str] = Field(default=None, description="Ending sheet name for 3D ranges (e.g. Sheet1:Sheet3)")
    workbook_name: Optional[str] = Field(default=None, description="External workbook reference if present")
    is_full_col: bool = Field(default=False, description="True for full column ranges (e.g. A:A)")
    is_full_row: bool = Field(default=False, description="True for full row ranges (e.g. 1:1)")
    is_3d: bool = Field(default=False, description="True if range spans multiple sheets")
    raw_reference: str = Field(description="Verbatim source range text")

    model_config = ConfigDict(frozen=True)


class StructuredReferenceNode(BaseASTNode):
    """Excel ListObject table structured reference node."""

    node_type: ASTNodeType = ASTNodeType.STRUCTURED_REFERENCE
    table_name: Optional[str] = Field(default=None, description="Table name if explicitly qualified")
    column_name: str = Field(description="Target column or starting column name")
    column_end: Optional[str] = Field(default=None, description="Ending column name for column span ranges")
    specifiers: list[str] = Field(
        default_factory=list,
        description="Structured specifiers, e.g. ['#Headers'], ['#Data'], ['#Totals'], ['#All']",
    )
    is_this_row: bool = Field(default=False, description="True if '@' this-row operator was specified")
    raw_reference: str = Field(description="Verbatim source reference text")

    model_config = ConfigDict(frozen=True)


class FunctionCallNode(BaseASTNode):
    """Formula function call node with ordered arguments."""

    node_type: ASTNodeType = ASTNodeType.FUNCTION_CALL
    function_name: str = Field(description="Normalized uppercase function name (e.g. 'SUM', 'VLOOKUP')")
    arguments: list[BaseASTNode] = Field(default_factory=list, description="Ordered list of argument AST nodes")

    model_config = ConfigDict(frozen=True)


class BinaryOpNode(BaseASTNode):
    """Binary infix operator node."""

    node_type: ASTNodeType = ASTNodeType.BINARY_OP
    operator: str = Field(description="Infix operator: '+', '-', '*', '/', '^', '&', '=', '<>', '<', '>', '<=', '>=', ':', ',', ' '")
    left: BaseASTNode
    right: BaseASTNode

    model_config = ConfigDict(frozen=True)


class UnaryOpNode(BaseASTNode):
    """Unary prefix operator node."""

    node_type: ASTNodeType = ASTNodeType.UNARY_OP
    operator: str = Field(description="Prefix operator: '+' or '-'")
    operand: BaseASTNode

    model_config = ConfigDict(frozen=True)


class PostfixOpNode(BaseASTNode):
    """Postfix operator node."""

    node_type: ASTNodeType = ASTNodeType.POSTFIX_OP
    operator: str = Field(default="%", description="Postfix operator: '%'")
    operand: BaseASTNode

    model_config = ConfigDict(frozen=True)


class ArrayLiteralNode(BaseASTNode):
    """Strict rectangular matrix array constant node."""

    node_type: ASTNodeType = ASTNodeType.ARRAY_LITERAL
    rows: list[list[BaseASTNode]] = Field(default_factory=list, description="2D matrix of row elements")
    row_count: int = Field(ge=1)
    col_count: int = Field(ge=1)
    is_rectangular: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def validate_rectangular(self) -> ArrayLiteralNode:
        if not self.rows:
            raise ValueError("Array literal cannot have zero rows")
        expected_cols = len(self.rows[0])
        if expected_cols == 0:
            raise ValueError("Array row cannot be empty")
        for idx, row in enumerate(self.rows):
            if len(row) != expected_cols:
                raise ValueError(
                    f"Array literal is not rectangular: row {idx} has {len(row)} elements, expected {expected_cols}"
                )
        return self


class UnsupportedFormulaNode(BaseASTNode):
    """Recognized but unsupported syntax node (never fabricates placeholder semantics)."""

    node_type: ASTNodeType = ASTNodeType.UNSUPPORTED
    raw_formula: str = Field(description="Verbatim text of the unsupported construct")
    syntax_category: str = Field(
        description="Classification: 'DYNAMIC_ARRAY_SPILL', 'LAMBDA_HELPER', 'EXTERNAL_URI_CHAIN', 'THIRD_PARTY_UDF', 'UNSUPPORTED_OPERATOR'"
    )
    details: Optional[str] = Field(default=None, description="Diagnostic details explaining why construct is unsupported")

    model_config = ConfigDict(frozen=True)


class UnparsedFormulaNode(BaseASTNode):
    """Malformed formula syntax node capturing error offset and diagnostic message."""

    node_type: ASTNodeType = ASTNodeType.UNPARSED
    raw_formula: str = Field(description="Raw formula text that failed parsing")
    error_message: str = Field(description="Diagnostic syntax error message")
    error_position: int = Field(ge=0, description="0-indexed character offset where error occurred")

    model_config = ConfigDict(frozen=True)


class FormulaParseResult(BaseModel):
    """Complete structured result of Excel formula parsing."""

    raw_formula: str = Field(description="Original verbatim formula text")
    status: FormulaParseStatus = Field(description="Discrete parse outcome status")
    ast: Optional[BaseASTNode] = Field(default=None, description="Root AST node if parse produced a tree")
    error_message: Optional[str] = Field(default=None, description="Diagnostic error message if status is not PARSED_COMPLETE")
    error_position: Optional[int] = Field(default=None, ge=0, description="Character offset associated with error or unsupported syntax")
    syntax_category: Optional[str] = Field(default=None, description="Classification category for unsupported syntax")

    model_config = ConfigDict(frozen=True)

    @property
    def is_success(self) -> bool:
        """True if formula parsed completely without unsupported syntax or parse errors."""
        return self.status == FormulaParseStatus.PARSED_COMPLETE and self.ast is not None
