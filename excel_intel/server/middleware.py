"""HTTP middleware for request correlation, structured access logging, and memory supervisor."""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from excel_intel.logging import StructuredLogger, _current_trace_id, get_logger

logger: StructuredLogger = get_logger("AccessLog")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagates or generates X-Correlation-ID for all requests and responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        header_corr_id = request.headers.get("X-Correlation-ID")
        correlation_id = header_corr_id or f"req-{uuid.uuid4().hex[:12]}"

        # Bind to request state and context variable
        request.state.correlation_id = correlation_id
        token = _current_trace_id.set(correlation_id)

        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            _current_trace_id.reset(token)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs structured JSON metrics for every HTTP interaction."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        correlation_id = getattr(request.state, "correlation_id", "unknown")

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            logger.info(
                "HttpRequestCompleted",
                message=f"{request.method} {request.url.path} -> {response.status_code}",
                context={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "client_host": request.client.host if request.client else "unknown",
                    "correlation_id": correlation_id,
                },
                metrics={"duration_ms": round(duration_ms, 2)},
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                "HttpRequestFailed",
                message=f"{request.method} {request.url.path} -> Exception: {exc}",
                context={
                    "method": request.method,
                    "path": request.url.path,
                    "client_host": request.client.host if request.client else "unknown",
                    "correlation_id": correlation_id,
                    "exception": str(exc),
                },
                metrics={"duration_ms": round(duration_ms, 2)},
            )
            from excel_intel.server.errors import unhandled_exception_handler

            return await unhandled_exception_handler(request, exc)
