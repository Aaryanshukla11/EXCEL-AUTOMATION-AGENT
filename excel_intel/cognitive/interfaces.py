"""Abstract interfaces for the Cognitive Orchestrator Tier (Candidate C).

Enforces strict separation of reasoning from execution (ADR-006).
Cognitive components have zero direct access to filesystem handles,
in-memory workbook buffers, or transaction managers.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from excel_intel.core.types import DiscoveryManifest, OperationPlan


@runtime_checkable
class CognitiveOrchestratorProtocol(Protocol):
    """Protocol for single-turn semantic column mapping and plan synthesis."""

    def synthesize_plan(
        self,
        *,
        source_manifests: list[DiscoveryManifest],
        target_manifest: DiscoveryManifest,
        instruction: str,
    ) -> OperationPlan:
        """Synthesize a declarative, strongly-typed OperationPlan from discovery metadata.

        Args:
            source_manifests: Structural manifests of source workbooks.
            target_manifest: Structural manifest of the Master/target workbook.
            instruction: User-provided goal or operational instruction.

        Returns:
            Declarative OperationPlan conforming to JSON Schema Draft 2020-12.
        """
        ...
