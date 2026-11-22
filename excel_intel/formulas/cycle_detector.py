"""Tarjan's Strongly Connected Components (SCC) Cycle Detector for Formula Calculation Graphs (M05).

Detects direct and transitive circular references in directed formula calculation graphs,
reconstructing exact cycle paths while bounding execution complexity to O(|V| + |E|).
"""

from __future__ import annotations

from typing import Optional


class CycleDetector:
    """Detects cycles in directed graphs using Tarjan's SCC algorithm."""

    def __init__(self, adjacency: dict[str, set[str]]) -> None:
        """Initialize with directed adjacency list where edge (u -> v) means v depends on u."""
        self.adjacency = adjacency
        self._index = 0
        self._indices: dict[str, int] = {}
        self._lowlink: dict[str, int] = {}
        self._on_stack: dict[str, bool] = {}
        self._stack: list[str] = []
        self._sccs: list[list[str]] = []

    def find_cycles(self) -> list[list[str]]:
        """Find all circular reference paths in the graph.

        Returns:
            List of cycle paths, each represented as an ordered sequence of node IDs
            starting and ending at the same node, e.g. [['A1', 'B1', 'C1', 'A1']].
        """
        self._index = 0
        self._indices = {}
        self._lowlink = {}
        self._on_stack = {}
        self._stack = []
        self._sccs = []

        all_nodes = set(self.adjacency.keys())
        for targets in self.adjacency.values():
            all_nodes.update(targets)

        # Run Tarjan's SCC across all graph nodes
        for node in sorted(all_nodes):
            if node not in self._indices:
                self._strongconnect(node)

        # Extract cycle paths from non-trivial SCCs
        cycles: list[list[str]] = []
        for scc in self._sccs:
            if len(scc) > 1:
                path = self._reconstruct_cycle_path(scc)
                if path:
                    cycles.append(path)
            elif len(scc) == 1:
                node = scc[0]
                # Check for self-loop (direct circular reference)
                if node in self.adjacency.get(node, set()):
                    cycles.append([node, node])

        return cycles

    def _strongconnect(self, node: str) -> None:
        self._indices[node] = self._index
        self._lowlink[node] = self._index
        self._index += 1
        self._stack.append(node)
        self._on_stack[node] = True

        for neighbor in sorted(self.adjacency.get(node, set())):
            if neighbor not in self._indices:
                self._strongconnect(neighbor)
                self._lowlink[node] = min(self._lowlink[node], self._lowlink[neighbor])
            elif self._on_stack.get(neighbor, False):
                self._lowlink[node] = min(self._lowlink[node], self._indices[neighbor])

        if self._lowlink[node] == self._indices[node]:
            scc: list[str] = []
            while True:
                w = self._stack.pop()
                self._on_stack[w] = False
                scc.append(w)
                if w == node:
                    break
            self._sccs.append(scc)

    def _reconstruct_cycle_path(self, scc: list[str]) -> Optional[list[str]]:
        """Reconstruct a representative closed cycle path within a strongly connected component."""
        scc_set = set(scc)
        start_node = scc[0]

        visited: list[str] = []
        visited_set: set[str] = set()

        def _dfs(current: str) -> Optional[list[str]]:
            visited.append(current)
            visited_set.add(current)

            for neighbor in sorted(self.adjacency.get(current, set())):
                if neighbor not in scc_set:
                    continue
                if neighbor == start_node and len(visited) > 1:
                    return visited + [start_node]
                if neighbor not in visited_set:
                    res = _dfs(neighbor)
                    if res is not None:
                        return res

            visited.pop()
            visited_set.remove(current)
            return None

        # Try to find a simple cycle starting from start_node
        path = _dfs(start_node)
        if path:
            return path

        # Fallback: connect consecutive nodes in SCC order
        return scc + [scc[0]]
