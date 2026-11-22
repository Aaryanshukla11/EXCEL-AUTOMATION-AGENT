"""Directed Calculation Graph Construction and Cycle Sentinels for Excel Formulas (M05).

Builds directed dependency graphs with bounded range expansion, direct range containment
detection, Tarjan SCC cycle analysis, volatile function cataloging, and incomplete
dependency status guards adhering to FR-4 and FR-5.
"""

from __future__ import annotations

from enum import Enum
import re
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from excel_intel.core.types import FormulaGraphMetadata
from excel_intel.formulas.cycle_detector import CycleDetector
from excel_intel.formulas.lexer import col_letter_to_index, index_to_col_letter
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
)
from excel_intel.formulas.parser import FormulaParser


def extract_precedents(
    ast: Optional[BaseASTNode],
) -> list[Union[CellReferenceNode, RangeReferenceNode, StructuredReferenceNode]]:
    """Traverse AST and extract all precedent references (cells, ranges, structured refs)."""
    precedents: list[Union[CellReferenceNode, RangeReferenceNode, StructuredReferenceNode]] = []
    if ast is None:
        return precedents

    def _walk(node: BaseASTNode) -> None:
        if isinstance(node, (CellReferenceNode, RangeReferenceNode, StructuredReferenceNode)):
            precedents.append(node)
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
    CYCLES_DETECTED = "CYCLES_DETECTED"
    UNCERTAIN_INCOMPLETE_DEPENDENCIES = "UNCERTAIN_INCOMPLETE_DEPENDENCIES"


class DependencyNodeType(str, Enum):
    """Categorization of dependency graph nodes."""

    CELL = "CELL"
    RANGE = "RANGE"
    NAMED_RANGE = "NAMED_RANGE"
    EXTERNAL = "EXTERNAL"
    STRUCTURED_TABLE = "STRUCTURED_TABLE"


class DependencyNode(BaseModel):
    """Base immutable graph node representation."""

    node_id: str = Field(description="Unique canonical node identifier (e.g. 'Sheet1!A1')")
    node_type: DependencyNodeType
    sheet_name: Optional[str] = None
    is_external: bool = False

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
    else:
        sheet, coord = "Sheet1", cell_id
    m = re.match(r"^\$?([A-Za-z]+)\$?(\d+)$", coord)
    if not m:
        raise ValueError(f"Cannot parse cell ID '{cell_id}'")
    return sheet, col_letter_to_index(m.group(1)), int(m.group(2))


class FormulaDependencyGraph:
    """Constructs and analyzes workbook calculation dependency graphs."""

    def __init__(
        self,
        defined_names: Optional[dict[str, str]] = None,
        max_range_expansion: int = MAX_RANGE_EXPANSION,
    ) -> None:
        self.defined_names = defined_names or {}
        self.max_range_expansion = max_range_expansion

        # Directed adjacency: u -> v means v depends on precedent u
        self.adjacency: dict[str, set[str]] = {}
        self.nodes: dict[str, DependencyNode] = {}
        self.volatile_cells: set[str] = set()
        self.unparsed_cells: list[str] = []
        self.unsupported_cells: list[str] = []
        self.is_complete = True
        self.direct_cycles: list[list[str]] = []

    def add_formula(
        self,
        cell_id: str,
        formula_text: str,
        parse_result: Optional[FormulaParseResult] = None,
    ) -> None:
        """Ingest a formula cell and link its precedents into the calculation graph."""
        sheet, target_col, target_row = _parse_cell_id(cell_id)

        # Ensure target node exists
        self._ensure_node(
            cell_id,
            DependencyNodeType.CELL,
            sheet_name=sheet,
            is_external=False,
        )

        # Parse formula if result not provided
        if parse_result is None:
            parser = FormulaParser(formula_text)
            parse_result = parser.parse()

        # Check parse outcome status
        if parse_result.status == FormulaParseStatus.PARSE_ERROR:
            self.unparsed_cells.append(cell_id)
            self.is_complete = False
            return

        if parse_result.status == FormulaParseStatus.UNSUPPORTED_SYNTAX:
            self.unsupported_cells.append(cell_id)
            self.is_complete = False
            # Still attempt to link any extractable precedents from partial AST if present
            if parse_result.ast is None:
                return

        ast = parse_result.ast
        if ast is None:
            return

        # 1. Catalog volatile functions
        if self._contains_volatile_function(ast):
            self.volatile_cells.add(cell_id)

        # 2. Extract precedent references
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

    def analyze(self) -> FormulaGraphReport:
        """Execute cycle detection and compile comprehensive calculation graph report."""
        # Detect circular references via Tarjan's SCC
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
            # If graph is incomplete, we cannot claim NO_CYCLES with certainty
            cycle_status = (
                CycleStatus.CYCLES_DETECTED
                if has_cycles
                else CycleStatus.UNCERTAIN_INCOMPLETE_DEPENDENCIES
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
        )

    def _ensure_node(
        self,
        node_id: str,
        node_type: DependencyNodeType,
        sheet_name: Optional[str],
        is_external: bool,
    ) -> None:
        if node_id not in self.nodes:
            if len(self.nodes) >= MAX_GRAPH_NODES:
                return
            self.nodes[node_id] = DependencyNode(
                node_id=node_id,
                node_type=node_type,
                sheet_name=sheet_name,
                is_external=is_external,
            )

    def _add_edge(self, precedent_id: str, dependent_id: str) -> None:
        """Add directed edge (precedent -> dependent) where dependent depends on precedent."""
        total_edges = sum(len(targets) for targets in self.adjacency.values())
        if total_edges >= MAX_GRAPH_EDGES:
            return

        if precedent_id not in self.adjacency:
            self.adjacency[precedent_id] = set()
        self.adjacency[precedent_id].add(dependent_id)

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
