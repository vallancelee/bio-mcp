"""
Unit tests for error handling functionality.
"""


import pytest
from mcp.types import TextContent

from bio_mcp.shared.core.error_handling import (
    ErrorCode,
    MCPError,
    NotFoundError,
    ValidationError,
    error_boundary,
    validate_tool_arguments,
)


class TestErrorCode:
    """Test ErrorCode enum."""
    
    def test_error_codes_exist(self):
        """Test that all expected error codes exist."""
        assert ErrorCode.VALIDATION == "VALIDATION"
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.RATE_LIMIT == "RATE_LIMIT"
        assert ErrorCode.UPSTREAM == "UPSTREAM"
        assert ErrorCode.INVARIANT_FAILURE == "INVARIANT_FAILURE"
        assert ErrorCode.STORE == "STORE"
        assert ErrorCode.EMBEDDINGS == "EMBEDDINGS"
        assert ErrorCode.WEAVIATE == "WEAVIATE"
        assert ErrorCode.ENTREZ == "ENTREZ"
        assert ErrorCode.UNKNOWN == "UNKNOWN"
    
    def test_error_code_string_inheritance(self):
        """Test that ErrorCode inherits from str."""
        assert isinstance(ErrorCode.VALIDATION, str)
        assert ErrorCode.VALIDATION.value == "VALIDATION"


class TestMCPError:
    """Test MCPError base exception."""
    
    def test_basic_error_creation(self):
        """Test creating a basic MCP error."""
        error = MCPError("Something went wrong")
        
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.code == ErrorCode.UNKNOWN
        assert error.details == {}
    
    def test_error_with_code(self):
        """Test creating error with specific code."""
        error = MCPError("Validation failed", ErrorCode.VALIDATION)
        
        assert error.message == "Validation failed"
        assert error.code == ErrorCode.VALIDATION
        assert error.details == {}
    
    def test_error_with_details(self):
        """Test creating error with details."""
        details = {"field": "query", "value": "", "constraint": "non-empty"}
        error = MCPError("Invalid query", ErrorCode.VALIDATION, details)
        
        assert error.message == "Invalid query"
        assert error.code == ErrorCode.VALIDATION
        assert error.details == details
    
    def test_to_error_response(self):
        """Test converting error to response format."""
        details = {"field": "limit", "max_value": 100}
        error = MCPError("Limit exceeded", ErrorCode.RATE_LIMIT, details)
        
        response = error.to_error_response()
        
        expected = {
            "error": {
                "code": "RATE_LIMIT",
                "message": "Limit exceeded",
                "details": {"field": "limit", "max_value": 100}
            }
        }
        assert response == expected
    
    def test_to_error_response_minimal(self):
        """Test converting minimal error to response format."""
        error = MCPError("Basic error")
        
        response = error.to_error_response()
        
        expected = {
            "error": {
                "code": "UNKNOWN",
                "message": "Basic error",
                "details": {}
            }
        }
        assert response == expected


class TestValidationError:
    """Test ValidationError subclass."""
    
    def test_validation_error_creation(self):
        """Test creating a validation error."""
        error = ValidationError("Invalid input format")
        
        assert error.message == "Invalid input format"
        assert error.code == ErrorCode.VALIDATION
        assert error.details == {}
    
    def test_validation_error_with_details(self):
        """Test validation error with details."""
        details = {"field": "email", "pattern": "email_format"}
        error = ValidationError("Invalid email format", details)
        
        assert error.message == "Invalid email format"
        assert error.code == ErrorCode.VALIDATION
        assert error.details == details
    
    def test_validation_error_inheritance(self):
        """Test that ValidationError inherits from MCPError."""
        error = ValidationError("Test error")
        
        assert isinstance(error, MCPError)
        assert isinstance(error, ValidationError)


class TestNotFoundError:
    """Test NotFoundError subclass."""
    
    def test_not_found_error_creation(self):
        """Test creating a not found error."""
        error = NotFoundError("Resource not found")
        
        assert error.message == "Resource not found"
        assert error.code == ErrorCode.NOT_FOUND
        assert error.details == {}
    
    def test_not_found_error_with_details(self):
        """Test not found error with details."""
        details = {"resource_type": "document", "id": "pubmed:12345"}
        error = NotFoundError("Document not found", details)
        
        assert error.message == "Document not found"
        assert error.code == ErrorCode.NOT_FOUND
        assert error.details == details
    
    def test_not_found_error_inheritance(self):
        """Test that NotFoundError inherits from MCPError."""
        error = NotFoundError("Test error")
        
        assert isinstance(error, MCPError)
        assert isinstance(error, NotFoundError)


