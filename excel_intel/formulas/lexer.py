"""Deterministic Lexical Analyzer and Tokenizer for Excel Formulas (M05).

Tokenizes Excel formulas into strongly typed tokens with character span tracking,
supporting standard Excel literals, cell and range references, structured table
references, operators, and recognized unsupported syntax sentinels.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Optional

# Maximum limits to prevent denial-of-service / resource exhaustion
MAX_FORMULA_LENGTH = 16_384
MAX_TOKENS = 4_096


class TokenType(str, Enum):
    """Excel formula token types."""

    # Literals
    NUMBER = "NUMBER"
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    ERROR = "ERROR"

    # References & Identifiers
    CELL_REF = "CELL_REF"
    STRUCTURED_REF = "STRUCTURED_REF"
    IDENT = "IDENT"
    FUNCTION = "FUNCTION"

    # Arithmetic & String Operators
    OP_ADD = "OP_ADD"              # +
    OP_SUB = "OP_SUB"              # -
    OP_MUL = "OP_MUL"              # *
    OP_DIV = "OP_DIV"              # /
    OP_EXP = "OP_EXP"              # ^
    OP_CONCAT = "OP_CONCAT"        # &

    # Comparison Operators
    OP_EQ = "OP_EQ"                # =
    OP_NE = "OP_NE"                # <>
    OP_LT = "OP_LT"                # <
    OP_GT = "OP_GT"                # >
    OP_LTE = "OP_LTE"              # <=
    OP_GTE = "OP_GTE"              # >=

    # Postfix & Range Operators
    OP_PERCENT = "OP_PERCENT"      # %
    OP_COLON = "OP_COLON"          # :
    OP_COMMA = "OP_COMMA"          # ,
    OP_SEMICOLON = "OP_SEMICOLON"  # ;
    OP_SPILL = "OP_SPILL"          # # (spill operator)

    # Delimiters
    LPAREN = "LPAREN"              # (
    RPAREN = "RPAREN"              # )
    LBRACE = "LBRACE"              # {
    RBRACE = "RBRACE"              # }

    # End of input
    EOF = "EOF"


class Token:
    """Represents a single lexical token with character span provenance."""

    __slots__ = ("token_type", "value", "span", "raw_text")

    def __init__(
        self,
        token_type: TokenType,
        value: object,
        span: tuple[int, int],
        raw_text: str,
    ) -> None:
        self.token_type = token_type
        self.value = value
        self.span = span
        self.raw_text = raw_text

    def __repr__(self) -> str:
        return f"Token({self.token_type.name}, {self.value!r}, span={self.span})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Token):
            return False
        return (
            self.token_type == other.token_type
            and self.value == other.value
            and self.span == other.span
            and self.raw_text == other.raw_text
        )


class LexerError(Exception):
    """Exception raised for lexical errors during tokenization."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(message)
        self.message = message
        self.position = position


# Excel error literals
EXCEL_ERRORS = {
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
    "#SPILL!",
    "#CALC!",
    "#FIELD!",
    "#UNKNOWN!",
}

# Regex for cell references with optional sheet/workbook qualification
# Example: Sheet1!$A$1, 'Sales Q1'!B2, [Budget.xlsx]Sheet1!$C$10, 'Jan:Dec'!$A$1
CELL_REF_REGEX = re.compile(
    r"^(?:(?:(?:'((?:[^']|'')*)'|\[([^\]]+)\](?:'((?:[^']|'')*)'|([A-Za-z0-9_]+))|([A-Za-z0-9_]+(?::[A-Za-z0-9_]+)?))!)?)"
    r"(\$?)([A-Za-z]{1,3})(\$?)(\d{1,7})\b"
)

# Regex matching sheet qualification followed by whole column
# e.g. 'Rate Table'!A or Sheet1!A or [Budget.xlsx]Sheet1!A
SHEET_COL_REF_REGEX = re.compile(
    r"^(?:(?:'((?:[^']|'')*)'|\[([^\]]+)\](?:'((?:[^']|'')*)'|([A-Za-z0-9_]+))|([A-Za-z0-9_]+(?::[A-Za-z0-9_]+)?))!)"
    r"(\$?)([A-Za-z]{1,3})\b"
)

