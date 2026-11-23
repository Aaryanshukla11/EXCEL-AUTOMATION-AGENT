"""Routers package for API v1."""

from excel_intel.server.routers.health import router as health_router
from excel_intel.server.routers.workbooks import router as workbooks_router

__all__ = ["health_router", "workbooks_router"]
