"""Tests for trace context and correlation."""

import time
import uuid
from unittest.mock import patch

from bio_mcp.http.tracing import TraceContext, generate_trace_id, get_current_trace


class TestTraceGeneration:
    """Test trace ID generation."""

    def test_generate_trace_id_format(self):
        """Test that trace IDs are valid UUID4 format."""
        trace_id = generate_trace_id()

        # Should be valid UUID4
        parsed_uuid = uuid.UUID(trace_id)
        assert str(parsed_uuid) == trace_id
        assert parsed_uuid.version == 4

    def test_generate_trace_id_uniqueness(self):
        """Test that generated trace IDs are unique."""
        trace_ids = {generate_trace_id() for _ in range(100)}

        # All should be unique
        assert len(trace_ids) == 100

    def test_trace_id_string_format(self):
        """Test trace ID string format matches expected pattern."""
        trace_id = generate_trace_id()

        # Should match UUID4 pattern: 8-4-4-4-12 hex digits
        assert len(trace_id) == 36
        assert trace_id.count("-") == 4


class TestTraceContext:
    """Test trace context management."""

    def test_trace_context_creation(self):
        """Test creating trace context with required fields."""
        context = TraceContext(trace_id="test-trace-123", tool_name="test.tool")

        assert context.trace_id == "test-trace-123"
        assert context.tool_name == "test.tool"
        assert isinstance(context.start_time, float)
        assert context.start_time <= time.time()

    def test_trace_context_duration(self):
        """Test trace context duration calculation."""
        context = TraceContext("trace-123", "test.tool")
        time.sleep(0.01)  # Small delay

        duration = context.get_duration_ms()
        assert duration > 0
        assert duration < 1000  # Should be less than 1 second

    def test_trace_context_metadata(self):
        """Test adding metadata to trace context."""
        context = TraceContext("trace-456", "pubmed.search")

        context.add_metadata("query", "glioblastoma")
        context.add_metadata("limit", 10)

        assert context.metadata["query"] == "glioblastoma"
        assert context.metadata["limit"] == 10

    def test_trace_context_structured_log_data(self):
        """Test getting structured log data from trace context."""
        context = TraceContext("trace-789", "rag.search")
        context.add_metadata("search_mode", "hybrid")
        time.sleep(0.001)  # Tiny delay for duration

        log_data = context.get_structured_log_data()

        assert log_data["trace_id"] == "trace-789"
        assert log_data["tool"] == "rag.search"
        assert log_data["latency_ms"] > 0
        assert log_data["metadata"]["search_mode"] == "hybrid"

    def test_trace_context_with_error(self):
        """Test trace context error handling."""
        context = TraceContext("trace-error", "test.failing")

        error = ValueError("Test error")
        context.set_error(error)

        log_data = context.get_structured_log_data()

        assert log_data["status"] == "error"
        assert log_data["error_type"] == "ValueError"
        assert log_data["error_message"] == "Test error"

    def test_trace_context_success(self):
        """Test trace context success state."""
        context = TraceContext("trace-success", "test.working")
        context.set_success({"result": "success"})

        log_data = context.get_structured_log_data()

        assert log_data["status"] == "success"
        assert "error_type" not in log_data
        assert "error_message" not in log_data


class TestTraceContextManager:
    """Test trace context as context manager."""

    @patch("bio_mcp.http.tracing.logger")
    def test_trace_context_manager_success(self, mock_logger):
        """Test trace context manager logs on successful completion."""
        with TraceContext("trace-cm-1", "test.tool") as context:
            context.add_metadata("param", "value")
            context.set_success({"result": "ok"})

        # Should have logged completion
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args
        assert "trace_id" in call_args.kwargs
        assert call_args.kwargs["trace_id"] == "trace-cm-1"

    @patch("bio_mcp.http.tracing.logger")
    def test_trace_context_manager_error(self, mock_logger):
        """Test trace context manager logs on error."""
        try:
            with TraceContext("trace-cm-2", "test.error"):
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should have logged error
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args
        assert "trace_id" in call_args.kwargs
        assert call_args.kwargs["trace_id"] == "trace-cm-2"


class TestCurrentTraceContext:
    """Test current trace context management."""

    def test_no_current_trace_initially(self):
        """Test that no trace context exists initially."""
        current = get_current_trace()
        assert current is None

    def test_set_and_get_current_trace(self):
        """Test setting and getting current trace context."""
        context = TraceContext("trace-current", "test.tool")

        # Use the context manager to set current trace
        with context:
            current = get_current_trace()
            assert current is not None
            assert current.trace_id == "trace-current"
            assert current.tool_name == "test.tool"


class TestTraceIntegration:
    """Test trace integration scenarios."""

    @patch("bio_mcp.http.tracing.logger")
    def test_nested_trace_contexts(self, mock_logger):
        """Test that nested trace contexts work correctly."""
        # Outer context
        with TraceContext("outer-trace", "outer.tool") as outer:
            outer.add_metadata("outer", "value")

            # Inner context (simulating sub-operation)
            with TraceContext("inner-trace", "inner.tool") as inner:
                inner.add_metadata("inner", "value")
                inner.set_success({"inner": "result"})

            outer.set_success({"outer": "result"})

        # Both contexts should have logged
        assert mock_logger.info.call_count == 2

    def test_trace_correlation_data(self):
        """Test that trace context provides correlation data."""
        context = TraceContext("correlation-test", "test.correlation")
        context.add_metadata("user_id", "user123")
        context.add_metadata("request_id", "req456")

        correlation_data = context.get_correlation_data()

        assert correlation_data["trace_id"] == "correlation-test"
        assert correlation_data["tool"] == "test.correlation"
        assert correlation_data["user_id"] == "user123"
        assert correlation_data["request_id"] == "req456"
