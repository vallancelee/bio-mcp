"""Error envelope and classification system for HTTP adapter."""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ErrorCode(Enum):
    """Standardized error codes for HTTP responses."""
    
    # Tool-related errors
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    
    # Request validation errors  
    VALIDATION_ERROR = "VALIDATION_ERROR"
    
    # External service errors
    WEAVIATE_TIMEOUT = "WEAVIATE_TIMEOUT"
    WEAVIATE_CONNECTION_ERROR = "WEAVIATE_CONNECTION_ERROR"
    
    PUBMED_TIMEOUT = "PUBMED_TIMEOUT"
    PUBMED_CONNECTION_ERROR = "PUBMED_CONNECTION_ERROR"
    PUBMED_RATE_LIMIT = "PUBMED_RATE_LIMIT"
    
    DATABASE_ERROR = "DATABASE_ERROR"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"
    
    # Generic network/connection errors
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"


class ErrorEnvelope(BaseModel):
    """Standardized error response envelope."""
    
    ok: bool = False
    error_code: str
    message: str
    trace_id: str
    tool: str | None = None
    context: dict[str, Any] | None = None
    exception: str | None = None


def classify_exception(exc: Exception, tool_name: str) -> ErrorCode:
    """Classify an exception into a standardized error code.
    
    Args:
        exc: The exception to classify
        tool_name: Name of the tool that raised the exception
        
    Returns:
        Appropriate ErrorCode for the exception
    """
    exc_type = type(exc).__name__
    exc_message = str(exc).lower()
    
    # Type-based classification
    if isinstance(exc, TypeError):
        return ErrorCode.VALIDATION_ERROR
    
    # Import-specific error handling (avoid hard imports for optional dependencies)
    if exc_type in ("ConnectionError", "ConnectTimeout", "ConnectError"):
        # Check tool context for specific service
        if tool_name.startswith("pubmed."):
            return ErrorCode.PUBMED_CONNECTION_ERROR
        return ErrorCode.CONNECTION_ERROR
    
    if exc_type in ("Timeout", "TimeoutError", "ReadTimeout"):
        # Context-specific timeout classification
        if tool_name.startswith("pubmed."):
            return ErrorCode.PUBMED_TIMEOUT
        elif tool_name.startswith("rag."):
            return ErrorCode.WEAVIATE_TIMEOUT
        return ErrorCode.TIMEOUT_ERROR
    
    # Message-based classification for more specific errors
    if "rate limit" in exc_message or "429" in exc_message:
        if tool_name.startswith("pubmed."):
            return ErrorCode.PUBMED_RATE_LIMIT
    
    if "weaviate" in exc_message or "vector" in exc_message:
        if "timeout" in exc_message:
            return ErrorCode.WEAVIATE_TIMEOUT
        return ErrorCode.WEAVIATE_CONNECTION_ERROR
    
    if any(db_term in exc_message for db_term in ["database", "sql", "connection pool"]):
        if "timeout" in exc_message:
            return ErrorCode.DATABASE_TIMEOUT
        return ErrorCode.DATABASE_ERROR
    
    # Default fallback
    return ErrorCode.TOOL_EXECUTION_ERROR


def sanitize_error_message(message: str) -> str:
    """Sanitize error message to remove potentially sensitive information.
    
    Args:
        message: Original error message
        
    Returns:
        Sanitized error message
    """
    # Remove common sensitive patterns
    patterns_to_remove = [
        r'password=\S+',
        r'token=\S+', 
        r'key=\S+',
        r'secret=\S+',
        r'auth=\S+',
    ]
    
    sanitized = message
    for pattern in patterns_to_remove:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    return sanitized


def create_error_envelope(
    error_code: ErrorCode,
    message: str,
    trace_id: str,
    tool_name: str | None = None,
    context: dict[str, Any] | None = None,
    exception: Exception | None = None
) -> ErrorEnvelope:
    """Create a standardized error envelope.
    
    Args:
        error_code: The error code enum
        message: Error message (will be sanitized)
        trace_id: Request trace ID
        tool_name: Optional tool name that caused the error
        context: Optional additional context information
        exception: Optional original exception for debugging
        
    Returns:
        ErrorEnvelope instance
    """
    sanitized_message = sanitize_error_message(message)
    
    envelope = ErrorEnvelope(
        error_code=error_code.value,
        message=sanitized_message,
        trace_id=trace_id,
        tool=tool_name,
        context=context
    )
    
    # Add exception info for debugging (in non-production)
    if exception:
        envelope.exception = f"{type(exception).__name__}: {exception!s}"
    
    return envelope