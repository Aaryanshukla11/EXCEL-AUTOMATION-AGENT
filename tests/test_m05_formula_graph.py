"""Unit tests for M05 Formula Dependency Graph Construction.

Validates directed calculation edge orientation (u -> v), bounded range expansion
(expansion for <= 1000 cells vs RangeNode hyper-edges for > 1000 cells and full col/row),
volatile function indexing, external references, and structured table references.
"""

import pytest

from excel_intel.formulas.graph import (
    CycleStatus,
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


def test_defined_names_workbook_level_resolution() -> None:
    """Test resolution of workbook-level defined names to underlying cell targets."""
    defined_names = {"TaxRate": "Sheet1!B1"}
    graph = FormulaDependencyGraph(defined_names=defined_names)
    graph.add_formula("Sheet1!C1", "=A1 * TaxRate")
    report = graph.analyze()

    assert report.is_complete is True
    assert report.cycle_status == CycleStatus.NO_CYCLES
    assert "NAME:TaxRate" in graph.nodes
    assert graph.nodes["NAME:TaxRate"].node_type == DependencyNodeType.NAMED_RANGE
    assert "Sheet1!C1" in graph.adjacency.get("NAME:TaxRate", set())
    assert "NAME:TaxRate" in graph.adjacency.get("Sheet1!B1", set())


def test_defined_names_sheet_scoped_precedence() -> None:
    """Test sheet-scoped defined name overrides workbook-level defined name."""
    defined_names = {
        "Discount": "Sheet1!B1",
        "Sheet2!Discount": "Sheet2!B2",
    }
    graph = FormulaDependencyGraph(defined_names=defined_names)
    graph.add_formula("Sheet2!C1", "=A1 * Discount")
    report = graph.analyze()

    assert report.is_complete is True
    assert "Sheet2!B2" in graph.nodes
    assert "Sheet1!B1" not in graph.nodes
    assert "Sheet2!C1" in graph.adjacency.get("Sheet2!B2", set())


def test_defined_names_range_target() -> None:
    """Test defined name pointing to a range expands into precedent cell edges."""
    defined_names = {"SalesData": "Sheet1!A1:B2"}
    graph = FormulaDependencyGraph(defined_names=defined_names)
    graph.add_formula("Sheet1!D1", "=SUM(SalesData)")
    report = graph.analyze()

    assert report.is_complete is True
    assert "NAME:SalesData" in graph.nodes
    for r in (1, 2):
        for c in ("A", "B"):
            cell_id = f"Sheet1!{c}{r}"
            assert cell_id in graph.nodes
            assert "Sheet1!D1" in graph.adjacency.get(cell_id, set())


def test_defined_names_unresolved() -> None:
    """Test unresolved defined name creates UNRESOLVED node and sets incomplete status."""
    graph = FormulaDependencyGraph(defined_names={})
    graph.add_formula("Sheet1!C1", "=A1 * UnknownRate")
    report = graph.analyze()

    assert report.is_complete is False
    assert report.cycle_status == CycleStatus.POTENTIAL_CYCLES_UNVERIFIED
    unres_node = graph.nodes.get("UNRESOLVED:UnknownRate")
    assert unres_node is not None
    assert unres_node.node_type == DependencyNodeType.UNRESOLVED
    assert unres_node.is_unresolved is True
    assert any("UnknownRate" in r for r in report.incompleteness_reasons)


def test_defined_names_recursive_cycle() -> None:
    """Test recursive cycle between defined names is flagged as cycle and incomplete."""
    defined_names = {
        "RateA": "RateB",
        "RateB": "RateA",
    }
    graph = FormulaDependencyGraph(defined_names=defined_names)
    graph.add_formula("Sheet1!C1", "=A1 + RateA")
    report = graph.analyze()

    assert report.is_complete is False
    assert report.has_cycles is True
    assert report.cycle_status == CycleStatus.CYCLES_DETECTED
    assert any("Recursive defined name" in r for r in report.incompleteness_reasons)


def test_dynamic_spill_reference_semantics() -> None:
    """Test dynamic array spill reference (A1#) preserves anchor and marks dynamic/unbounded."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!D1", "=SUM(Sheet1!A1#)")
    report = graph.analyze()

    assert report.has_dynamic_spills is True
    assert report.is_complete is False
    assert report.cycle_status == CycleStatus.POTENTIAL_CYCLES_UNVERIFIED
    assert "Sheet1!A1" in graph.nodes
    spill_node = graph.nodes.get("Sheet1!A1#")
    assert spill_node is not None
    assert spill_node.node_type == DependencyNodeType.DYNAMIC_SPILL
    assert spill_node.is_dynamic is True
    assert spill_node.anchor_id == "Sheet1!A1"
    assert "Sheet1!A1#" in graph.adjacency.get("Sheet1!A1", set())
    assert "Sheet1!D1" in graph.adjacency.get("Sheet1!A1#", set())


def test_dynamic_spill_cycle() -> None:
    """Test direct cycle formed by dynamic array spill reference."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A1", "=A1#")
    report = graph.analyze()

    assert report.has_cycles is True
    assert report.cycle_status == CycleStatus.CYCLES_DETECTED
    assert any("Sheet1!A1" in path for path in report.circular_paths)


def test_resource_safety_limits_nodes_and_edges() -> None:
    """Test node and edge caps prevent unbounded expansion and mark graph incomplete."""
    graph = FormulaDependencyGraph(max_nodes=3, max_edges=3)
    graph.add_formula("Sheet1!D1", "=A1 + B1 + C1")
    report = graph.analyze()

    assert report.is_complete is False
    assert report.cycle_status == CycleStatus.POTENTIAL_CYCLES_UNVERIFIED
    assert any("limit reached" in r for r in report.incompleteness_reasons)


def test_range_expansion_edge_cap_fallback() -> None:
    """Test range expansion falling back to hyperedge when edge cap would be breached."""
    graph = FormulaDependencyGraph(max_range_expansion=100, max_edges=10)
    # Range A1:A20 has 20 cells <= 100, but 20 edges > max_edges 10
    graph.add_formula("Sheet1!B1", "=SUM(A1:A20)")
    report = graph.analyze()

    assert report.is_complete is False
    assert "Sheet1!A1:A20" in graph.nodes
    assert graph.nodes["Sheet1!A1:A20"].node_type == DependencyNodeType.RANGE
    assert any("exceed maximum edges limit" in r for r in report.incompleteness_reasons)

