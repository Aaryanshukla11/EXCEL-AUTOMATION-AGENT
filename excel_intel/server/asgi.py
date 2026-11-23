"""ASGI application entry point for Uvicorn / Gunicorn."""

from excel_intel.server.app import create_app

# Default application instance for ASGI servers
app = create_app()
