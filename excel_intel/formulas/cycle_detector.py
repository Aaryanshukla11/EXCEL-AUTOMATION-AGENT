"""Tarjan's Strongly Connected Components (SCC) Cycle Detector for Formula Calculation Graphs (M05).

Detects direct and transitive circular references in directed formula calculation graphs,
reconstructing exact cycle paths while bounding execution complexity to O(|V| + |E|).
Uses an iterative call-stack simulation to guarantee recursion safety on deep dependency graphs.
"""

from __future__ import annotations

from typing import Any, Optional


class CycleDetector:
    """Detects cycles in directed graphs using Tarjan's SCC algorithm (iterative implementation)."""

    def __init__(self, adjacency: dict[str, set[str]]) -> None:
        """Initialize with directed adjacency list where edge (u -> v) means v depends on u."""
        self.adjacency = {k: set(v) for k, v in adjacency.items()}
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

        # Run iterative Tarjan's SCC across all graph nodes in deterministic sorted order
        for node in sorted(all_nodes):
            if node not in self._indices:
                self._strongconnect_iterative(node)

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

    def get_sccs(self) -> list[list[str]]:
        """Return all strongly connected components discovered in the graph."""
        if not self._sccs:
            self.find_cycles()
        return list(self._sccs)

    def _strongconnect_iterative(self, start_node: str) -> None:
        """Iterative implementation of Tarjan's SCC to avoid recursion-depth limits on large graphs."""
        # Call frame: [node, sorted_neighbors_iterator]
        call_stack: list[tuple[str, Any]] = []

        self._indices[start_node] = self._index
        self._lowlink[start_node] = self._index
        self._index += 1
        self._stack.append(start_node)
        self._on_stack[start_node] = True

        call_stack.append((start_node, iter(sorted(self.adjacency.get(start_node, set())))))

        while call_stack:
            u, it = call_stack[-1]
            try:
                v = next(it)
                if v not in self._indices:
                    self._indices[v] = self._index
                    self._lowlink[v] = self._index
                    self._index += 1
                    self._stack.append(v)
                    self._on_stack[v] = True
                    call_stack.append((v, iter(sorted(self.adjacency.get(v, set())))))
                elif self._on_stack.get(v, False):
                    self._lowlink[u] = min(self._lowlink[u], self._indices[v])
            except StopIteration:
                call_stack.pop()
                if call_stack:
                    parent = call_stack[-1][0]
                    self._lowlink[parent] = min(self._lowlink[parent], self._lowlink[u])

                if self._lowlink[u] == self._indices[u]:
                    scc: list[str] = []
                    while True:
                        w = self._stack.pop()
                        self._on_stack[w] = False
                        scc.append(w)
                        if w == u:
                            break
                    self._sccs.append(scc)

    def _reconstruct_cycle_path(self, scc: list[str]) -> Optional[list[str]]:
        """Reconstruct a representative closed cycle path within a strongly connected component."""
        scc_set = set(scc)
        start_node = scc[0]

        from collections import deque
        for neighbor in sorted(self.adjacency.get(start_node, set())):
            if neighbor not in scc_set:
                continue
            if neighbor == start_node:
                return [start_node, start_node]
            # BFS from neighbor to start_node to find shortest cycle containing start_node
            queue = deque([(neighbor, [start_node, neighbor])])
            visited = {start_node, neighbor}
            while queue:
                curr, path = queue.popleft()
                if start_node in self.adjacency.get(curr, set()):
                    return path + [start_node]
                for next_n in sorted(self.adjacency.get(curr, set())):
                    if next_n in scc_set and next_n not in visited:
                        visited.add(next_n)
                        queue.append((next_n, path + [next_n]))

        # Fallback: connect consecutive nodes in SCC order
        return scc + [scc[0]]
