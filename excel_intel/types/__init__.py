"""M05 Semantic Type Inference Package.

Exposes domain-agnostic semantic type inference, fine-grained pattern detection,
deterministic 2D sampling, and explicit inference states for tabular spatial regions.
"""

from excel_intel.types.models import (
    ColumnTypeProfile,
    InferenceState,
    NormalizedValue,
    RegionTypeReport,
    SamplingDiagnostics,
    ValueCategory,
)
from excel_intel.types.pattern_detector import PatternDetector
from excel_intel.types.sampling import (
    MAX_CELL_BUDGET,
    sample_body_coordinates,
    select_3band_indices,
)
from excel_intel.types.type_inferrer import TypeInferenceEngine

__all__ = [
    "InferenceState",
    "ValueCategory",
    "NormalizedValue",
    "SamplingDiagnostics",
    "ColumnTypeProfile",
    "RegionTypeReport",
    "PatternDetector",
    "MAX_CELL_BUDGET",
    "select_3band_indices",
    "sample_body_coordinates",
    "TypeInferenceEngine",
]
