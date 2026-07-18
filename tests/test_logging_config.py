from __future__ import annotations

import json
import logging
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.core.logging_config import JSONFormatter, configure_logging


class TestJSONFormatter:
    def test_format_produces_valid_json(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger", level=logging.INFO,
            pathname="/path/to/file.py", lineno=42,
            msg="Hello, world!", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Hello, world!"
        assert parsed["module"] == "file"
        # funcName may be None when LogRecord is constructed directly

    def test_format_includes_timestamp(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t", level=logging.DEBUG,
            pathname="test.py", lineno=1,
            msg="msg", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert "T" in parsed["timestamp"]

    def test_format_includes_line_number(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t", level=logging.WARNING,
            pathname="app.py", lineno=99,
            msg="warn", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["line"] == 99

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            record = logging.LogRecord(
                name="t", level=logging.ERROR,
                pathname="err.py", lineno=10,
                msg="An error occurred", args=(), exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["message"] == "test error"

    def test_format_without_exception_no_exception_field(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t", level=logging.INFO,
            pathname="ok.py", lineno=5,
            msg="all good", args=(), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" not in parsed

    def test_format_with_extra_data(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t", level=logging.INFO,
            pathname="extra.py", lineno=3,
            msg="with extra", args=(), exc_info=None,
        )
        record.extra_data = {"user_id": "u123", "request_id": "r456"}
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["extra"] == {"user_id": "u123", "request_id": "r456"}

    def test_format_levels(self):
        formatter = JSONFormatter()
        for level in (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL):
            record = logging.LogRecord(
                name="t", level=level,
                pathname="levels.py", lineno=1,
                msg="level test", args=(), exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["level"] == logging.getLevelName(level)

    def test_format_non_string_message(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="t", level=logging.INFO,
            pathname="num.py", lineno=1,
            msg="count: %d", args=(42,), exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "count: 42"


class TestConfigureLogging:
    def test_configure_logging_adds_handler(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        try:
            root.handlers.clear()
            configure_logging("DEBUG")
            assert len(root.handlers) == 1
            handler = root.handlers[0]
            assert isinstance(handler, logging.StreamHandler)
            assert isinstance(handler.formatter, JSONFormatter)
            assert root.level == logging.DEBUG
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_configure_logging_default_level(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        try:
            root.handlers.clear()
            configure_logging()
            assert root.level == logging.INFO
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_configure_logging_clears_existing_handlers(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        try:
            root.handlers.clear()
            root.addHandler(logging.StreamHandler())
            assert len(root.handlers) == 1
            configure_logging("INFO")
            assert len(root.handlers) == 1
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)

    def test_configure_logging_sets_third_party_levels(self):
        root = logging.getLogger()
        original_handlers = list(root.handlers)
        try:
            root.handlers.clear()
            configure_logging("INFO")
            assert logging.getLogger("uvicorn").level == logging.WARNING
            assert logging.getLogger("httpx").level == logging.WARNING
            assert logging.getLogger("neo4j").level == logging.WARNING
        finally:
            root.handlers.clear()
            for h in original_handlers:
                root.addHandler(h)
