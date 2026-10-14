"""Authenticated HTTP/MCP facade for the Phase 1 real local workflow."""

from .app import Credentials, Service, ServiceConfig, ServiceError
from .transport import Phase1RealServiceServer, serve

__all__ = [
    "Credentials",
    "Phase1RealServiceServer",
    "Service",
    "ServiceConfig",
    "ServiceError",
    "serve",
]
