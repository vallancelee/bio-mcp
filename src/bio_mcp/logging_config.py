"""
Structured logging configuration for Bio-MCP server.
Phase 1B: JSON logging for container environments and monitoring.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from .config import config


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hostname = None
        try:
            import socket

            self.hostname = socket.gethostname()
        except Exception:
            self.hostname = "unknown"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log structure
        log_entry = {
            "@timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
            "process": record.process,
            "hostname": self.hostname,
            "service": {"name": config.server_name, "version": config.version},
        }

        # Add build info if available
        if config.build:
            log_entry["service"]["build"] = config.build
        if config.commit:
            log_entry["service"]["commit"] = config.commit

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "message",
            }:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str, ensure_ascii=False)


class StructuredLogger:
    """Wrapper for structured logging with context."""

    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
        self._context: dict[str, Any] = {}

    def with_context(self, **kwargs) -> "StructuredLogger":
        """Return a new logger with additional context."""
        new_logger = StructuredLogger(self.logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _log(self, level: int, message: str, **kwargs):
        """Log with context and extra fields."""
        extra = {**self._context, **kwargs}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        extra = {**self._context, **kwargs}
        self.logger.exception(message, extra=extra)


def setup_logging(use_json: bool = True, level: str | None = None) -> None:
    """Set up logging configuration."""
    if level is None:
        level = config.log_level

    # Convert string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create handler - use stderr for MCP compatibility
    handler = logging.StreamHandler(sys.stderr)

    if use_json:
        # Use JSON formatter for structured logging
        formatter = JSONFormatter()
    else:
        # Use standard formatter for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    handler.setLevel(numeric_level)

    # Configure root logger
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


# Auto-configure logging based on environment
def auto_configure_logging():
    """Automatically configure logging based on environment."""
    # Use JSON logging based on environment variables or when not in a terminal
    use_json = (
        # Explicit environment variable
        os.getenv("BIO_MCP_JSON_LOGS", "").lower() in ("true", "1", "yes")
        or
        # Container environment (no TTY)
        not sys.stdout.isatty()
        or
        # Production log levels
        config.log_level in ["WARNING", "ERROR"]
    )

    setup_logging(use_json=use_json)
