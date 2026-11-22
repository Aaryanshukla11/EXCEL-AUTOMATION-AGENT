"""Unit tests for M05 Formula Cycle Detection and Status Guards.

Validates Tarjan's SCC cycle detection, direct self-loops, direct range containment
circular references, acyclic graphs, and the FR-5.2 Incomplete Graph Invariant
(preventing premature claims of NO_CYCLES when dependencies are incomplete).
"""

import pytest

from excel_intel.formulas.cycle_detector import CycleDetector
from excel_intel.formulas.graph import (
    CycleStatus,
    FormulaDependencyGraph,
)


def test_tarjan_scc_standalone_cycle_detection() -> None:
    """Test CycleDetector on simple circular dependency graph."""
    # A -> B -> C -> A
    adj = {
        "A": {"B"},
        "B": {"C"},
        "C": {"A"},
    }
    detector = CycleDetector(adj)
    cycles = detector.find_cycles()
    assert len(cycles) == 1
    # Check that cycle starts and ends at same node
    path = cycles[0]
    assert path[0] == path[-1]
    assert set(path[:-1]) == {"A", "B", "C"}


def test_acyclic_dag_no_cycles() -> None:
    """Test fully resolved acyclic graph produces NO_CYCLES."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!C1", "=A1 + B1")
    graph.add_formula("Sheet1!D1", "=C1 * 2")
    graph.add_formula("Sheet1!E1", "=D1 + A1")

    report = graph.analyze()
    assert report.has_cycles is False
    assert report.cycle_status == CycleStatus.NO_CYCLES
    assert report.is_complete is True
    assert len(report.circular_paths) == 0


def test_direct_self_loop_cycle() -> None:
    """Test direct circular reference A1 = A1."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A1", "=A1 + 1")

    report = graph.analyze()
    assert report.has_cycles is True
    assert report.cycle_status == CycleStatus.CYCLES_DETECTED
    assert len(report.circular_paths) > 0


def test_direct_range_containment_cycle() -> None:
    """Test direct range containment cycle: formula cell inside referenced range (FR-5.1)."""
    # Sheet1!A5 is inside range Sheet1!A1:A10
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A5", "=SUM(A1:A10)")

    report = graph.analyze()
    assert report.has_cycles is True
    assert report.cycle_status == CycleStatus.CYCLES_DETECTED
    assert len(report.circular_paths) > 0


def test_indirect_transitive_cycle() -> None:
    """Test transitive cycle: A1 depends on B1, B1 depends on C1, C1 depends on A1."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A1", "=B1 * 2")
    graph.add_formula("Sheet1!B1", "=C1 - 5")
    graph.add_formula("Sheet1!C1", "=A1 + 10")

    report = graph.analyze()
    assert report.has_cycles is True
    assert report.cycle_status == CycleStatus.CYCLES_DETECTED
    assert len(report.circular_paths) > 0


def test_incomplete_graph_invariant_unparsed_formula() -> None:
    """FR-5.2: Incomplete graph with unparsed formula CANNOT claim NO_CYCLES."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A1", "=B1 + 1")
    # Malformed syntax in Sheet1!C1
    graph.add_formula("Sheet1!C1", "=(D1 + * 2")

    report = graph.analyze()
    assert report.is_complete is False
    assert len(report.unparsed_cells) == 1
    # Even though A1 and B1 have no cycles, status MUST NOT be NO_CYCLES
    assert report.has_cycles is False
    assert report.cycle_status == CycleStatus.UNCERTAIN_INCOMPLETE_DEPENDENCIES


def test_incomplete_graph_invariant_unsupported_syntax() -> None:
    """FR-5.2: Incomplete graph with unsupported syntax CANNOT claim NO_CYCLES."""
    graph = FormulaDependencyGraph()
    graph.add_formula("Sheet1!A1", "=B1 + 1")
    # Unsupported dynamic spill in Sheet1!C1
    graph.add_formula("Sheet1!C1", "=D1#")

    report = graph.analyze()
    assert report.is_complete is False
    assert len(report.unsupported_cells) == 1
    assert report.cycle_status == CycleStatus.UNCERTAIN_INCOMPLETE_DEPENDENCIES


def test_incomplete_graph_with_confirmed_cycles() -> None:
    """If confirmed cycles exist in an incomplete graph, status is still CYCLES_DETECTED."""
    graph = FormulaDependencyGraph()
    # Confirmed cycle: A1 <-> B1
    graph.add_formula("Sheet1!A1", "=B1 + 1")
    graph.add_formula("Sheet1!B1", "=A1 + 2")
    # Also an unsupported syntax formula
    graph.add_formula("Sheet1!C1", "=D1#")

    report = graph.analyze()
    assert report.is_complete is False
    assert report.has_cycles is True
    assert report.cycle_status == CycleStatus.CYCLES_DETECTED


def test_iterative_tarjan_deep_chain_acyclic() -> None:
    """Verify iterative Tarjan SCC handles deep graph (>1000 nodes) without RecursionError."""
    # Acyclic chain of 1,500 nodes: N0 -> N1 -> ... -> N1499
    depth = 1500
    adj: dict[str, set[str]] = {}
    for i in range(depth - 1):
        adj[f"N{i}"] = {f"N{i + 1}"}

    detector = CycleDetector(adj)
    cycles = detector.find_cycles()
    assert len(cycles) == 0


def test_iterative_tarjan_deep_chain_cycle() -> None:
    """Verify iterative Tarjan SCC handles deep cycle (>1000 nodes) and reconstructs path."""
    # Circular chain of 1,500 nodes: N0 -> N1 -> ... -> N1499 -> N0
    depth = 1500
    adj: dict[str, set[str]] = {}
    for i in range(depth - 1):
        adj[f"N{i}"] = {f"N{i + 1}"}
    adj[f"N{depth - 1}"] = {"N0"}

    detector = CycleDetector(adj)
    cycles = detector.find_cycles()
    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle[0] == cycle[-1]
    assert len(cycle) == depth + 1

