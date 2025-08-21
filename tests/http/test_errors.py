"""Tests for error envelope and classification system."""


from bio_mcp.http.errors import (
    ErrorCode,
    ErrorEnvelope,
    classify_exception,
    create_error_envelope,
)


class TestErrorCode:
    """Test error code enumeration and classification."""
    
    def test_error_code_enum_values(self):
        """Test that error codes have expected string values."""
        assert ErrorCode.TOOL_NOT_FOUND.value == "TOOL_NOT_FOUND"
        assert ErrorCode.TOOL_EXECUTION_ERROR.value == "TOOL_EXECUTION_ERROR"
        assert ErrorCode.VALIDATION_ERROR.value == "VALIDATION_ERROR"
        assert ErrorCode.WEAVIATE_TIMEOUT.value == "WEAVIATE_TIMEOUT"
        assert ErrorCode.PUBMED_RATE_LIMIT.value == "PUBMED_RATE_LIMIT"
        assert ErrorCode.DATABASE_ERROR.value == "DATABASE_ERROR"


class TestExceptionClassification:
    """Test exception mapping to error codes."""
    
    def test_classify_value_error(self):
        """Test that ValueError maps to TOOL_EXECUTION_ERROR."""
        exc = ValueError("Invalid parameter")
        code = classify_exception(exc, "test.tool")
        assert code == ErrorCode.TOOL_EXECUTION_ERROR
    
    def test_classify_type_error(self):
        """Test that TypeError maps to VALIDATION_ERROR."""
        exc = TypeError("Wrong type")
        code = classify_exception(exc, "test.tool")
        assert code == ErrorCode.VALIDATION_ERROR
    
    def test_classify_connection_error(self):
        """Test that ConnectionError maps to appropriate code based on tool."""
        import requests
        exc = requests.ConnectionError("Connection failed")
        
        # PubMed tool
        code = classify_exception(exc, "pubmed.search")
        assert code == ErrorCode.PUBMED_CONNECTION_ERROR
        
        # Generic tool
        code = classify_exception(exc, "generic.tool")
        assert code == ErrorCode.CONNECTION_ERROR
    
    def test_classify_timeout_error(self):
        """Test timeout error classification by tool context."""
        import requests
        exc = requests.Timeout("Request timeout")
        
        # PubMed tool
        code = classify_exception(exc, "pubmed.sync")
        assert code == ErrorCode.PUBMED_TIMEOUT
        
        # Weaviate context (tool name pattern)
        code = classify_exception(exc, "rag.search")
        assert code == ErrorCode.WEAVIATE_TIMEOUT
        
        # Generic timeout
        code = classify_exception(exc, "other.tool")
        assert code == ErrorCode.TIMEOUT_ERROR
    
    def test_classify_database_errors(self):
        """Test database-related error classification."""
        # Mock SQLAlchemy errors since they might not be available in test env
        class MockSQLError(Exception):
            pass
        
        exc = MockSQLError("Database connection failed")
        code = classify_exception(exc, "corpus.checkpoint.create")
        # Should be classified as database error due to message content
        assert code == ErrorCode.DATABASE_ERROR
        
        # Test timeout variant
        exc_timeout = MockSQLError("Database connection timeout")
        code_timeout = classify_exception(exc_timeout, "corpus.checkpoint.get")
        assert code_timeout == ErrorCode.DATABASE_TIMEOUT
    
    def test_classify_unknown_exception(self):
        """Test that unknown exceptions map to TOOL_EXECUTION_ERROR."""
        class CustomError(Exception):
            pass
        
        exc = CustomError("Unknown error")
        code = classify_exception(exc, "test.tool")
        assert code == ErrorCode.TOOL_EXECUTION_ERROR


class TestErrorEnvelope:
    """Test error envelope creation and structure."""
    
    def test_create_basic_error_envelope(self):
        """Test creating basic error envelope."""
        envelope = create_error_envelope(
            error_code=ErrorCode.TOOL_NOT_FOUND,
            message="Tool 'test.tool' not found",
            trace_id="trace-123",
            tool_name="test.tool"
        )
        
        assert isinstance(envelope, ErrorEnvelope)
        assert envelope.ok is False
        assert envelope.error_code == "TOOL_NOT_FOUND"
        assert envelope.message == "Tool 'test.tool' not found"
        assert envelope.trace_id == "trace-123"
        assert envelope.tool == "test.tool"
    
    def test_create_error_envelope_without_tool(self):
        """Test creating error envelope without tool name."""
        envelope = create_error_envelope(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Invalid request format",
            trace_id="trace-456"
        )
        
        assert envelope.ok is False
        assert envelope.error_code == "VALIDATION_ERROR"
        assert envelope.message == "Invalid request format"
        assert envelope.trace_id == "trace-456"
        assert envelope.tool is None
    
    def test_error_envelope_serialization(self):
        """Test that error envelope can be serialized to dict."""
        envelope = create_error_envelope(
            error_code=ErrorCode.WEAVIATE_TIMEOUT,
            message="Weaviate request timed out",
            trace_id="trace-789",
            tool_name="rag.search"
        )
        
        data = envelope.model_dump()
        
        assert data["ok"] is False
        assert data["error_code"] == "WEAVIATE_TIMEOUT"
        assert data["message"] == "Weaviate request timed out"
        assert data["trace_id"] == "trace-789"
        assert data["tool"] == "rag.search"
    
    def test_error_envelope_with_context(self):
        """Test error envelope with additional context."""
        envelope = create_error_envelope(
            error_code=ErrorCode.PUBMED_RATE_LIMIT,
            message="PubMed rate limit exceeded",
            trace_id="trace-rate-limit",
            tool_name="pubmed.search",
            context={"retry_after": 60, "current_rate": 15}
        )
        
        assert envelope.context == {"retry_after": 60, "current_rate": 15}


class TestErrorFromException:
    """Test creating error envelopes directly from exceptions."""
    
    def test_create_envelope_from_exception(self):
        """Test creating error envelope from exception with classification."""
        exc = ValueError("Invalid query parameter")
        
        envelope = create_error_envelope(
            error_code=classify_exception(exc, "pubmed.search"),
            message=str(exc),
            trace_id="trace-exception",
            tool_name="pubmed.search",
            exception=exc
        )
        
        assert envelope.error_code == "TOOL_EXECUTION_ERROR"
        assert envelope.message == "Invalid query parameter"
        assert envelope.tool == "pubmed.search"
    
    def test_message_sanitization(self):
        """Test that error messages are sanitized for security."""
        # Test with potentially sensitive information
        sensitive_exc = ValueError("Database connection failed: password=secret123")
        
        envelope = create_error_envelope(
            error_code=ErrorCode.DATABASE_ERROR,
            message=str(sensitive_exc),
            trace_id="trace-sanitize"
        )
        
        # Message should be sanitized (this is a placeholder test)
        # In real implementation, we'd sanitize sensitive info
        assert "password=" not in envelope.message or envelope.message == "Database connection failed"