class TestErrorBoundary:
    """Test error_boundary decorator."""
    
    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Test error boundary with successful async function."""
        @error_boundary()
        async def successful_function(value: int) -> int:
            return value * 2
        
        result = await successful_function(5)
        assert result == 10
    
    def test_sync_function_success(self):
        """Test error boundary with successful sync function."""
        @error_boundary()
        def successful_function(value: int) -> int:
            return value * 2
        
        result = successful_function(5)
        assert result == 10
    
    @pytest.mark.asyncio
    async def test_async_function_mcp_error(self):
        """Test error boundary with MCP error in async function."""
        @error_boundary()
        async def failing_function():
            raise ValidationError("Invalid input")
        
        with pytest.raises(ValidationError) as exc_info:
            await failing_function()
        
        assert exc_info.value.message == "Invalid input"
        assert exc_info.value.code == ErrorCode.VALIDATION
    
    def test_sync_function_mcp_error(self):
        """Test error boundary with MCP error in sync function."""
        @error_boundary()
        def failing_function():
            raise NotFoundError("Resource not found")
        
        with pytest.raises(NotFoundError) as exc_info:
            failing_function()
        
        assert exc_info.value.message == "Resource not found"
        assert exc_info.value.code == ErrorCode.NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_async_function_value_error(self):
        """Test error boundary with ValueError in async function."""
        @error_boundary()
        async def failing_function():
            raise ValueError("Invalid value provided")
        
        with pytest.raises(ValidationError) as exc_info:
            await failing_function()
        
        assert exc_info.value.message == "Invalid value provided"
        assert exc_info.value.code == ErrorCode.VALIDATION
    
    def test_sync_function_value_error(self):
        """Test error boundary with ValueError in sync function."""
        @error_boundary()
        def failing_function():
            raise ValueError("Invalid value provided")
        
        with pytest.raises(ValidationError) as exc_info:
            failing_function()
        
        assert exc_info.value.message == "Invalid value provided"
        assert exc_info.value.code == ErrorCode.VALIDATION
    
    @pytest.mark.asyncio
    async def test_async_function_unexpected_error(self):
        """Test error boundary with unexpected error in async function."""
        @error_boundary(fallback_message="Operation failed")
        async def failing_function():
            raise RuntimeError("Unexpected runtime error")
        
        with pytest.raises(MCPError) as exc_info:
            await failing_function()
        
        assert "Operation failed" in exc_info.value.message
        assert "Error ID:" in exc_info.value.message
        assert exc_info.value.code == ErrorCode.UNKNOWN
        assert "error_id" in exc_info.value.details
        assert exc_info.value.details["original_error"] == "Unexpected runtime error"
    
    def test_sync_function_unexpected_error(self):
        """Test error boundary with unexpected error in sync function."""
        @error_boundary(fallback_message="Operation failed")
        def failing_function():
            raise KeyError("Missing key")
        
        with pytest.raises(MCPError) as exc_info:
            failing_function()
        
        assert "Operation failed" in exc_info.value.message
        assert "Error ID:" in exc_info.value.message
        assert exc_info.value.code == ErrorCode.UNKNOWN
        assert "error_id" in exc_info.value.details
        # The original error is converted to string, so it includes quotes for string values
        assert "Missing key" in exc_info.value.details["original_error"]
    
    @pytest.mark.asyncio
    async def test_async_return_error_response_mcp_error(self):
        """Test returning error response for MCP error."""
        @error_boundary(return_error_response=True)
        async def failing_function():
            raise ValidationError("Invalid input format")
        
        result = await failing_function()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"
        assert result[0].text == "Error: Invalid input format"
    
    @pytest.mark.asyncio
    async def test_async_return_error_response_value_error(self):
        """Test returning error response for ValueError."""
        @error_boundary(return_error_response=True)
        async def failing_function():
            raise ValueError("Bad value")
        
        result = await failing_function()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"
        assert result[0].text == "Validation error: Bad value"
    
    @pytest.mark.asyncio
    async def test_async_return_error_response_unexpected_error(self):
        """Test returning error response for unexpected error."""
        @error_boundary(return_error_response=True, fallback_message="System error")
        async def failing_function():
            raise RuntimeError("System failure")
        
        result = await failing_function()
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"
        assert "System error" in result[0].text
        assert "Error ID:" in result[0].text
    
    def test_error_boundary_preserves_function_metadata(self):
        """Test that error boundary preserves function name and docs."""
        @error_boundary()
        def test_function():
            """This is a test function."""
            return "success"
        
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "This is a test function."


class TestValidateToolArguments:
    """Test validate_tool_arguments function."""
    
    def test_valid_arguments(self):
        """Test validation with valid arguments."""
        schema = {
            "required": ["query", "limit"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"}
            }
        }
        arguments = {"query": "cancer research", "limit": 10}
        
        # Should not raise an error
        validate_tool_arguments("search_tool", arguments, schema)
    
    def test_missing_required_field(self):
        """Test validation with missing required field."""
        schema = {
            "required": ["query", "limit"],
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"}
            }
        }
        arguments = {"query": "cancer research"}  # Missing 'limit'
        
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_arguments("search_tool", arguments, schema)
        
        assert "Missing required field 'limit'" in exc_info.value.message
        assert exc_info.value.details["tool"] == "search_tool"
        assert exc_info.value.details["missing_field"] == "limit"
        assert "query" in exc_info.value.details["provided_fields"]
    
    def test_unexpected_fields_not_allowed(self):
        """Test validation with unexpected fields when not allowed."""
        schema = {
            "required": ["query"],
            "properties": {
                "query": {"type": "string"}
            },
            "additionalProperties": False
        }
        arguments = {"query": "cancer", "extra_field": "unexpected"}
        
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_arguments("search_tool", arguments, schema)
        
        assert "Unexpected fields" in exc_info.value.message
        assert "extra_field" in exc_info.value.message
        assert exc_info.value.details["tool"] == "search_tool"
        assert "extra_field" in exc_info.value.details["unexpected_fields"]
    
    def test_unexpected_fields_allowed(self):
        """Test validation with unexpected fields when allowed."""
        schema = {
            "required": ["query"],
            "properties": {
                "query": {"type": "string"}
            },
            "additionalProperties": True  # Explicitly allow extra fields
        }
        arguments = {"query": "cancer", "extra_field": "allowed"}
        
        # Should not raise an error
        validate_tool_arguments("search_tool", arguments, schema)
    
    def test_unexpected_fields_default_allowed(self):
        """Test validation with unexpected fields when additionalProperties not specified."""
        schema = {
            "required": ["query"],
            "properties": {
                "query": {"type": "string"}
            }
            # additionalProperties defaults to True
        }
        arguments = {"query": "cancer", "extra_field": "allowed"}
        
        # Should not raise an error
        validate_tool_arguments("search_tool", arguments, schema)
    
    def test_string_type_validation_invalid(self):
        """Test string type validation with invalid type."""
        schema = {
            "required": ["query"],
            "properties": {
                "query": {"type": "string"}
            }
        }
        arguments = {"query": 12345}  # Should be string
        
        with pytest.raises(ValidationError) as exc_info:
            validate_tool_arguments("search_tool", arguments, schema)
        
        assert "must be a string" in exc_info.value.message
        assert "got int" in exc_info.value.message
        assert exc_info.value.details["field"] == "query"
        assert exc_info.value.details["expected"] == "string"
        assert exc_info.value.details["got"] == "int"
    
    def test_string_type_validation_none_allowed(self):
        """Test string type validation allows None for optional fields."""
        schema = {
            "properties": {
                "optional_field": {"type": "string"}
            }
        }
        arguments = {"optional_field": None}
        
        # Should not raise an error - None is allowed for optional fields
        validate_tool_arguments("search_tool", arguments, schema)
    
    def test_minimal_schema(self):
        """Test validation with minimal schema."""
        schema = {}  # No requirements or properties
        arguments = {"anything": "goes"}
        
        # Should not raise an error
        validate_tool_arguments("search_tool", arguments, schema)
    
    def test_empty_arguments(self):
        """Test validation with empty arguments."""
        schema = {
            "properties": {
                "optional_query": {"type": "string"}
            }
        }
        arguments = {}
        
        # Should not raise an error - no required fields
        validate_tool_arguments("search_tool", arguments, schema)
    
    def test_complex_validation_scenario(self):
        """Test complex validation scenario."""
        schema = {
            "required": ["query", "source"],
            "properties": {
                "query": {"type": "string"},
                "source": {"type": "string"},
                "limit": {"type": "integer"},
                "filters": {"type": "object"}
            },
            "additionalProperties": False
        }
        arguments = {
            "query": "immunotherapy AND cancer",
            "source": "pubmed",
            "limit": 50
        }
        
        # Should not raise an error
        validate_tool_arguments("rag_search", arguments, schema)


# Mark as unit tests
pytestmark = pytest.mark.unit