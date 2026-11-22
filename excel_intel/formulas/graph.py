"""Directed Calculation Graph Construction and Cycle Sentinels for Excel Formulas (M05 Prompt 4).

Builds directed dependency calculation graphs with bounded range expansion,
range hyperedges, direct range containment cycle detection, Tarjan SCC cycle analysis,
defined names resolution (workbook and sheet-scoped), dynamic spill reference representation,
resource safety limits, volatile function cataloging, and incomplete dependency status guards.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from excel_intel.core.types import FormulaGraphMetadata
from excel_intel.formulas.cycle_detector import CycleDetector
from excel_intel.formulas.lexer import (
    FormulaLexer,
    TokenType,
    col_letter_to_index,
    index_to_col_letter,
)
from excel_intel.formulas.models import (
    ArrayLiteralNode,
    ASTNodeType,
    BaseASTNode,
    BinaryOpNode,
    CellReferenceNode,
    FormulaParseResult,
    FormulaParseStatus,
    FunctionCallNode,
    PostfixOpNode,
    RangeReferenceNode,
    StructuredReferenceNode,
    UnaryOpNode,
    UnsupportedFormulaNode,
)
from excel_intel.formulas.parser import FormulaParser, parse_cell_reference_string

# Multi-tier resource safety caps
MAX_RANGE_EXPANSION = 1_000
MAX_GRAPH_NODES = 50_000
MAX_GRAPH_EDGES = 100_000

# Excel volatile functions
VOLATILE_FUNCTIONS = {
    "NOW",
    "TODAY",
    "RAND",
    "RANDBETWEEN",
    "OFFSET",
    "INDIRECT",
    "INFO",
    "CELL",
}


class CycleStatus(str, Enum):
    """Cycle analysis status guard enum (FR-5.2)."""

    NO_CYCLES = "NO_CYCLES"
    VERIFIED_NO_CYCLES = "NO_CYCLES"
    CYCLES_DETECTED = "CYCLES_DETECTED"
    POTENTIAL_CYCLES_UNVERIFIED = "POTENTIAL_CYCLES_UNVERIFIED"
    UNCERTAIN_INCOMPLETE_DEPENDENCIES = "POTENTIAL_CYCLES_UNVERIFIED"


class DependencyNodeType(str, Enum):
    """Categorization of dependency graph nodes."""

    CELL = "CELL"
    RANGE = "RANGE"
    NAMED_RANGE = "NAMED_RANGE"
    EXTERNAL = "EXTERNAL"
    STRUCTURED_TABLE = "STRUCTURED_TABLE"
    DYNAMIC_SPILL = "DYNAMIC_SPILL"
    UNRESOLVED = "UNRESOLVED"


class DynamicSpillReference(BaseModel):
    """Explicit model representing a dynamic array spill reference (e.g. A1#)."""

    raw_reference: str
    anchor_cell: CellReferenceNode
    sheet_name: Optional[str] = None

    model_config = ConfigDict(frozen=True)


PrecedentItem = Union[
    CellReferenceNode,
    RangeReferenceNode,
    StructuredReferenceNode,
    DynamicSpillReference,
]


def extract_precedents(
    ast: Optional[BaseASTNode],
) -> list[PrecedentItem]:
    """Traverse AST and extract all precedent references (cells, ranges, structured refs, spills)."""
    precedents: list[PrecedentItem] = []
    if ast is None:
        return precedents

    def _walk(node: BaseASTNode) -> None:
        if isinstance(node, (CellReferenceNode, RangeReferenceNode, StructuredReferenceNode)):
            precedents.append(node)
            return

        if isinstance(node, UnsupportedFormulaNode):
            if node.syntax_category == "DYNAMIC_ARRAY_SPILL":
                # Dynamic array spill operator '#' e.g. A1# or Sheet2!$B$5#
                raw_ref = node.raw_formula.rstrip("#").strip()
                try:
                    anchor = parse_cell_reference_string(raw_ref, node.span)
                    precedents.append(
                        DynamicSpillReference(
                            raw_reference=node.raw_formula,
                            anchor_cell=anchor,
                            sheet_name=anchor.sheet_name,
                        )
                    )
                except Exception:
                    pass
            return

        if isinstance(node, FunctionCallNode):
            for arg in node.arguments:
                _walk(arg)
        elif isinstance(node, BinaryOpNode):
            _walk(node.left)
            _walk(node.right)
        elif isinstance(node, UnaryOpNode):
            _walk(node.operand)
        elif isinstance(node, PostfixOpNode):
            _walk(node.operand)
        elif isinstance(node, ArrayLiteralNode):
            for row in node.rows:
                for elem in row:
                    _walk(elem)

    _walk(ast)
    return precedents


class DependencyNode(BaseModel):
    """Base immutable graph node representation."""

    node_id: str = Field(description="Unique canonical node identifier (e.g. 'Sheet1!A1')")
    node_type: DependencyNodeType
    sheet_name: Optional[str] = None
    is_external: bool = False
    is_dynamic: bool = False
    is_unresolved: bool = False
    anchor_id: Optional[str] = None
    details: Optional[str] = None

    model_config = ConfigDict(frozen=True)


class FormulaGraphReport(BaseModel):
    """Comprehensive analytical report produced by formula calculation graph construction."""

    node_count: int = Field(ge=0, description="Total unique precedent and dependent nodes in the graph")
    edge_count: int = Field(ge=0, description="Total directed calculation dependency edges (u -> v)")
    has_cycles: bool = Field(description="True if one or more confirmed calculation cycles exist")
    cycle_status: CycleStatus = Field(description="Explicit cycle status guard")
    is_complete: bool = Field(description="True if all dependencies were fully resolved without gaps")
    circular_paths: list[list[str]] = Field(default_factory=list, description="Exact cycle paths detected")
    volatile_cells: list[str] = Field(default_factory=list, description="Coordinates calling volatile functions")
    unparsed_cells: list[str] = Field(default_factory=list, description="Coordinates failing parsing")
    unsupported_cells: list[str] = Field(default_factory=list, description="Coordinates containing unsupported syntax")
    unresolved_dependencies: list[str] = Field(default_factory=list, description="Explicit list of unresolved dependencies")
    incompleteness_reasons: list[str] = Field(default_factory=list, description="Reasons explaining graph incompleteness")
    has_dynamic_spills: bool = Field(default=False, description="True if graph contains dynamic spill references")

    model_config = ConfigDict(frozen=True)

    def to_formula_graph_metadata(self) -> FormulaGraphMetadata:
        """Losslessly project to canonical M01 FormulaGraphMetadata."""
        return FormulaGraphMetadata(
            node_count=self.node_count,
            edge_count=self.edge_count,
            has_cycles=self.has_cycles,
            volatile_cells=list(self.volatile_cells),
        )


def _canonical_cell_id(sheet_name: str, col: int, row: int) -> str:
    """Format canonical cell ID e.g. Sheet1!A1."""
    return f"{sheet_name}!{index_to_col_letter(col)}{row}"


def _canonical_range_id(sheet_name: str, col_s: int, row_s: int, col_e: int, row_e: int) -> str:
    """Format canonical range ID e.g. Sheet1!A1:B10."""
    return f"{sheet_name}!{index_to_col_letter(col_s)}{row_s}:{index_to_col_letter(col_e)}{row_e}"


def _parse_cell_id(cell_id: str) -> tuple[str, int, int]:
    """Parse canonical cell ID 'Sheet1!A1' into (sheet_name, col_idx, row_idx)."""
    if "!" in cell_id:
        sheet, coord = cell_id.split("!", 1)
        sheet = sheet.strip("'")
    else:
        sheet, coord = "Sheet1", cell_id
    m = re.match(r"^\$?([A-Za-z]+)\$?(\d+)$", coord)
    if not m:
        raise ValueError(f"Cannot parse cell ID '{cell_id}'")
    return sheet, col_letter_to_index(m.group(1)), int(m.group(2))


def _is_valid_cell_reference(text: str) -> bool:
    """Check if token string represents a standard A1 cell reference rather than a defined name."""
    clean = text.strip()
    if "!" in clean:
        clean = clean.split("!", 1)[1]
    m = re.match(r"^\$?([A-Za-z]{1,3})\$?(\d{1,7})$", clean)
    if not m:
        return False
    try:
        col = col_letter_to_index(m.group(1))
        row = int(m.group(2))
        return 1 <= col <= 16384 and 1 <= row <= 1048576
    except Exception:
        return False


class FormulaDependencyGraph:
    """Constructs and analyzes workbook calculation dependency graphs."""

    def __init__(
        self,
        defined_names: Optional[dict[str, Any]] = None,
        max_range_expansion: int = MAX_RANGE_EXPANSION,
        max_nodes: int = MAX_GRAPH_NODES,
        max_edges: int = MAX_GRAPH_EDGES,
    ) -> None:
        self.raw_defined_names = defined_names or {}
        self.max_range_expansion = max_range_expansion
        self.max_nodes = max_nodes
        self.max_edges = max_edges

        # Normalized defined names:
        # sheet_defined_names: {sheet_name: {name: target_expression}}
        # global_defined_names: {name: target_expression}
        self.sheet_defined_names: dict[str, dict[str, str]] = {}
        self.global_defined_names: dict[str, str] = {}
        self._init_defined_names(self.raw_defined_names)

        # Directed adjacency: u -> v means v depends on precedent u
        self.adjacency: dict[str, set[str]] = {}
        self.nodes: dict[str, DependencyNode] = {}
        self.volatile_cells: set[str] = set()
        self.unparsed_cells: list[str] = []
        self.unsupported_cells: list[str] = []
        self.unresolved_dependencies: list[str] = []
        self.has_dynamic_spills: bool = False
        self.is_complete: bool = True
        self.incompleteness_reasons: list[str] = []
        self.direct_cycles: list[list[str]] = []

    def _init_defined_names(self, raw_names: dict[str, Any]) -> None:
        """Normalize defined names into sheet-scoped and workbook-level dictionaries."""
        for k, v in raw_names.items():
            if isinstance(v, dict):
                sheet = k.strip().strip("'")
                for sub_k, sub_v in v.items():
                    name_clean = sub_k.strip().upper()
                    target = str(sub_v).strip()
                    if sheet == "" or sheet.upper() == "GLOBAL":
                        self.global_defined_names[name_clean] = target
                    else:
                        if sheet not in self.sheet_defined_names:
                            self.sheet_defined_names[sheet] = {}
                        self.sheet_defined_names[sheet][name_clean] = target
            else:
                target = str(v).strip()
                if "!" in k:
                    sheet_part, name_part = k.split("!", 1)
                    sheet_clean = sheet_part.strip().strip("'")
                    name_clean = name_part.strip().upper()
                    if sheet_clean not in self.sheet_defined_names:
                        self.sheet_defined_names[sheet_clean] = {}
                    self.sheet_defined_names[sheet_clean][name_clean] = target
                else:
                    self.global_defined_names[k.strip().upper()] = target

    def resolve_defined_name(
        self,
        name: str,
        current_sheet: str,
        visited: Optional[set[str]] = None,
    ) -> tuple[Optional[str], Optional[str], bool, bool]:
        """Resolve a defined name using scope precedence (sheet-scoped over workbook-level).

        Args:
            name: The raw identifier or qualified name (e.g. 'TaxRate' or 'Sheet2!TaxRate').
            current_sheet: The sheet in which the formula resides.
            visited: Set of previously visited name keys to prevent infinite recursion.

        Returns:
            Tuple of (target_ref, resolved_scope, is_recursive, is_unresolved).
        """
        if visited is None:
            visited = set()

        raw_clean = name.strip()
        target_sheet = current_sheet
        if "!" in raw_clean:
            s_part, n_part = raw_clean.split("!", 1)
            target_sheet = s_part.strip().strip("'")
            name_clean = n_part.strip().upper()
        else:
            name_clean = raw_clean.upper()

        # 1. Check sheet-scoped names first (precedence)
        target = None
        scope = None
        if target_sheet in self.sheet_defined_names and name_clean in self.sheet_defined_names[target_sheet]:
            target = self.sheet_defined_names[target_sheet][name_clean]
            scope = target_sheet
        elif name_clean in self.global_defined_names:
            target = self.global_defined_names[name_clean]
            scope = "WORKBOOK"

        if target is None:
            # Unresolved name
            return None, None, False, True

        key = f"{scope}!{name_clean}"
        if key in visited:
            # Recursive cycle detected in defined names
            return target, scope, True, False

        visited.add(key)

        # Check if target points to another defined name (alias) rather than a cell or range
        clean_target = target.lstrip("=").strip()
        if not _is_valid_cell_reference(clean_target) and ":" not in clean_target and not re.search(r"[+\-*/()\[\]]", clean_target):
            # Attempt recursive resolution of alias
            sub_target, sub_scope, is_rec, is_unres = self.resolve_defined_name(
                clean_target, current_sheet=target_sheet, visited=visited
            )
            if is_rec:
                return sub_target, sub_scope, True, False
            if not is_unres and sub_target is not None:
                return sub_target, sub_scope, False, False

        return target, scope, False, False

    def add_formula(
        self,
        cell_id: str,
        formula_text: str,
        parse_result: Optional[FormulaParseResult] = None,
    ) -> None:
        """Ingest a formula cell and link its precedents into the calculation graph."""
        sheet, target_col, target_row = _parse_cell_id(cell_id)

        # Ensure target dependent node exists
        self._ensure_node(
            cell_id,
            DependencyNodeType.CELL,
            sheet_name=sheet,
            is_external=False,
        )

        working_formula = formula_text

        # 1. Defined Names Pre-Scan & Resolution via Lexer
        try:
            tokens = FormulaLexer(formula_text).tokenize()
            replacements: list[tuple[int, int, str]] = []

            for i, tok in enumerate(tokens):
                if tok.token_type == TokenType.IDENT:
                    # Check if next token is '(' (function call)
                    if i + 1 < len(tokens) and tokens[i + 1].token_type == TokenType.LPAREN:
                        continue

                    # Skip if token is part of a colon range expression (e.g. A:A or Sheet1!A:A)
                    if i + 1 < len(tokens) and tokens[i + 1].token_type == TokenType.OP_COLON:
                        continue
                    if i > 0 and tokens[i - 1].token_type == TokenType.OP_COLON:
                        continue

                    # Check if it is a standard cell coordinate (A1)
                    if _is_valid_cell_reference(tok.raw_text):
                        continue

                    raw_ident = tok.raw_text
                    target, scope, is_recursive, is_unresolved = self.resolve_defined_name(
                        raw_ident, current_sheet=sheet
                    )

                    name_node_id = f"NAME:{raw_ident}" if "!" in raw_ident else f"NAME:{sheet}!{raw_ident}" if scope == sheet else f"NAME:{raw_ident}"

                    if is_recursive:
                        self._ensure_node(name_node_id, DependencyNodeType.NAMED_RANGE, sheet_name=sheet, is_external=False)
                        self._add_edge(name_node_id, cell_id)
                        self.direct_cycles.append([name_node_id, name_node_id])
                        self.is_complete = False
                        self.incompleteness_reasons.append(
                            f"Recursive defined name '{raw_ident}' referenced in cell '{cell_id}'"
                        )
                        continue

                    if is_unresolved:
                        unres_id = f"UNRESOLVED:{raw_ident}"
                        self._ensure_node(
                            unres_id,
                            DependencyNodeType.UNRESOLVED,
                            sheet_name=sheet,
                            is_external=False,
                            is_unresolved=True,
                            details=f"Unresolved defined name '{raw_ident}'",
                        )
                        self._add_edge(unres_id, cell_id)
                        self.unresolved_dependencies.append(f"{cell_id} -> {raw_ident}")
                        self.is_complete = False
                        self.incompleteness_reasons.append(
                            f"Unresolved defined name '{raw_ident}' referenced in cell '{cell_id}'"
                        )
                        continue

                    # Successfully resolved defined name
                    self._ensure_node(name_node_id, DependencyNodeType.NAMED_RANGE, sheet_name=sheet, is_external=False)
                    self._add_edge(name_node_id, cell_id)

                    # Link the underlying resolved target cell or range to the named range node and dependent cell
                    resolved_target = str(target).lstrip("=").strip()
                    self._link_resolved_name_target(resolved_target, name_node_id, cell_id, sheet)

                    # Prepare token text substitution for parser
                    replacements.append((tok.span[0], tok.span[1], resolved_target))

            # Apply replacements in reverse order of span to preserve character offsets
            if replacements and parse_result is None:
                mod_chars = list(working_formula)
                for start, end, rep in sorted(replacements, key=lambda x: x[0], reverse=True):
                    mod_chars[start:end] = list(rep)
                working_formula = "".join(mod_chars)

        except Exception as e:
            # If lexing for defined names fails, record and fall back to raw formula
            self.is_complete = False
            self.incompleteness_reasons.append(f"Defined names pre-scan error in cell '{cell_id}': {e}")

        # Parse formula if result not provided
        if parse_result is None:
            parser = FormulaParser(working_formula)
            parse_result = parser.parse()

        # Check parse outcome status
        if parse_result.status == FormulaParseStatus.PARSE_ERROR:
            self.unparsed_cells.append(cell_id)
            self.is_complete = False
            self.incompleteness_reasons.append(f"Formula parse error in cell '{cell_id}': {parse_result.error_message}")
            return

        if parse_result.status == FormulaParseStatus.UNSUPPORTED_SYNTAX:
            self.unsupported_cells.append(cell_id)
            self.is_complete = False
            self.incompleteness_reasons.append(
                f"Unsupported syntax ({parse_result.syntax_category}) in cell '{cell_id}'"
            )
            # Still attempt to link any extractable precedents from partial AST if present
            if parse_result.ast is None:
                return

        ast = parse_result.ast
        if ast is None:
            return

        # 2. Catalog volatile functions
        if self._contains_volatile_function(ast):
            self.volatile_cells.add(cell_id)

        # 3. Extract precedent references from AST
        precedents = extract_precedents(ast)

        for prec in precedents:
            if isinstance(prec, CellReferenceNode):
                prec_sheet = prec.sheet_name or sheet
                if prec.workbook_name:
                    # External cell reference
                    ext_id = f"[{prec.workbook_name}]{prec_sheet}!{prec.col_letter}{prec.row}"
                    self._ensure_node(ext_id, DependencyNodeType.EXTERNAL, sheet_name=prec_sheet, is_external=True)
                    self._add_edge(ext_id, cell_id)
                else:
                    prec_id = _canonical_cell_id(prec_sheet, prec.col, prec.row)
                    self._ensure_node(prec_id, DependencyNodeType.CELL, sheet_name=prec_sheet, is_external=False)
                    self._add_edge(prec_id, cell_id)
                    # Check direct self-loop
                    if prec_id == cell_id:
                        self.direct_cycles.append([cell_id, cell_id])

            elif isinstance(prec, DynamicSpillReference):
                # Dynamic array spill reference (e.g. A1# or Sheet2!$B$5#)
                anchor = prec.anchor_cell
                prec_sheet = anchor.sheet_name or sheet
                if anchor.workbook_name:
                    anchor_id = f"[{anchor.workbook_name}]{prec_sheet}!{anchor.col_letter}{anchor.row}"
                else:
                    anchor_id = _canonical_cell_id(prec_sheet, anchor.col, anchor.row)
                spill_id = f"{anchor_id}#"

                self.has_dynamic_spills = True
                self.is_complete = False
                self.incompleteness_reasons.append(
                    f"Cell '{cell_id}' depends on dynamic spill reference '{spill_id}' with unresolvable runtime extents"
                )

                # Ensure anchor node and dynamic spill node
                self._ensure_node(anchor_id, DependencyNodeType.CELL, sheet_name=prec_sheet, is_external=bool(anchor.workbook_name))
                self._ensure_node(
                    spill_id,
                    DependencyNodeType.DYNAMIC_SPILL,
                    sheet_name=prec_sheet,
                    is_external=bool(anchor.workbook_name),
                    is_dynamic=True,
                    anchor_id=anchor_id,
                )
                self._add_edge(anchor_id, spill_id)
                self._add_edge(spill_id, cell_id)

                # Direct containment check: anchor equals cell
                if anchor_id == cell_id:
                    self.direct_cycles.append([cell_id, spill_id, cell_id])

            elif isinstance(prec, RangeReferenceNode):
                prec_sheet = prec.sheet_name or sheet
                if prec.workbook_name or prec.is_3d:
                    # External or 3D range node (unexpanded)
                    range_id = f"{prec.raw_reference}"
                    self._ensure_node(range_id, DependencyNodeType.RANGE, sheet_name=prec_sheet, is_external=bool(prec.workbook_name))
                    self._add_edge(range_id, cell_id)
                    continue

                if prec.is_full_col or prec.is_full_row:
                    # Unbounded full col / full row: store as RangeNode hyper-edge (FR-4.2)
                    range_id = f"{prec_sheet}!{prec.raw_reference}"
                    self._ensure_node(range_id, DependencyNodeType.RANGE, sheet_name=prec_sheet, is_external=False)
                    self._add_edge(range_id, cell_id)

                    # Check direct range containment cycle: does target cell fall into this full col/row?
                    if prec_sheet == sheet:
                        if prec.is_full_col and prec.start_cell.col <= target_col <= prec.end_cell.col:
                            self.direct_cycles.append([cell_id, range_id, cell_id])
                        elif prec.is_full_row and prec.start_cell.row <= target_row <= prec.end_cell.row:
                            self.direct_cycles.append([cell_id, range_id, cell_id])
                    continue

                # Finite bounded 2D range
                col_min = min(prec.start_cell.col, prec.end_cell.col)
                col_max = max(prec.start_cell.col, prec.end_cell.col)
                row_min = min(prec.start_cell.row, prec.end_cell.row)
                row_max = max(prec.start_cell.row, prec.end_cell.row)
                cell_count = (col_max - col_min + 1) * (row_max - row_min + 1)

                # Check direct range containment cycle: does target cell fall within range bounds?
                if prec_sheet == sheet and (col_min <= target_col <= col_max) and (row_min <= target_row <= row_max):
                    range_id = _canonical_range_id(prec_sheet, col_min, row_min, col_max, row_max)
                    self.direct_cycles.append([cell_id, range_id, cell_id])

                if cell_count <= self.max_range_expansion:
                    # Check if expanding would breach max_edges
                    current_edge_count = sum(len(targets) for targets in self.adjacency.values())
                    if current_edge_count + cell_count > self.max_edges:
                        # Edge cap reached during expansion: stop safely and store as hyperedge
                        self.is_complete = False
                        self.incompleteness_reasons.append(
                            f"Range expansion of {cell_count} cells would exceed maximum edges limit ({self.max_edges})"
                        )
                        range_id = _canonical_range_id(prec_sheet, col_min, row_min, col_max, row_max)
                        self._ensure_node(range_id, DependencyNodeType.RANGE, sheet_name=prec_sheet, is_external=False)
                        self._add_edge(range_id, cell_id)
                    else:
                        # Compact range: expand to individual cell edges (FR-4.2)
                        for r in range(row_min, row_max + 1):
                            for c in range(col_min, col_max + 1):
                                p_id = _canonical_cell_id(prec_sheet, c, r)
                                self._ensure_node(p_id, DependencyNodeType.CELL, sheet_name=prec_sheet, is_external=False)
                                self._add_edge(p_id, cell_id)
                else:
                    # Large range (> 1,000 cells): store as single RangeNode with hyper-edge (FR-4.2)
                    range_id = _canonical_range_id(prec_sheet, col_min, row_min, col_max, row_max)
                    self._ensure_node(range_id, DependencyNodeType.RANGE, sheet_name=prec_sheet, is_external=False)
                    self._add_edge(range_id, cell_id)

            elif isinstance(prec, StructuredReferenceNode):
                # Structured reference e.g. Table1[Sales]
                struct_id = prec.raw_reference
                self._ensure_node(struct_id, DependencyNodeType.STRUCTURED_TABLE, sheet_name=sheet, is_external=False)
                self._add_edge(struct_id, cell_id)

    def _link_resolved_name_target(
        self,
        target_ref: str,
        name_node_id: str,
        dependent_cell_id: str,
        default_sheet: str,
    ) -> None:
        """Link a resolved defined name target to its named range node and dependent formula cell."""
        clean_target = target_ref.strip()
        target_sheet = default_sheet
        if "!" in clean_target:
            s_part, clean_target = clean_target.split("!", 1)
            target_sheet = s_part.strip().strip("'")

        if ":" in clean_target:
            # Range reference e.g. A1:B10
            parts = clean_target.split(":")
            if len(parts) == 2 and _is_valid_cell_reference(parts[0]) and _is_valid_cell_reference(parts[1]):
                try:
                    c1 = parse_cell_reference_string(parts[0], (0, len(parts[0])))
                    c2 = parse_cell_reference_string(parts[1], (0, len(parts[1])))
                    col_min, col_max = min(c1.col, c2.col), max(c1.col, c2.col)
                    row_min, row_max = min(c1.row, c2.row), max(c1.row, c2.row)
                    cell_count = (col_max - col_min + 1) * (row_max - row_min + 1)

                    if cell_count <= self.max_range_expansion:
                        for r in range(row_min, row_max + 1):
                            for c in range(col_min, col_max + 1):
                                p_id = _canonical_cell_id(target_sheet, c, r)
                                self._ensure_node(p_id, DependencyNodeType.CELL, sheet_name=target_sheet, is_external=False)
                                self._add_edge(p_id, name_node_id)
                                self._add_edge(p_id, dependent_cell_id)
                    else:
                        range_id = _canonical_range_id(target_sheet, col_min, row_min, col_max, row_max)
                        self._ensure_node(range_id, DependencyNodeType.RANGE, sheet_name=target_sheet, is_external=False)
                        self._add_edge(range_id, name_node_id)
                        self._add_edge(range_id, dependent_cell_id)
                except Exception:
                    pass
        elif _is_valid_cell_reference(clean_target):
            # Single cell reference e.g. $B$1
            try:
                c_node = parse_cell_reference_string(clean_target, (0, len(clean_target)))
                p_id = _canonical_cell_id(target_sheet, c_node.col, c_node.row)
                self._ensure_node(p_id, DependencyNodeType.CELL, sheet_name=target_sheet, is_external=False)
                self._add_edge(p_id, name_node_id)
                self._add_edge(p_id, dependent_cell_id)
            except Exception:
                pass

    def analyze(self) -> FormulaGraphReport:
        """Execute cycle detection and compile comprehensive calculation graph report."""
        # Detect circular references via iterative Tarjan's SCC
        detector = CycleDetector(self.adjacency)
        scc_cycles = detector.find_cycles()

        # Combine direct containment cycles and Tarjan SCC cycles
        all_cycles = list(self.direct_cycles)
        seen_cycle_keys = {tuple(p) for p in all_cycles}

        for path in scc_cycles:
            key = tuple(path)
            if key not in seen_cycle_keys:
                all_cycles.append(path)
                seen_cycle_keys.add(key)

        has_cycles = len(all_cycles) > 0

        # Enforce FR-5.2 Incomplete Graph Invariant
        if not self.is_complete:
            # If graph is incomplete or has dynamic spills, we cannot claim NO_CYCLES with certainty
            cycle_status = (
                CycleStatus.CYCLES_DETECTED
                if has_cycles
                else CycleStatus.POTENTIAL_CYCLES_UNVERIFIED
            )
        else:
            cycle_status = (
                CycleStatus.CYCLES_DETECTED if has_cycles else CycleStatus.NO_CYCLES
            )

        edge_count = sum(len(targets) for targets in self.adjacency.values())

        return FormulaGraphReport(
            node_count=len(self.nodes),
            edge_count=edge_count,
            has_cycles=has_cycles,
            cycle_status=cycle_status,
            is_complete=self.is_complete,
            circular_paths=all_cycles,
            volatile_cells=sorted(self.volatile_cells),
            unparsed_cells=sorted(self.unparsed_cells),
            unsupported_cells=sorted(self.unsupported_cells),
            unresolved_dependencies=sorted(self.unresolved_dependencies),
            incompleteness_reasons=sorted(set(self.incompleteness_reasons)),
            has_dynamic_spills=self.has_dynamic_spills,
        )

    def _ensure_node(
        self,
        node_id: str,
        node_type: DependencyNodeType,
        sheet_name: Optional[str] = None,
        is_external: bool = False,
        is_dynamic: bool = False,
        is_unresolved: bool = False,
        anchor_id: Optional[str] = None,
        details: Optional[str] = None,
    ) -> bool:
        """Ensure a dependency node exists in the graph, respecting MAX_GRAPH_NODES limit."""
        if node_id not in self.nodes:
            if len(self.nodes) >= self.max_nodes:
                self.is_complete = False
                reason = f"Maximum graph nodes limit reached ({self.max_nodes})"
                if reason not in self.incompleteness_reasons:
                    self.incompleteness_reasons.append(reason)
                return False

            self.nodes[node_id] = DependencyNode(
                node_id=node_id,
                node_type=node_type,
                sheet_name=sheet_name,
                is_external=is_external,
                is_dynamic=is_dynamic,
                is_unresolved=is_unresolved,
                anchor_id=anchor_id,
                details=details,
            )
        return True

    def _add_edge(self, precedent_id: str, dependent_id: str) -> bool:
        """Add directed edge (precedent -> dependent), respecting MAX_GRAPH_EDGES limit."""
        total_edges = sum(len(targets) for targets in self.adjacency.values())
        if total_edges >= self.max_edges:
            self.is_complete = False
            reason = f"Maximum graph edges limit reached ({self.max_edges})"
            if reason not in self.incompleteness_reasons:
                self.incompleteness_reasons.append(reason)
            return False

        if precedent_id not in self.adjacency:
            self.adjacency[precedent_id] = set()
        self.adjacency[precedent_id].add(dependent_id)
        return True

    def _contains_volatile_function(self, ast: BaseASTNode) -> bool:
        """Check if AST subtree calls any volatile Excel functions."""
        if isinstance(ast, FunctionCallNode):
            if ast.function_name.upper() in VOLATILE_FUNCTIONS:
                return True
            for arg in ast.arguments:
                if self._contains_volatile_function(arg):
                    return True
        elif isinstance(ast, BinaryOpNode):
            return self._contains_volatile_function(ast.left) or self._contains_volatile_function(ast.right)
        elif isinstance(ast, UnaryOpNode):
            return self._contains_volatile_function(ast.operand)
        elif isinstance(ast, PostfixOpNode):
            return self._contains_volatile_function(ast.operand)
        return False
