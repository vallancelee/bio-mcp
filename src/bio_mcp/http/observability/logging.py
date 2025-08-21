"""Structured JSON logging configuration."""

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import structlog
from structlog.processors import JSONRenderer, add_log_level
from structlog.stdlib import BoundLogger, LoggerFactory

# Sensitive field patterns to redact
SENSITIVE_PATTERNS = {
    "api_key": re.compile(r"(api_key|apikey|api-key)", re.IGNORECASE),
    "password": re.compile(r"(password|passwd|pwd)", re.IGNORECASE),
    "secret": re.compile(r"(secret|token|auth)", re.IGNORECASE),
    "database_url": re.compile(r"(://[^:]+:)([^@]+)(@)", re.IGNORECASE),
}


def timestamp_processor(_, __, event_dict):
    """Add ISO 8601 timestamp to log events."""
    event_dict["ts"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return event_dict


def redact_processor(_, __, event_dict):
    """Redact sensitive information from logs."""
    for key, value in event_dict.items():
        if isinstance(value, dict):
            event_dict[key] = redact_sensitive(value)
        elif isinstance(value, str):
            # Check if key name suggests sensitive data
            for pattern in SENSITIVE_PATTERNS["api_key"], SENSITIVE_PATTERNS["password"], SENSITIVE_PATTERNS["secret"]:
                if pattern.search(key):
                    event_dict[key] = "***REDACTED***"
                    break
    return event_dict


def redact_sensitive(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive information from a dictionary."""
    if not isinstance(data, dict):
        return data
    
    redacted = {}
    for key, value in data.items():
        # Check key patterns
        is_sensitive = False
        for pattern_name, pattern in SENSITIVE_PATTERNS.items():
            if pattern_name == "database_url" and pattern.search(key):
                # Special handling for database URLs
                if isinstance(value, str):
                    redacted[key] = pattern.sub(r"\1***REDACTED***\3", value)
                    is_sensitive = True
                    break
            elif pattern.search(key):
                redacted[key] = "***REDACTED***"
                is_sensitive = True
                break
        
        if not is_sensitive:
            if isinstance(value, dict):
                redacted[key] = redact_sensitive(value)
            elif isinstance(value, str) and "database_url" in key.lower():
                # Extra check for database URLs
                redacted[key] = SENSITIVE_PATTERNS["database_url"].sub(r"\1***REDACTED***\3", value)
            else:
                redacted[key] = value
    
    return redacted


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for standard logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_data = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "filename", "funcName", 
                          "levelname", "levelno", "lineno", "module", "msecs", 
                          "pathname", "process", "processName", "relativeCreated", 
                          "thread", "threadName", "getMessage", "message", "asctime"]:
                log_data[key] = value
        
        return json.dumps(log_data)


def get_structured_logger(name: str):
    """Get a structured logger instance."""
    # Configure standard logger with JSON output
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Add JSON handler
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    
    # Wrap with custom info method that accepts kwargs
    class StructuredLogger:
        def __init__(self, logger):
            self._logger = logger
        
        def info(self, msg, **kwargs):
            # Create a LogRecord with extra fields
            self._logger.info(msg, extra=kwargs)
        
        def debug(self, msg, **kwargs):
            self._logger.debug(msg, extra=kwargs)
        
        def warning(self, msg, **kwargs):
            self._logger.warning(msg, extra=kwargs)
        
        def error(self, msg, **kwargs):
            self._logger.error(msg, extra=kwargs)
    
    return StructuredLogger(logger)


def configure_logging():
    """Configure structured logging from environment."""
    log_level = os.environ.get("BIO_MCP_LOG_LEVEL", "INFO").upper()
    json_logs = os.environ.get("BIO_MCP_JSON_LOGS", "true").lower() == "true"
    redact = os.environ.get("BIO_MCP_REDACT_SENSITIVE", "true").lower() == "true"
    
    # Configure structlog
    processors = [
        timestamp_processor,
        add_log_level,
    ]
    
    if redact:
        processors.append(redact_processor)
    
    if json_logs:
        processors.append(JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=BoundLogger,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(message)s" if json_logs else "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Create a mock logger for testing
    class MockLogger:
        def __init__(self):
            self.logs = []
            self.level = getattr(logging, log_level)
        
        def debug(self, msg):
            if self.level <= logging.DEBUG:
                self.logs.append({"level": "DEBUG", "msg": msg})
        
        def info(self, msg):
            if self.level <= logging.INFO:
                self.logs.append({"level": "INFO", "msg": msg})
        
        def warning(self, msg):
            if self.level <= logging.WARNING:
                self.logs.append({"level": "WARNING", "msg": msg})
        
        def error(self, msg):
            if self.level <= logging.ERROR:
                self.logs.append({"level": "ERROR", "msg": msg})
        
        def get_logs(self):
            return self.logs
    
    return MockLogger()