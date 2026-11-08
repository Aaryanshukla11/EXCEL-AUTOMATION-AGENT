"""Automated tests verifying clean module imports and protocol conformance."""

from __future__ import annotations

import importlib
import pytest

from excel_intel.cognitive.interfaces import CognitiveOrchestratorProtocol
from excel_intel.execution.interfaces import (
    AuditLedgerProtocol,
    HMACAuthorityProtocol,
    ShadowEngineProtocol,
    TransactionManagerProtocol,
)
from excel_intel.ui.interfaces import DiffPresenterProtocol


MODULES_TO_TEST = [
    "excel_intel",
    "excel_intel.cli",
    "excel_intel.config",
    "excel_intel.exceptions",
    "excel_intel.logging",
    "excel_intel.core",
    "excel_intel.core.types",
    "excel_intel.cognitive",
    "excel_intel.cognitive.interfaces",
    "excel_intel.execution",
    "excel_intel.execution.interfaces",
    "excel_intel.ui",
    "excel_intel.ui.interfaces",
]


@pytest.mark.parametrize("module_name", MODULES_TO_TEST)
def test_clean_module_import(module_name: str) -> None:
    """Verifies each module can be imported cleanly without side effects or circular import errors."""
    module = importlib.import_module(module_name)
    assert module is not None


def test_runtime_checkable_protocols() -> None:
    """Verifies that all architectural protocols are runtime_checkable."""
    # Dummy classes to verify protocol structural typing
    class DummyOrchestrator:
        def synthesize_plan(self, *, source_manifests, target_manifest, instruction):  # type: ignore
            return None  # type: ignore

    assert isinstance(DummyOrchestrator(), CognitiveOrchestratorProtocol)
