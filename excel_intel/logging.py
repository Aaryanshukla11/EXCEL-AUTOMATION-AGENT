"""Structured contextual JSON-Lines logging system.

Adheres to Section 13.1 of the Release 1.0 System Architecture Design (SAD).
Produces parseable JSON-Lines to stderr or rotating file handlers with thread-local
trace and span tracking.
"""

from __future__ import annotations

import contextvars
import datetime
import json
import logging
import sys
import uuid
from typing import Any, Optional

# Context variables for distributed/thread-safe trace propagation
_current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default=""
)
_current_span_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "span_id", default=""
)
_current_component: contextvars.ContextVar[str] = contextvars.ContextVar(
    "component", default="ApplicationSkeleton"
)


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects conforming to the platform schema."""

    def format(self, record: logging.LogRecord) -> str:
        trace_id = getattr(record, "trace_id", "") or _current_trace_id.get()
        if not trace_id:
            trace_id = uuid.uuid4().hex

        span_id = getattr(record, "span_id", "") or _current_span_id.get()
        component = getattr(record, "component", "") or _current_component.get()

        event = getattr(record, "event", "") or record.getMessage()
        metrics = getattr(record, "metrics", {})
        context = getattr(record, "context", {})

        payload: dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "trace_id": trace_id,
            "span_id": span_id or None,
            "component": component,
            "event": event,
            "message": record.getMessage(),
            "metrics": metrics,
            "context": context,
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class StructuredLogger:
    """Convenience wrapper providing strongly-typed structured logging methods."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(
        self,
        event: str,
        *,
        message: str = "",
        component: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        self._log(
            logging.DEBUG,
            event,
            message=message,
            component=component,
            context=context,
            metrics=metrics,
        )

    def info(
        self,
        event: str,
        *,
        message: str = "",
        component: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        self._log(
            logging.INFO,
            event,
            message=message,
            component=component,
            context=context,
            metrics=metrics,
        )

    def warning(
        self,
        event: str,
        *,
        message: str = "",
        component: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        self._log(
            logging.WARNING,
            event,
            message=message,
            component=component,
            context=context,
            metrics=metrics,
        )

    def error(
        self,
        event: str,
        *,
        message: str = "",
        component: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        exc_info: Optional[bool] = None,
    ) -> None:
        self._log(
            logging.ERROR,
            event,
            message=message,
            component=component,
            context=context,
            metrics=metrics,
            exc_info=exc_info,
        )

    def _log(
        self,
        level: int,
        event: str,
        *,
        message: str = "",
        component: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        metrics: Optional[dict[str, Any]] = None,
        exc_info: Optional[bool] = None,
    ) -> None:
        if not self._logger.isEnabledFor(level):
            return

        extra = {
            "event": event,
            "component": component or _current_component.get(),
            "context": context or {},
            "metrics": metrics or {},
        }
        self._logger.log(
            level, message or event, extra=extra, exc_info=exc_info
        )


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    stream: Optional[Any] = None,
) -> None:
    """Configures the root or application logger with the platform JSON formatter."""
    root_logger = logging.getLogger("excel_intel")
    root_logger.setLevel(level.upper())

    # Remove existing handlers to prevent duplicate lines
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    dest_stream = stream or sys.stderr
    handler = logging.StreamHandler(dest_stream)

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter())
    else:
        standard_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        handler.setFormatter(logging.Formatter(standard_format))

    root_logger.addHandler(handler)


def get_logger(component_name: str) -> StructuredLogger:
    """Obtain a structured logger for a specific architecture component."""
    logger = logging.getLogger(f"excel_intel.{component_name}")
    return StructuredLogger(logger)


class LogContext:
    """Context manager for setting thread-local trace_id, span_id, and component."""

    def __init__(
        self,
        *,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        component: Optional[str] = None,
    ) -> None:
        self.trace_id = trace_id or uuid.uuid4().hex
        self.span_id = span_id or uuid.uuid4().hex[:16]
        self.component = component

        self._token_trace: Optional[contextvars.Token[str]] = None
        self._token_span: Optional[contextvars.Token[str]] = None
        self._token_comp: Optional[contextvars.Token[str]] = None

    def __enter__(self) -> LogContext:
        self._token_trace = _current_trace_id.set(self.trace_id)
        self._token_span = _current_span_id.set(self.span_id)
        if self.component:
            self._token_comp = _current_component.set(self.component)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._token_trace:
            _current_trace_id.reset(self._token_trace)
        if self._token_span:
            _current_span_id.reset(self._token_span)
        if self._token_comp:
            _current_component.reset(self._token_comp)
