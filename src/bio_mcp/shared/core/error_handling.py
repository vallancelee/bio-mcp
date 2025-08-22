"""
Error handling and boundaries for Bio-MCP server.
Phase 1B: Robust error handling with recovery and logging.
"""

import functools
import traceback
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar

from mcp.types import TextContent

from bio_mcp.config.logging_config import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class ErrorCode(str, Enum):
    """Standard error codes matching contracts.md"""

    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT = "RATE_LIMIT"
    UPSTREAM = "UPSTREAM"
    INVARIANT_FAILURE = "INVARIANT_FAILURE"
    STORE = "STORE"
    EMBEDDINGS = "EMBEDDINGS"
    WEAVIATE = "WEAVIATE"
    ENTREZ = "ENTREZ"
    UNKNOWN = "UNKNOWN"


class MCPError(Exception):
    """Base exception for MCP tool errors."""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_error_response(self) -> dict[str, Any]:
        """Convert to standardized error response format."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(MCPError):
    """Validation error for invalid inputs."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.VALIDATION, details)


class NotFoundError(MCPError):
    """Resource not found error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.NOT_FOUND, details)


def error_boundary(
    fallback_message: str = "An unexpected error occurred",
    log_errors: bool = True,
    return_error_response: bool = False,
):
    """
    Decorator that creates an error boundary around function execution.

    Args:
        fallback_message: Message to return if an unexpected error occurs
        log_errors: Whether to log errors (default: True)
        return_error_response: Whether to return error in MCP format
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_logger = logger.with_context(
                function=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()) if kwargs else [],
            )

            try:
                func_logger.debug("Function execution started")
                result = await func(*args, **kwargs)
                func_logger.debug("Function execution completed successfully")
                return result

            except MCPError as e:
                # Known MCP errors - log and re-raise
                func_logger.warning(
                    "MCP error occurred",
                    error_code=e.code.value,
                    error_message=e.message,
                    error_details=e.details,
                )

                if return_error_response:
                    return [TextContent(type="text", text=f"Error: {e.message}")]
                else:
                    raise

            except ValueError as e:
                # Validation-type errors
                func_logger.warning("Validation error", error_message=str(e))

                if return_error_response:
                    return [TextContent(type="text", text=f"Validation error: {e!s}")]
                else:
                    raise ValidationError(str(e))

            except Exception as e:
                # Unexpected errors
                error_id = f"error_{func.__name__}_{hash(str(e)) % 10000:04d}"

                if log_errors:
                    func_logger.error(
                        "Unexpected error in function",
                        error_id=error_id,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        traceback=traceback.format_exc(),
                    )

                if return_error_response:
                    return [
                        TextContent(
                            type="text",
                            text=f"{fallback_message} (Error ID: {error_id})",
                        )
                    ]
                else:
                    raise MCPError(
                        f"{fallback_message} (Error ID: {error_id})",
                        ErrorCode.UNKNOWN,
                        {"error_id": error_id, "original_error": str(e)},
                    )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_logger = logger.with_context(
                function=func.__name__,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()) if kwargs else [],
            )

            try:
                func_logger.debug("Function execution started")
                result = func(*args, **kwargs)
                func_logger.debug("Function execution completed successfully")
                return result

            except MCPError as e:
                func_logger.warning(
                    "MCP error occurred",
                    error_code=e.code.value,
                    error_message=e.message,
                    error_details=e.details,
                )
                raise

            except ValueError as e:
                func_logger.warning("Validation error", error_message=str(e))
                raise ValidationError(str(e))

            except Exception as e:
                error_id = f"error_{func.__name__}_{hash(str(e)) % 10000:04d}"

                if log_errors:
                    func_logger.error(
                        "Unexpected error in function",
                        error_id=error_id,
                        error_type=type(e).__name__,
                        error_message=str(e),
                        traceback=traceback.format_exc(),
                    )

                raise MCPError(
                    f"{fallback_message} (Error ID: {error_id})",
                    ErrorCode.UNKNOWN,
                    {"error_id": error_id, "original_error": str(e)},
                )

        # Return appropriate wrapper based on whether function is async
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def validate_tool_arguments(
    tool_name: str, arguments: dict[str, Any], schema: dict[str, Any]
):
    """Validate tool arguments against schema."""
    # Basic validation - can be enhanced with jsonschema later
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    # Check required fields
    for field in required:
        if field not in arguments:
            raise ValidationError(
                f"Missing required field '{field}' for tool '{tool_name}'",
                {
                    "tool": tool_name,
                    "missing_field": field,
                    "provided_fields": list(arguments.keys()),
                },
            )

    # Check additional properties
    if not schema.get("additionalProperties", True):
        extra_fields = set(arguments.keys()) - set(properties.keys())
        if extra_fields:
            raise ValidationError(
                f"Unexpected fields for tool '{tool_name}': {list(extra_fields)}",
                {"tool": tool_name, "unexpected_fields": list(extra_fields)},
            )

    # Basic type checking
    for field, value in arguments.items():
        if field in properties:
            expected_type = properties[field].get("type")
            if expected_type == "string" and not isinstance(value, str):
                if value is not None:  # Allow None for optional fields
                    raise ValidationError(
                        f"Field '{field}' must be a string, got {type(value).__name__}",
                        {
                            "tool": tool_name,
                            "field": field,
                            "expected": "string",
                            "got": type(value).__name__,
                        },
                    )
