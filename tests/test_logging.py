"""Automated tests for structured JSON-Lines logging and context binding."""

from __future__ import annotations

import io
import json
import logging

from excel_intel.logging import (
    JSONFormatter,
    LogContext,
    configure_logging,
    get_logger,
)


def test_json_formatter_structure() -> None:
    """Verifies that JSONFormatter produces valid JSON containing mandatory platform fields."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="excel_intel.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Sample log message",
        args=(),
        exc_info=None,
    )
    setattr(record, "event", "TEST_EVENT")
    setattr(record, "component", "TestComponent")
    setattr(record, "metrics", {"duration_ms": 12.5})
    setattr(record, "context", {"plan_id": "12345"})

    line = formatter.format(record)
    data = json.loads(line)

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert "trace_id" in data
    assert data["component"] == "TestComponent"
    assert data["event"] == "TEST_EVENT"
    assert data["message"] == "Sample log message"
    assert data["metrics"] == {"duration_ms": 12.5}
    assert data["context"] == {"plan_id": "12345"}


def test_structured_logger_stream_capture() -> None:
    """Verifies StructuredLogger emits JSON-Lines to the configured stream."""
    stream = io.StringIO()
    configure_logging(level="DEBUG", log_format="json", stream=stream)

    logger = get_logger("stream_test")
    logger.info(
        "TRANSACTION_COMMITTED",
        message="Transaction committed successfully.",
        context={"target": "Master.xlsx"},
        metrics={"rows": 100},
    )

    output = stream.getvalue().strip()
    assert output != ""
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["event"] == "TRANSACTION_COMMITTED"
    assert data["context"]["target"] == "Master.xlsx"
    assert data["metrics"]["rows"] == 100


def test_log_context_trace_propagation() -> None:
    """Verifies LogContext binds trace_id and span_id across nested calls."""
    stream = io.StringIO()
    configure_logging(level="DEBUG", log_format="json", stream=stream)
    logger = get_logger("context_test")

    with LogContext(trace_id="test-trace-999", span_id="span-123", component="DelCore"):
        logger.debug("STEP_ONE", message="First step")
        logger.info("STEP_TWO", message="Second step")

    lines = [json.loads(line) for line in stream.getvalue().strip().split("\n") if line]
    assert len(lines) == 2

    for entry in lines:
        assert entry["trace_id"] == "test-trace-999"
        assert entry["span_id"] == "span-123"
        assert entry["component"] == "DelCore"


def test_log_level_filtering() -> None:
    """Verifies logs below threshold are filtered out."""
    stream = io.StringIO()
    configure_logging(level="WARNING", log_format="json", stream=stream)
    logger = get_logger("filter_test")

    logger.debug("IGNORED_DEBUG")
    logger.info("IGNORED_INFO")
    logger.warning("CAPTURED_WARNING")
    logger.error("CAPTURED_ERROR")

    lines = [json.loads(line) for line in stream.getvalue().strip().split("\n") if line]
    assert len(lines) == 2
    assert lines[0]["level"] == "WARNING"
    assert lines[1]["level"] == "ERROR"
