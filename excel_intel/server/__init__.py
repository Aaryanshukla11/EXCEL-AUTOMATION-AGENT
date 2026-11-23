"""Server package for Autonomous Excel Intelligence Platform."""

from excel_intel.server.app import create_app
from excel_intel.server.config import ServerConfig, get_server_config

__all__ = ["create_app", "ServerConfig", "get_server_config"]
