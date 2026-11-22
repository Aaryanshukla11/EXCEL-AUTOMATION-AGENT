"""Deterministic Operator-Precedence Recursive-Descent Formula Parser (M05).

Parses tokenized Excel formulas into strongly-typed immutable Pydantic v2 AST nodes,
enforces strict rectangularity on array constants, preserves character spans,
detects recognized unsupported syntax, and enforces resource safety bounds.
"""

from __future__ import annotations

import re
from typing import Optional, Union

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

# Resource safety limits
MAX_NESTING_DEPTH = 64
MAX_AST_NODES = 4_096

# Lambda helper functions recognized as unsupported
LAMBDA_HELPERS = {
    "LAMBDA",
    "MAP",
    "REDUCE",
    "SCAN",
    "MAKEARRAY",
    "BYROW",
    "BYCOL",
}

# Standard built-in Excel functions that contain dots
STANDARD_DOT_FUNCTIONS = {
    "CEILING.MATH",
    "CEILING.PRECISE",
    "FLOOR.MATH",
    "FLOOR.PRECISE",
    "ISO.CEILING",
    "RANK.AVG",
    "RANK.EQ",
    "PERCENTRANK.INC",
    "PERCENTRANK.EXC",
    "PERCENTILE.INC",
    "PERCENTILE.EXC",
    "QUARTILE.INC",
    "QUARTILE.EXC",
    "NORM.DIST",
    "NORM.INV",
    "NORM.S.DIST",
    "NORM.S.INV",
    "T.DIST",
    "T.DIST.2T",
    "T.DIST.RT",
    "T.INV",
    "T.INV.2T",
    "T.TEST",
    "F.DIST",
    "F.DIST.RT",
    "F.INV",
    "F.INV.RT",
    "F.TEST",
    "CHISQ.DIST",
    "CHISQ.DIST.RT",
    "CHISQ.INV",
    "CHISQ.INV.RT",
    "CHISQ.TEST",
    "CONFIDENCE.NORM",
    "CONFIDENCE.T",
    "COVARIANCE.P",
    "COVARIANCE.S",
    "STDEV.P",
    "STDEV.S",
    "VAR.P",
    "VAR.S",
    "MODE.MULT",
    "MODE.SNGL",
    "EXPON.DIST",
    "GAMMA.DIST",
    "GAMMA.INV",
    "GAMMALN.PRECISE",
    "HYPGEOM.DIST",
    "LOGNORM.DIST",
    "LOGNORM.INV",
    "POISSON.DIST",
    "WEIBULL.DIST",
    "BINOM.DIST",
    "BINOM.DIST.RANGE",
    "BINOM.INV",
    "NEGBINOM.DIST",
    "BETA.DIST",
    "BETA.INV",
    "WORKDAY.INTL",
    "NETWORKDAYS.INTL",
    "ERF.PRECISE",
    "ERFC.PRECISE",
    "ECMA.CEILING",
    "Z.TEST",
}


