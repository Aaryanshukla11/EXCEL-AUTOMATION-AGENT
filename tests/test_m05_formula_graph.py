"""Unit tests for M05 Formula Dependency Graph Construction.

Validates directed calculation edge orientation (u -> v), bounded range expansion
(expansion for <= 1000 cells vs RangeNode hyper-edges for > 1000 cells and full col/row),
volatile function indexing, external references, and structured table references.
"""

import pytest

from excel_intel.formulas.graph import (
    DependencyNodeType,
    FormulaDependencyGraph,
)


def test_basic_cell_dependency_edge_orientation() -> None:
    """Test directed edge orientation: u -> v denotes that v depends on precedent u."""
    # Sheet1!C1 depends on Sheet1!A1 and Sheet1!B1
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!C1", "=A1 + B1")
    report = graph.analyze()

    assert report.node_count == 3  # A1, B1, C1
    assert report.edge_count == 2
    # Precedent A1 points to dependent C1
    assert "Sheet1!C1" in graph.adjacency.get("Sheet1!A1", set())
    assert "Sheet1!C1" in graph.adjacency.get("Sheet1!B1", set())


def test_bounded_range_expansion_compact_range() -> None:
    """Test compact range (<= 1000 cells) expands to individual cell edges (FR-4.2)."""
    # Sheet1!D1 = SUM(Sheet1!A1:B2) -> 4 cells
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!D1", "=SUM(Sheet1!A1:B2)")
    report = graph.analyze()

    # D1 + 4 cells = 5 nodes
    assert report.node_count == 5
    assert report.edge_count == 4
    for r in (1, 2):
        for c in ("A", "B"):
            cell_id = f"Sheet1!{c}{r}"
            assert cell_id in graph.nodes
            assert "Sheet1!D1" in graph.adjacency.get(cell_id, set())


def test_large_range_hyper_edge_bounding() -> None:
    """Test large range (> 1000 cells) is bounded to a single RangeNode hyper-edge (FR-4.2)."""
    # Sheet1!Z1 = SUM(Sheet1!A1:A2000) -> 2000 cells > 1000 threshold
    graph = FormulaDependencyGraph(max_range_expansion=1000)
    graph.add_formula("Sheet1!Z1", "=SUM(Sheet1!A1:A2000)")
    report = graph.analyze()

    # Z1 + 1 RangeNode = 2 nodes (NOT 2001 nodes!)
    assert report.node_count == 2
    assert report.edge_count == 1
    range_id = "Sheet1!A1:A2000"
    assert range_id in graph.nodes
    assert graph.nodes[range_id].node_type == DependencyNodeType.RANGE
    assert "Sheet1!Z1" in graph.adjacency.get(range_id, set())


def test_full_column_and_full_row_hyper_edges() -> None:
    """Test full column (A:A) and full row (1:1) stored as RangeNode hyper-edges (FR-4.2)."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!C1", "=SUM(A:A) + AVERAGE(1:1)")
    report = graph.analyze()

    assert report.node_count == 3  # C1, Sheet1!A:A, Sheet1!1:1
    assert report.edge_count == 2
    col_range_node = graph.nodes.get("Sheet1!A:A")
    assert col_range_node is not None
    assert col_range_node.node_type == DependencyNodeType.RANGE

    row_range_node = graph.nodes.get("Sheet1!1:1")
    assert row_range_node is not None
    assert row_range_node.node_type == DependencyNodeType.RANGE


def test_volatile_function_cataloging() -> None:
    """Test volatile function cataloging into volatile_cells (FR-5.3)."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A1", "=NOW()")
    graph.add_formula("Sheet1!A2", "=TODAY() + 1")
    graph.add_formula("Sheet1!A3", "=RAND() * 100")
    graph.add_formula("Sheet1!A4", "=OFFSET(B1, 1, 1)")
    graph.add_formula("Sheet1!A5", "=1 + 2")  # Non-volatile

    report = graph.analyze()
    assert len(report.volatile_cells) == 4
    assert "Sheet1!A1" in report.volatile_cells
    assert "Sheet1!A2" in report.volatile_cells
    assert "Sheet1!A3" in report.volatile_cells
    assert "Sheet1!A4" in report.volatile_cells
    assert "Sheet1!A5" not in report.volatile_cells


def test_external_and_structured_references() -> None:
    """Test external workbook references and structured table references."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!C1", "=[Budget.xlsx]Sheet2!A1 + Table1[Sales]")
    report = graph.analyze()

    assert report.node_count == 3
    ext_node = graph.nodes.get("[Budget.xlsx]Sheet2!A1")
    assert ext_node is not None
    assert ext_node.is_external is True
    assert ext_node.node_type == DependencyNodeType.EXTERNAL

    table_node = graph.nodes.get("Table1[Sales]")
    assert table_node is not None
    assert table_node.node_type == DependencyNodeType.STRUCTURED_TABLE
