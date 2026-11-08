"""Abstract interfaces for the Interface & Presentation Tier.

Defines protocols for side-by-side diff card rendering, candidate key conflict
escalation cards, and operator approval prompts (ADR-004, ADR-005, §8.3).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from excel_intel.core.types import OperationPlan


@runtime_checkable
class DiffPresenterProtocol(Protocol):
    """Protocol for rendering terminal diff cards and capturing operator decisions."""

    def render_diff(
        self,
        *,
        plan: OperationPlan,
        pre_state_sample: list[dict[str, Any]],
        post_state_sample: list[dict[str, Any]],
    ) -> None:
        """Render side-by-side cell before/after diff cards to terminal or stream."""
        ...

    def prompt_approval(
        self,
        *,
        plan: OperationPlan,
    ) -> bool:
        """Prompt operator for cryptographic HMAC approval confirmation."""
        ...
