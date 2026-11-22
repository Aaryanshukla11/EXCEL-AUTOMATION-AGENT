"""Spatial Grid & Bounding-Box Detection Subsystem (M04).

Provides 2D whitespace corridor segmentation, hierarchical header resolution,
semantic zone classification, ADR-005 append boundary sentinel evaluation,
and unified spatial detection facade.
"""

from __future__ import annotations

from excel_intel.spatial.boundary_sentinel import BoundarySentinel
from excel_intel.spatial.detector import SpatialDetector
from excel_intel.spatial.grid_segmenter import GridSegmenter
from excel_intel.spatial.header_resolver import HeaderResolver
from excel_intel.spatial.models import (
    CorridorOrientation,
    HeaderHierarchyLevel,
    HeaderResolutionReport,
    HeaderResolutionStatus,
    MarginClearance,
    RegionZone,
    RegionZoneType,
    ResolvedHeaderColumn,
    SemanticZone,
    SemanticZoneType,
    SeparationCorridor,
    SpatialAnalysisReport,
    SpatialDetectionReport,
    SpatialEvidence,
    SpatialEvidenceType,
    SpatialRegionType,
    SpatialTableRegion,
)
from excel_intel.spatial.zone_classifier import ZoneClassifier

__all__ = [
    # Facade & Engines
    "SpatialDetector",
    "GridSegmenter",
    "HeaderResolver",
    "ZoneClassifier",
    "BoundarySentinel",
    # Core Spatial Models
    "SpatialTableRegion",
    "SpatialDetectionReport",
    "SpatialAnalysisReport",
    "SeparationCorridor",
    "SpatialEvidence",
    "SpatialRegionType",
    "SpatialEvidenceType",
    "CorridorOrientation",
    # Header Models
    "HeaderResolutionReport",
    "HeaderResolutionStatus",
    "HeaderHierarchyLevel",
    "ResolvedHeaderColumn",
    # Zone & Boundary Models
    "SemanticZoneType",
    "SemanticZone",
    "RegionZoneType",
    "RegionZone",
    "MarginClearance",
]