# Regex matching external workbook prefix e.g. [Budget.xlsx]Sheet1!
EXT_WB_PREFIX_REGEX = re.compile(r"^\[([^\]]+)\](?:'((?:[^']|'')*)'|([A-Za-z0-9_]+))!")

# Regex matching single-quoted sheet prefix e.g. 'Sheet 1'! or '[Budget.xlsx]Sheet 1'!
QUOTED_SHEET_PREFIX_REGEX = re.compile(r"^'((?:[^']|'')*)'!")


def col_letter_to_index(col_str: str) -> int:
    """Convert column letter string (e.g. 'A', 'Z', 'AA', 'XFD') to 1-indexed column number."""
    result = 0
    for char in col_str.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


def index_to_col_letter(col_idx: int) -> str:
    """Convert 1-indexed column number to column letter string."""
    result = []
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        result.append(chr(ord("A") + rem))
    return "".join(reversed(result))


class FormulaLexer:
    """Deterministic Excel formula tokenizer."""

    def __init__(self, formula: str) -> None:
        if len(formula) > MAX_FORMULA_LENGTH:
            raise LexerError(
                f"Formula length ({len(formula)}) exceeds maximum allowed limit ({MAX_FORMULA_LENGTH})",
                0,
            )
        self.formula = formula
        self.length = len(formula)
        self.pos = 0

    def tokenize(self) -> list[Token]:
        """Tokenize the entire formula string."""
        tokens: list[Token] = []

        # Optional leading '='
        if self.pos < self.length and self.formula[self.pos] == "=":
            self.pos += 1

        prev_token: Optional[Token] = None

        while self.pos < self.length:
            if len(tokens) >= MAX_TOKENS:
                raise LexerError(
                    f"Token count exceeds maximum limit ({MAX_TOKENS})",
                    self.pos,
                )

            # Skip whitespace
            if self.formula[self.pos].isspace():
                self.pos += 1
                continue

            start_pos = self.pos
            char = self.formula[self.pos]

            # 1. String literal
            if char == '"':
                tok = self._lex_string()
                tokens.append(tok)
                prev_token = tok
                continue

            # 2. Number literal (digits or . followed by digits)
            if char.isdigit() or (char == "." and self.pos + 1 < self.length and self.formula[self.pos + 1].isdigit()):
                tok = self._lex_number()
                tokens.append(tok)
                prev_token = tok
                continue

            # 3. Dynamic array spill operator '#' following a cell or structured ref
            if char == "#":
                err_tok = self._try_lex_error()
                if err_tok is not None:
                    tokens.append(err_tok)
                    prev_token = err_tok
                    continue

                if prev_token is not None and prev_token.token_type in (
                    TokenType.CELL_REF,
                    TokenType.STRUCTURED_REF,
                    TokenType.RPAREN,
                ):
                    tok = Token(TokenType.OP_SPILL, "#", (start_pos, start_pos + 1), "#")
                    self.pos += 1
                    tokens.append(tok)
                    prev_token = tok
                    continue

                raise LexerError(f"Unexpected '#' at position {start_pos}", start_pos)

            # 4. Bracket '[': Could be External Workbook prefix [Book.xlsx]Sheet!A1 OR Structured Reference [Sales]
            if char == "[":
                # Check if it is an external workbook prefix
                if EXT_WB_PREFIX_REGEX.match(self.formula[self.pos :]):
                    tok = self._lex_cell_or_col_ref()
                    tokens.append(tok)
                    prev_token = tok
                    continue
                else:
                    tok = self._lex_structured_reference(table_name=None)
                    tokens.append(tok)
                    prev_token = tok
                    continue

            # 5. Cell reference or column reference starting with single quote `'Sheet'!A1`
            if char == "'":
                tok = self._try_lex_quoted_ref()
                if tok is not None:
                    tokens.append(tok)
                    prev_token = tok
                    continue
                else:
                    raise LexerError(f"Malformed or unclosed single-quoted reference at position {start_pos}", start_pos)

            # 6. Two-character operators: <=, >=, <>
            if self.pos + 1 < self.length:
                two_char = self.formula[self.pos : self.pos + 2]
                if two_char == "<=":
                    tok = Token(TokenType.OP_LTE, "<=", (start_pos, start_pos + 2), "<=")
                    self.pos += 2
                    tokens.append(tok)
                    prev_token = tok
                    continue
                elif two_char == ">=":
                    tok = Token(TokenType.OP_GTE, ">=", (start_pos, start_pos + 2), "<=")
                    self.pos += 2
                    tokens.append(tok)
                    prev_token = tok
                    continue
                elif two_char == "<>":
                    tok = Token(TokenType.OP_NE, "<>", (start_pos, start_pos + 2), "<>")
                    self.pos += 2
                    tokens.append(tok)
                    prev_token = tok
                    continue

            # 7. Single-character operators & delimiters
            if char == "+":
                tok = Token(TokenType.OP_ADD, "+", (start_pos, start_pos + 1), "+")
                self.pos += 1
            elif char == "-":
                tok = Token(TokenType.OP_SUB, "-", (start_pos, start_pos + 1), "-")
                self.pos += 1
            elif char == "*":
                tok = Token(TokenType.OP_MUL, "*", (start_pos, start_pos + 1), "*")
                self.pos += 1
            elif char == "/":
                tok = Token(TokenType.OP_DIV, "/", (start_pos, start_pos + 1), "/")
                self.pos += 1
            elif char == "^":
                tok = Token(TokenType.OP_EXP, "^", (start_pos, start_pos + 1), "^")
                self.pos += 1
            elif char == "&":
                tok = Token(TokenType.OP_CONCAT, "&", (start_pos, start_pos + 1), "&")
                self.pos += 1
            elif char == "=":
                tok = Token(TokenType.OP_EQ, "=", (start_pos, start_pos + 1), "=")
                self.pos += 1
            elif char == "<":
                tok = Token(TokenType.OP_LT, "<", (start_pos, start_pos + 1), "<")
                self.pos += 1
            elif char == ">":
                tok = Token(TokenType.OP_GT, ">", (start_pos, start_pos + 1), ">")
                self.pos += 1
            elif char == "%":
                tok = Token(TokenType.OP_PERCENT, "%", (start_pos, start_pos + 1), "%")
                self.pos += 1
            elif char == ":":
                tok = Token(TokenType.OP_COLON, ":", (start_pos, start_pos + 1), ":")
                self.pos += 1
            elif char == ",":
                tok = Token(TokenType.OP_COMMA, ",", (start_pos, start_pos + 1), ",")
                self.pos += 1
            elif char == ";":
                tok = Token(TokenType.OP_SEMICOLON, ";", (start_pos, start_pos + 1), ";")
                self.pos += 1
            elif char == "(":
                tok = Token(TokenType.LPAREN, "(", (start_pos, start_pos + 1), "(")
                self.pos += 1
            elif char == ")":
                tok = Token(TokenType.RPAREN, ")", (start_pos, start_pos + 1), ")")
                self.pos += 1
            elif char == "{":
                tok = Token(TokenType.LBRACE, "{", (start_pos, start_pos + 1), "{")
                self.pos += 1
            elif char == "}":
                tok = Token(TokenType.RBRACE, "}", (start_pos, start_pos + 1), "}")
                self.pos += 1
            else:
                # 8. Identifiers, Cell References, Functions, Booleans, Structured References
                tok = self._lex_ident_or_ref()

            tokens.append(tok)
            prev_token = tok

        tokens.append(Token(TokenType.EOF, "", (self.length, self.length), ""))
        return tokens

    def _lex_string(self) -> Token:
        """Parse double-quoted string literal with "" escape."""
        start_pos = self.pos
        self.pos += 1  # Skip opening quote
        chars: list[str] = []

        while self.pos < self.length:
            c = self.formula[self.pos]
            if c == '"':
                if self.pos + 1 < self.length and self.formula[self.pos + 1] == '"':
                    chars.append('"')
                    self.pos += 2
                else:
                    self.pos += 1  # Closing quote
                    val = "".join(chars)
                    raw = self.formula[start_pos : self.pos]
                    return Token(TokenType.STRING, val, (start_pos, self.pos), raw)
            else:
                chars.append(c)
                self.pos += 1

        raise LexerError("Unclosed string literal", start_pos)

    def _lex_number(self) -> Token:
        """Parse numeric literal (integer, decimal, scientific notation)."""
        start_pos = self.pos
        while self.pos < self.length and (self.formula[self.pos].isdigit() or self.formula[self.pos] == "."):
            self.pos += 1

        if self.pos < self.length and self.formula[self.pos] in "eE":
            self.pos += 1
            if self.pos < self.length and self.formula[self.pos] in "+-":
                self.pos += 1
            while self.pos < self.length and self.formula[self.pos].isdigit():
                self.pos += 1

        raw = self.formula[start_pos : self.pos]
        try:
            val = float(raw) if ("." in raw or "e" in raw or "E" in raw) else int(raw)
        except ValueError:
            raise LexerError(f"Invalid numeric literal '{raw}'", start_pos)

        return Token(TokenType.NUMBER, val, (start_pos, self.pos), raw)

    def _try_lex_error(self) -> Optional[Token]:
        """Check for Excel error literal starting at current position."""
        remaining = self.formula[self.pos :]
        for err in EXCEL_ERRORS:
            if remaining.upper().startswith(err):
                end_pos = self.pos + len(err)
                raw = self.formula[self.pos : end_pos]
                tok = Token(TokenType.ERROR, err, (self.pos, end_pos), raw)
                self.pos = end_pos
                return tok
        return None

    def _try_lex_quoted_ref(self) -> Optional[Token]:
        """Try parsing single-quoted sheet/workbook reference e.g. 'Sheet 1'!A1 or 'Rate Table'!A."""
        start_pos = self.pos
        # 1. Try full cell reference match
        cell_match = CELL_REF_REGEX.match(self.formula[self.pos :])
        if cell_match:
            raw_len = cell_match.end()
            end_pos = self.pos + raw_len
            raw = self.formula[self.pos : end_pos]
            self.pos = end_pos
            return Token(TokenType.CELL_REF, raw, (start_pos, end_pos), raw)

        # 2. Try sheet-qualified whole column match e.g. 'Rate Table'!A
        col_match = SHEET_COL_REF_REGEX.match(self.formula[self.pos :])
        if col_match:
            raw_len = col_match.end()
            end_pos = self.pos + raw_len
            raw = self.formula[self.pos : end_pos]
            self.pos = end_pos
            return Token(TokenType.IDENT, raw, (start_pos, end_pos), raw)

        return None

    def _lex_cell_or_col_ref(self) -> Token:
        """Parse cell or whole column reference starting with external workbook prefix [Book.xlsx]Sheet!."""
        start_pos = self.pos
        cell_match = CELL_REF_REGEX.match(self.formula[self.pos :])
        if cell_match:
            end_pos = self.pos + cell_match.end()
            raw = self.formula[self.pos : end_pos]
            self.pos = end_pos
            return Token(TokenType.CELL_REF, raw, (start_pos, end_pos), raw)

        col_match = SHEET_COL_REF_REGEX.match(self.formula[self.pos :])
        if col_match:
            end_pos = self.pos + col_match.end()
            raw = self.formula[self.pos : end_pos]
            self.pos = end_pos
            return Token(TokenType.IDENT, raw, (start_pos, end_pos), raw)

        raise LexerError(f"Malformed external workbook reference at position {start_pos}", start_pos)

    def _lex_structured_reference(self, table_name: Optional[str]) -> Token:
        """Parse structured reference starting at '['."""
        start_pos = self.pos if table_name is None else self.pos - len(table_name)
        open_bracket_pos = self.pos
        depth = 0
        in_string = False

        while self.pos < self.length:
            c = self.formula[self.pos]
            if c == '"':
                in_string = not in_string
                self.pos += 1
                continue
            if not in_string:
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        self.pos += 1
                        raw = self.formula[start_pos : self.pos]
                        return Token(TokenType.STRUCTURED_REF, raw, (start_pos, self.pos), raw)
            self.pos += 1

        raise LexerError("Unclosed structured reference brackets", open_bracket_pos)

    def _lex_ident_or_ref(self) -> Token:
        """Parse identifiers, cell references, function names, booleans, or structured references."""
        start_pos = self.pos

        # Check for Cell Reference matching CELL_REF_REGEX
        cell_match = CELL_REF_REGEX.match(self.formula[self.pos :])
        if cell_match:
            # Group indices: col letters is group 7, row digits is group 9
            # (due to the regex groups)
            groups = cell_match.groups()
            col_letters = [g for g in groups[-4:] if g and g.isalpha()]
            row_digits = [g for g in groups[-2:] if g and g.isdigit()]

            if col_letters and row_digits:
                col_str = col_letters[0]
                row_str = row_digits[0]
                col_idx = col_letter_to_index(col_str)
                row_idx = int(row_str)
                if 1 <= col_idx <= 16384 and 1 <= row_idx <= 1048576:
                    end_pos = self.pos + cell_match.end()
                    raw = self.formula[self.pos : end_pos]
                    if not (end_pos < self.length and self.formula[end_pos] == "("):
                        self.pos = end_pos
                        return Token(TokenType.CELL_REF, raw, (start_pos, end_pos), raw)

        # Standard identifier reading
        ident_chars: list[str] = []
        has_leading_dollar = False
        if self.formula[self.pos] == "$":
            has_leading_dollar = True
            ident_chars.append("$")
            self.pos += 1

        while self.pos < self.length and (self.formula[self.pos].isalnum() or self.formula[self.pos] in "._"):
            ident_chars.append(self.formula[self.pos])
            self.pos += 1

        raw_ident = "".join(ident_chars)
        if not raw_ident or raw_ident == "$":
            raise LexerError(f"Unexpected character '{self.formula[start_pos]}' at position {start_pos}", start_pos)

        # Check if immediately followed by '[': this is a structured reference e.g. Table1[Sales]
        if self.pos < self.length and self.formula[self.pos] == "[":
            return self._lex_structured_reference(table_name=raw_ident)

        # Check if followed by '!': Sheet qualification e.g. Sheet1!A1 or Sheet1!A
        if self.pos < self.length and self.formula[self.pos] == "!":
            self.pos += 1
            sub_match = CELL_REF_REGEX.match(self.formula[self.pos :])
            if sub_match:
                end_pos = self.pos + sub_match.end()
                raw = self.formula[start_pos : end_pos]
                self.pos = end_pos
                return Token(TokenType.CELL_REF, raw, (start_pos, end_pos), raw)

            # Check if followed by column letter e.g. Sheet1!A
            col_m = re.match(r"^(\$?)([A-Za-z]{1,3})\b", self.formula[self.pos :])
            if col_m:
                end_pos = self.pos + col_m.end()
                raw = self.formula[start_pos : end_pos]
                self.pos = end_pos
                return Token(TokenType.IDENT, raw, (start_pos, end_pos), raw)

            raw = self.formula[start_pos : self.pos]
            return Token(TokenType.IDENT, raw, (start_pos, self.pos), raw)

        # Check if followed by '(': this is a function call
        if self.pos < self.length and self.formula[self.pos] == "(":
            return Token(TokenType.FUNCTION, raw_ident.upper(), (start_pos, self.pos), raw_ident)

        # Check for boolean TRUE / FALSE
        upper_ident = raw_ident.upper()
        if not has_leading_dollar:
            if upper_ident == "TRUE":
                return Token(TokenType.BOOLEAN, True, (start_pos, self.pos), raw_ident)
            elif upper_ident == "FALSE":
                return Token(TokenType.BOOLEAN, False, (start_pos, self.pos), raw_ident)

        return Token(TokenType.IDENT, raw_ident, (start_pos, self.pos), raw_ident)