class ParseException(Exception):
    """Internal exception raised during formula AST parsing."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(message)
        self.message = message
        self.position = position


def parse_cell_reference_string(
    raw_ref: str,
    span: tuple[int, int],
) -> CellReferenceNode:
    """Parse a cell reference string into CellReferenceNode with qualification details."""
    wb_name: Optional[str] = None
    sheet_name: Optional[str] = None
    sheet_end: Optional[str] = None

    remaining = raw_ref

    # Check for sheet exclamation mark
    if "!" in remaining:
        sheet_part, cell_part = remaining.rsplit("!", 1)
        # Parse sheet part (may contain workbook '[Book.xlsx]Sheet1' or single quotes)
        clean_sheet = sheet_part
        if clean_sheet.startswith("'") and clean_sheet.endswith("'"):
            clean_sheet = clean_sheet[1:-1].replace("''", "'")

        if clean_sheet.startswith("[") and "]" in clean_sheet:
            wb_end = clean_sheet.index("]")
            wb_name = clean_sheet[1:wb_end]
            clean_sheet = clean_sheet[wb_end + 1 :]

        if ":" in clean_sheet:
            s_start, s_end = clean_sheet.split(":", 1)
            sheet_name = s_start
            sheet_end = s_end
        else:
            sheet_name = clean_sheet
    else:
        cell_part = remaining

    # Parse cell coordinates: optional $, col letters, optional $, row digits
    m = re.match(r"^(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})$", cell_part)
    if not m:
        raise ValueError(f"Invalid cell coordinate format: '{cell_part}'")

    col_abs = bool(m.group(1))
    col_str = m.group(2).upper()
    row_abs = bool(m.group(3))
    row_idx = int(m.group(4))
    col_idx = col_letter_to_index(col_str)

    if not (1 <= col_idx <= 16384 and 1 <= row_idx <= 1048576):
        raise ValueError(f"Cell coordinates out of Excel bounds: '{cell_part}'")

    return CellReferenceNode(
        span=span,
        col=col_idx,
        row=row_idx,
        col_letter=col_str,
        col_absolute=col_abs,
        row_absolute=row_abs,
        sheet_name=sheet_name,
        workbook_name=wb_name,
        raw_reference=raw_ref,
    )


def parse_structured_reference_string(
    raw_ref: str,
    span: tuple[int, int],
) -> StructuredReferenceNode:
    """Parse structured reference string into StructuredReferenceNode."""
    table_name: Optional[str] = None
    remaining = raw_ref

    if not remaining.startswith("["):
        # Has table name
        bracket_idx = remaining.index("[")
        table_name = remaining[:bracket_idx].strip()
        remaining = remaining[bracket_idx:]

    # Strip outer [ and ]
    inner = remaining[1:-1].strip()

    is_this_row = False
    specifiers: list[str] = []
    column_name = ""
    column_end: Optional[str] = None

    if inner.startswith("@"):
        is_this_row = True
        inner = inner[1:].strip()

    # Parse components inside: could be [[#Headers],[Sales]] or [Sales] or [Sales]:[Profit]
    # Check for specifiers: #Headers, #Data, #Totals, #All, #This Row
    for spec in ("#Headers", "#Data", "#Totals", "#All", "#This Row"):
        if spec.lower() in inner.lower():
            specifiers.append(spec)
            if spec.lower() == "#this row":
                is_this_row = True

    # Extract column names
    # Simple unnested column e.g. Sales or [Sales]
    # Or range e.g. [Sales]:[Profit]
    if ":" in inner:
        parts = inner.split(":", 1)
        left_col = parts[0].strip().strip("[]").strip("@")
        right_col = parts[1].strip().strip("[]")
        # Filter out specifiers
        if left_col.startswith("#"):
            left_col = ""
        column_name = left_col
        column_end = right_col
    else:
        # Single column or specifiers only
        cols = re.findall(r"\[([^\]]+)\]", inner)
        if cols:
            non_spec_cols = [c for c in cols if not c.startswith("#") and c != "@"]
            if non_spec_cols:
                column_name = non_spec_cols[0].lstrip("@")
            else:
                column_name = ""
        else:
            # Unbracketed single name e.g. Sales or @Sales
            cleaned = inner.lstrip("@").strip()
            if not cleaned.startswith("#"):
                column_name = cleaned

    return StructuredReferenceNode(
        span=span,
        table_name=table_name,
        column_name=column_name,
        column_end=column_end,
        specifiers=specifiers,
        is_this_row=is_this_row,
        raw_reference=raw_ref,
    )


class FormulaParser:
    """Pure-Python deterministic formula parser implementing Excel operator precedence."""

    def __init__(self, raw_formula: str) -> None:
        self.raw_formula = raw_formula
        self.tokens: list[Token] = []
        self.pos = 0
        self.nesting_depth = 0
        self.node_count = 0
        self.unsupported_nodes: list[UnsupportedFormulaNode] = []

    def parse(self) -> FormulaParseResult:
        """Parse formula into a typed AST or structured error result."""
        # 1. Guard against empty or whitespace-only formula
        clean = self.raw_formula.strip()
        if not clean or clean == "=":
            return FormulaParseResult(
                raw_formula=self.raw_formula,
                status=FormulaParseStatus.PARSE_ERROR,
                ast=UnparsedFormulaNode(
                    raw_formula=self.raw_formula,
                    error_message="Empty formula expression",
                    error_position=0,
                    span=(0, len(self.raw_formula)),
                ),
                error_message="Empty formula expression",
                error_position=0,
            )

        # 2. Tokenize
        try:
            lexer = FormulaLexer(self.raw_formula)
            self.tokens = lexer.tokenize()
        except LexerError as exc:
            return FormulaParseResult(
                raw_formula=self.raw_formula,
                status=FormulaParseStatus.PARSE_ERROR,
                ast=UnparsedFormulaNode(
                    raw_formula=self.raw_formula,
                    error_message=exc.message,
                    error_position=exc.position,
                    span=(exc.position, min(exc.position + 1, len(self.raw_formula))),
                ),
                error_message=exc.message,
                error_position=exc.position,
            )

        # 3. Parse expression tree
        self.pos = 0
        self.nesting_depth = 0
        self.node_count = 0
        self.unsupported_nodes = []

        try:
            root_ast = self._parse_expression(precedence=0)

            # Check for unconsumed tokens (FR-3.3 Prevention of partial parsing conflation)
            current_tok = self._current_token()
            if current_tok.token_type != TokenType.EOF:
                raise ParseException(
                    f"Unexpected token '{current_tok.raw_text}' after expression at offset {current_tok.span[0]}",
                    current_tok.span[0],
                )

        except ParseException as exc:
            return FormulaParseResult(
                raw_formula=self.raw_formula,
                status=FormulaParseStatus.PARSE_ERROR,
                ast=UnparsedFormulaNode(
                    raw_formula=self.raw_formula,
                    error_message=exc.message,
                    error_position=exc.position,
                    span=(exc.position, min(exc.position + 1, len(self.raw_formula))),
                ),
                error_message=exc.message,
                error_position=exc.position,
            )

        # 4. Check if any unsupported nodes were encountered
        if self.unsupported_nodes:
            first_unsupported = self.unsupported_nodes[0]
            return FormulaParseResult(
                raw_formula=self.raw_formula,
                status=FormulaParseStatus.UNSUPPORTED_SYNTAX,
                ast=root_ast,
                error_message=first_unsupported.details or f"Unsupported syntax category: {first_unsupported.syntax_category}",
                error_position=first_unsupported.span[0],
                syntax_category=first_unsupported.syntax_category,
            )

        return FormulaParseResult(
            raw_formula=self.raw_formula,
            status=FormulaParseStatus.PARSED_COMPLETE,
            ast=root_ast,
        )

    # --------------------------------------------------------------------------
    # Recursive-Descent Expression Parsing with Operator Precedence
    # --------------------------------------------------------------------------

    # Precedence table
    # 1: Comparison: =, <>, <, >, <=, >=
    # 2: Concatenation: &
    # 3: Additive: +, -
    # 4: Multiplicative: *, /
    # 5: Power: ^ (left-associative in Excel)
    _BINARY_PRECEDENCE = {
        TokenType.OP_EQ: 1,
        TokenType.OP_NE: 1,
        TokenType.OP_LT: 1,
        TokenType.OP_GT: 1,
        TokenType.OP_LTE: 1,
        TokenType.OP_GTE: 1,
        TokenType.OP_CONCAT: 2,
        TokenType.OP_ADD: 3,
        TokenType.OP_SUB: 3,
        TokenType.OP_MUL: 4,
        TokenType.OP_DIV: 4,
        TokenType.OP_EXP: 5,
    }

    def _parse_expression(self, precedence: int = 0) -> BaseASTNode:
        """Parse binary expression climbing precedence levels."""
        self._check_depth()
        left = self._parse_unary()

        while True:
            tok = self._current_token()
            tok_prec = self._BINARY_PRECEDENCE.get(tok.token_type)

            if tok_prec is None or tok_prec < precedence:
                break

            # Consume operator
            op_tok = self._advance_token()
            # Left associativity: pass tok_prec + 1
            right = self._parse_expression(precedence=tok_prec + 1)
            span = (left.span[0], right.span[1])
            self._increment_node_count(op_tok.span[0])
            left = BinaryOpNode(
                span=span,
                operator=op_tok.raw_text,
                left=left,
                right=right,
            )

        return left

    def _parse_unary(self) -> BaseASTNode:
        """Parse prefix unary operators (+, -) or primary."""
        self._check_depth()
        tok = self._current_token()

        if tok.token_type in (TokenType.OP_ADD, TokenType.OP_SUB):
            op_tok = self._advance_token()
            operand = self._parse_unary()
            span = (op_tok.span[0], operand.span[1])
            self._increment_node_count(op_tok.span[0])
            return UnaryOpNode(
                span=span,
                operator=op_tok.raw_text,
                operand=operand,
            )

        return self._parse_postfix()

    def _parse_postfix(self) -> BaseASTNode:
        """Parse primary followed by postfix operators (e.g. %, dynamic spill #)."""
        node = self._parse_primary()

        while True:
            tok = self._current_token()
            if tok.token_type == TokenType.OP_PERCENT:
                pct_tok = self._advance_token()
                span = (node.span[0], pct_tok.span[1])
                self._increment_node_count(pct_tok.span[0])
                node = PostfixOpNode(
                    span=span,
                    operator="%",
                    operand=node,
                )
            elif tok.token_type == TokenType.OP_SPILL:
                # Dynamic array spill operator '#'
                spill_tok = self._advance_token()
                span = (node.span[0], spill_tok.span[1])
                unsupported = UnsupportedFormulaNode(
                    span=span,
                    raw_formula=self.raw_formula[span[0] : span[1]],
                    syntax_category="DYNAMIC_ARRAY_SPILL",
                    details=f"Dynamic array spill operator '#' at offset {spill_tok.span[0]} is unsupported",
                )
                self.unsupported_nodes.append(unsupported)
                node = unsupported
            else:
                break

        return node

    def _parse_primary(self) -> BaseASTNode:
        """Parse primary atom: literal, cell ref, range, function, parenthesized expr, array literal."""
        self._check_depth()
        tok = self._current_token()

        # 1. Parenthesized expression
        if tok.token_type == TokenType.LPAREN:
            self._advance_token()  # consume '('
            self.nesting_depth += 1
            expr = self._parse_expression(precedence=0)
            close_tok = self._current_token()
            if close_tok.token_type != TokenType.RPAREN:
                raise ParseException(f"Missing closing parenthesis ')' at offset {close_tok.span[0]}", close_tok.span[0])
            self._advance_token()  # consume ')'
            self.nesting_depth -= 1
            return expr

        # 2. Number literal
        if tok.token_type == TokenType.NUMBER:
            tok = self._advance_token()
            self._increment_node_count(tok.span[0])
            # Check if this number is followed by ':' as in a whole row range 1:1 or 1:10
            if self._current_token().token_type == TokenType.OP_COLON:
                colon_tok = self._advance_token()
                next_tok = self._current_token()
                if next_tok.token_type == TokenType.NUMBER:
                    end_num_tok = self._advance_token()
                    start_row = int(tok.value)
                    end_row = int(end_num_tok.value)
                    span = (tok.span[0], end_num_tok.span[1])
                    start_cell = CellReferenceNode(
                        span=(tok.span[0], tok.span[1]),
                        col=1,
                        row=start_row,
                        col_letter="A",
                        raw_reference=tok.raw_text,
                    )
                    end_cell = CellReferenceNode(
                        span=(end_num_tok.span[0], end_num_tok.span[1]),
                        col=16384,
                        row=end_row,
                        col_letter="XFD",
                        raw_reference=end_num_tok.raw_text,
                    )
                    return RangeReferenceNode(
                        span=span,
                        start_cell=start_cell,
                        end_cell=end_cell,
                        is_full_row=True,
                        raw_reference=self.raw_formula[span[0] : span[1]],
                    )
            return LiteralNode(
                span=tok.span,
                value=tok.value,
                literal_kind="NUMBER",
                raw_text=tok.raw_text,
            )

        # 3. String literal
        if tok.token_type == TokenType.STRING:
            tok = self._advance_token()
            self._increment_node_count(tok.span[0])
            return LiteralNode(
                span=tok.span,
                value=tok.value,
                literal_kind="STRING",
                raw_text=tok.raw_text,
            )

        # 4. Boolean literal
        if tok.token_type == TokenType.BOOLEAN:
            tok = self._advance_token()
            self._increment_node_count(tok.span[0])
            return LiteralNode(
                span=tok.span,
                value=tok.value,
                literal_kind="BOOLEAN",
                raw_text=tok.raw_text,
            )

        # 5. Error literal
        if tok.token_type == TokenType.ERROR:
            tok = self._advance_token()
            self._increment_node_count(tok.span[0])
            return LiteralNode(
                span=tok.span,
                value=tok.value,
                literal_kind="ERROR",
                raw_text=tok.raw_text,
            )

        # 6. Structured reference
        if tok.token_type == TokenType.STRUCTURED_REF:
            tok = self._advance_token()
            self._increment_node_count(tok.span[0])
            return parse_structured_reference_string(tok.raw_text, tok.span)

        # 7. Function call
        if tok.token_type == TokenType.FUNCTION:
            return self._parse_function_call()

        # 8. Cell Reference or Whole Column Range (IDENT or CELL_REF)
        if tok.token_type in (TokenType.CELL_REF, TokenType.IDENT):
            return self._parse_ref_or_range()

        # 9. Array literal constant {...}
        if tok.token_type == TokenType.LBRACE:
            return self._parse_array_literal()

        raise ParseException(f"Unexpected token '{tok.raw_text}' at offset {tok.span[0]}", tok.span[0])

    def _parse_ref_or_range(self) -> BaseASTNode:
        """Parse cell reference, 2D range, full column/row range, or 3D range."""
        tok = self._advance_token()
        self._increment_node_count(tok.span[0])

        # Check for complex external URI network chains
        if any(proto in tok.raw_text.lower() for proto in ("http://", "https://", "ftp://", "file://", "mailto:")):
            unsupported = UnsupportedFormulaNode(
                span=tok.span,
                raw_formula=tok.raw_text,
                syntax_category="EXTERNAL_URI_CHAIN",
                details=f"Complex external URI network chain in reference '{tok.raw_text}' is recognized but unsupported",
            )
            self.unsupported_nodes.append(unsupported)
            return unsupported

        # Check if it's a cell reference
        is_cell_ref = False
        cell_node: Optional[CellReferenceNode] = None

        if tok.token_type == TokenType.CELL_REF:
            try:
                cell_node = parse_cell_reference_string(tok.raw_text, tok.span)
                is_cell_ref = True
            except ValueError:
                pass

        # Check if followed by colon ':' for range reference (e.g. A1:B10 or A:A)
        if self._current_token().token_type == TokenType.OP_COLON:
            colon_tok = self._advance_token()  # consume ':'
            next_tok = self._current_token()

            if is_cell_ref and cell_node is not None:
                # End of range should be another cell ref
                if next_tok.token_type in (TokenType.CELL_REF, TokenType.IDENT):
                    end_tok = self._advance_token()
                    try:
                        end_cell = parse_cell_reference_string(end_tok.raw_text, end_tok.span)
                    except ValueError as err:
                        raise ParseException(f"Invalid range end '{end_tok.raw_text}': {err}", end_tok.span[0])

                    # Inherit sheet if right cell doesn't have sheet
                    sheet_name = cell_node.sheet_name
                    sheet_end = None
                    # Check 3D range
                    is_3d = False
                    if cell_node.raw_reference and "!" in cell_node.raw_reference:
                        sheet_part = cell_node.raw_reference.split("!")[0]
                        if ":" in sheet_part:
                            is_3d = True
                            clean_sheet = sheet_part.strip("'")
                            if clean_sheet.startswith("[") and "]" in clean_sheet:
                                clean_sheet = clean_sheet[clean_sheet.index("]") + 1 :]
                            s_parts = clean_sheet.split(":")
                            sheet_name = s_parts[0]
                            sheet_end = s_parts[1]

                    span = (cell_node.span[0], end_tok.span[1])
                    return RangeReferenceNode(
                        span=span,
                        start_cell=cell_node,
                        end_cell=end_cell,
                        sheet_name=sheet_name,
                        sheet_end=sheet_end,
                        workbook_name=cell_node.workbook_name,
                        is_full_col=False,
                        is_full_row=False,
                        is_3d=is_3d,
                        raw_reference=self.raw_formula[span[0] : span[1]],
                    )
                else:
                    raise ParseException(f"Expected range end reference after ':' at offset {colon_tok.span[0]}", colon_tok.span[0])

            # Whole column reference e.g. A:A or $A:$B or Sheet1!A:B
            if tok.token_type == TokenType.IDENT:
                sheet_prefix = None
                wb_prefix = None
                raw_ident = tok.raw_text

                if "!" in raw_ident:
                    s_part, col_part = raw_ident.split("!", 1)
                    sheet_prefix = s_part.strip("'")
                    raw_ident = col_part

                clean_col1 = raw_ident.lstrip("$").upper()
                if next_tok.token_type == TokenType.IDENT:
                    end_tok = self._advance_token()
                    clean_col2 = end_tok.raw_text.lstrip("$").upper()
                    if clean_col1.isalpha() and clean_col2.isalpha():
                        col1_idx = col_letter_to_index(clean_col1)
                        col2_idx = col_letter_to_index(clean_col2)
                        if 1 <= col1_idx <= 16384 and 1 <= col2_idx <= 16384:
                            span = (tok.span[0], end_tok.span[1])
                            start_cell = CellReferenceNode(
                                span=(tok.span[0], tok.span[1]),
                                col=col1_idx,
                                row=1,
                                col_letter=clean_col1,
                                col_absolute=tok.raw_text.startswith("$"),
                                sheet_name=sheet_prefix,
                                workbook_name=wb_prefix,
                                raw_reference=tok.raw_text,
                            )
                            end_cell = CellReferenceNode(
                                span=(end_tok.span[0], end_tok.span[1]),
                                col=col2_idx,
                                row=1048576,
                                col_letter=clean_col2,
                                col_absolute=end_tok.raw_text.startswith("$"),
                                sheet_name=sheet_prefix,
                                workbook_name=wb_prefix,
                                raw_reference=end_tok.raw_text,
                            )
                            return RangeReferenceNode(
                                span=span,
                                start_cell=start_cell,
                                end_cell=end_cell,
                                sheet_name=sheet_prefix,
                                workbook_name=wb_prefix,
                                is_full_col=True,
                                raw_reference=self.raw_formula[span[0] : span[1]],
                            )

            raise ParseException(f"Invalid reference operator ':' at offset {colon_tok.span[0]}", colon_tok.span[0])

        if cell_node is not None:
            return cell_node

        # Standalone identifier (e.g. named range or unresolved variable)
        # Note: if it is an identifier not recognized, represented as CellReference or parsed
        # For now, treat unbracketed identifier as cell ref if valid, or parse error
        raise ParseException(f"Unrecognized identifier or reference '{tok.raw_text}' at offset {tok.span[0]}", tok.span[0])

    def _parse_function_call(self) -> BaseASTNode:
        """Parse function call node with ordered arguments."""
        func_tok = self._advance_token()  # consume FUNCTION token
        self._increment_node_count(func_tok.span[0])
        func_name = str(func_tok.value).upper()

        # Next token must be '('
        lparen_tok = self._current_token()
        if lparen_tok.token_type != TokenType.LPAREN:
            raise ParseException(f"Expected '(' after function name '{func_name}' at offset {lparen_tok.span[0]}", lparen_tok.span[0])
        self._advance_token()  # consume '('
        self.nesting_depth += 1

        args: list[BaseASTNode] = []
        if self._current_token().token_type != TokenType.RPAREN:
            while True:
                # Parse argument expression
                arg_expr = self._parse_expression(precedence=0)
                args.append(arg_expr)

                next_tok = self._current_token()
                if next_tok.token_type == TokenType.OP_COMMA:
                    self._advance_token()  # consume ','
                    continue
                elif next_tok.token_type == TokenType.RPAREN:
                    break
                else:
                    raise ParseException(
                        f"Expected ',' or ')' in argument list of function '{func_name}' at offset {next_tok.span[0]}",
                        next_tok.span[0],
                    )

        rparen_tok = self._advance_token()  # consume ')'
        self.nesting_depth -= 1
        span = (func_tok.span[0], rparen_tok.span[1])

        # Check recognized unsupported syntax categories:
        # Category B: Lambda helper functions
        if func_name in LAMBDA_HELPERS:
            unsupported = UnsupportedFormulaNode(
                span=span,
                raw_formula=self.raw_formula[span[0] : span[1]],
                syntax_category="LAMBDA_HELPER",
                details=f"Lambda helper function '{func_name}' is recognized but unsupported",
            )
            self.unsupported_nodes.append(unsupported)
            return unsupported

        # Category B: Third-party UDF (contains '.' not in standard Excel function catalog)
        if "." in func_name and func_name not in STANDARD_DOT_FUNCTIONS:
            unsupported = UnsupportedFormulaNode(
                span=span,
                raw_formula=self.raw_formula[span[0] : span[1]],
                syntax_category="THIRD_PARTY_UDF",
                details=f"Third-party user defined function '{func_name}' is recognized but unsupported",
            )
            self.unsupported_nodes.append(unsupported)
            return unsupported

        return FunctionCallNode(
            span=span,
            function_name=func_name,
            arguments=args,
        )

    def _parse_array_literal(self) -> BaseASTNode:
        """Parse strict rectangular matrix array constant {...}."""
        lbrace_tok = self._advance_token()  # consume '{'
        self._increment_node_count(lbrace_tok.span[0])
        rows: list[list[BaseASTNode]] = []
        current_row: list[BaseASTNode] = []

        while True:
            tok = self._current_token()
            if tok.token_type == TokenType.RBRACE:
                break
            if tok.token_type == TokenType.EOF:
                raise ParseException("Unclosed array constant '{'", lbrace_tok.span[0])

            # Elements in array constants must be literal constants or signed numbers!
            # Excel does NOT allow cell references or formulas inside {}.
            elem = self._parse_array_element()
            current_row.append(elem)

            sep = self._current_token()
            if sep.token_type == TokenType.OP_COMMA:
                self._advance_token()  # consume ','
                continue
            elif sep.token_type == TokenType.OP_SEMICOLON:
                self._advance_token()  # consume ';'
                rows.append(current_row)
                current_row = []
                continue
            elif sep.token_type == TokenType.RBRACE:
                break
            else:
                raise ParseException(f"Expected ',' or ';' in array constant at offset {sep.span[0]}", sep.span[0])

        rbrace_tok = self._advance_token()  # consume '}'

        if current_row:
            rows.append(current_row)

        if not rows:
            raise ParseException("Empty array constant '{}' is not valid in Excel", lbrace_tok.span[0])

        row_count = len(rows)
        col_count = len(rows[0])
        # Validate rectangular matrix invariant
        for idx, row in enumerate(rows):
            if len(row) != col_count:
                raise ParseException(
                    f"Array literal is not rectangular: row {idx} has {len(row)} elements, expected {col_count}",
                    lbrace_tok.span[0],
                )

        span = (lbrace_tok.span[0], rbrace_tok.span[1])
        return ArrayLiteralNode(
            span=span,
            rows=rows,
            row_count=row_count,
            col_count=col_count,
            is_rectangular=True,
        )

    def _parse_array_element(self) -> BaseASTNode:
        """Parse an allowed constant element inside an array literal."""
        tok = self._current_token()

        # Handle signed number e.g. -1 or +2.5
        if tok.token_type in (TokenType.OP_ADD, TokenType.OP_SUB):
            sign_tok = self._advance_token()
            num_tok = self._current_token()
            if num_tok.token_type != TokenType.NUMBER:
                raise ParseException("Only constant literals or signed numbers allowed in array constants", sign_tok.span[0])
            self._advance_token()
            val = -num_tok.value if sign_tok.token_type == TokenType.OP_SUB else num_tok.value
            span = (sign_tok.span[0], num_tok.span[1])
            return LiteralNode(
                span=span,
                value=val,
                literal_kind="NUMBER",
                raw_text=self.raw_formula[span[0] : span[1]],
            )

        if tok.token_type in (TokenType.NUMBER, TokenType.STRING, TokenType.BOOLEAN, TokenType.ERROR):
            tok = self._advance_token()
            kind = tok.token_type.name
            return LiteralNode(
                span=tok.span,
                value=tok.value,
                literal_kind=kind,
                raw_text=tok.raw_text,
            )

        raise ParseException(
            f"Array constants cannot contain expressions, cell references, or formulas (found '{tok.raw_text}') at offset {tok.span[0]}",
            tok.span[0],
        )

    # --------------------------------------------------------------------------
    # Token Navigation & Safety Tripwires
    # --------------------------------------------------------------------------

    def _current_token(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def _advance_token(self) -> Token:
        tok = self._current_token()
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _check_depth(self) -> None:
        if self.nesting_depth > MAX_NESTING_DEPTH:
            pos = self._current_token().span[0]
            raise ParseException(
                f"Formula nesting depth exceeds maximum limit of {MAX_NESTING_DEPTH}",
                pos,
            )

    def _increment_node_count(self, position: int) -> None:
        self.node_count += 1
        if self.node_count > MAX_AST_NODES:
            raise ParseException(
                f"Formula AST node count exceeds maximum limit of {MAX_AST_NODES}",
                position,
            )
