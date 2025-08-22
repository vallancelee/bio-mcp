"""Tests for structured JSON logging and metrics collection (T5)."""

import asyncio
import json
from datetime import datetime

import pytest


class TestStructuredLogging:
    """Test structured JSON logging output and configuration."""

    def test_json_log_format(self, capsys):
        """Test that logs are valid JSON with required fields."""
        from bio_mcp.http.observability.logging import get_structured_logger

        logger = get_structured_logger("test")
        trace_id = "550e8400-e29b-41d4-a716-446655440000"

        logger.info(
            "Tool invocation completed",
            trace_id=trace_id,
            tool="rag.search",
            latency_ms=145.3,
            status="success",
        )

        # Capture stderr output
        captured = capsys.readouterr()
        assert captured.err  # Should have stderr output

        # Parse as JSON
        log_data = json.loads(captured.err.strip())

        # Verify required fields
        assert "ts" in log_data
        assert "level" in log_data
        assert log_data["level"] == "INFO"
        assert log_data["msg"] == "Tool invocation completed"
        assert log_data["trace_id"] == trace_id
        assert log_data["tool"] == "rag.search"
        assert log_data["latency_ms"] == 145.3
        assert log_data["status"] == "success"

        # Verify timestamp format (ISO 8601)
        datetime.fromisoformat(log_data["ts"].replace("Z", "+00:00"))

    def test_trace_id_propagation(self):
        """Test trace_id flows through async operations."""
        from bio_mcp.http.observability.context import TraceContext
        from bio_mcp.http.observability.logging import get_structured_logger

        logger = get_structured_logger("test")
        trace_id = "test-trace-123"

        with TraceContext(trace_id) as ctx:
            logger.info("Operation started")

            # Simulate nested operation
            with ctx.span("database_query"):
                logger.info("Querying database")

            logger.info("Operation completed")

        # All logs should have the same trace_id
        logs = ctx.get_logs()
        assert all(log.get("trace_id") == trace_id for log in logs)

    def test_sensitive_data_redaction(self):
        """Test API keys and passwords are redacted from logs."""
        from bio_mcp.http.observability.logging import (
            get_structured_logger,
            redact_sensitive,
        )

        _logger = get_structured_logger("test")

        sensitive_data = {
            "api_key": "sk-1234567890abcdef",
            "password": "super_secret_123",
            "database_url": "postgresql://user:pass@localhost/db",
            "safe_field": "this is okay to log",
        }

        redacted = redact_sensitive(sensitive_data)

        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["password"] == "***REDACTED***"
        assert "pass" not in redacted["database_url"]
        assert redacted["safe_field"] == "this is okay to log"

    def test_log_level_configuration(self):
        """Test log level filtering from environment."""
        import os

        from bio_mcp.http.observability.logging import configure_logging

        # Test different log levels
        os.environ["BIO_MCP_LOG_LEVEL"] = "WARNING"
        logger = configure_logging()

        # Debug and info should not appear
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Only warning and error should be logged
        logs = logger.get_logs()
        assert len(logs) == 2
        assert logs[0]["level"] == "WARNING"
        assert logs[1]["level"] == "ERROR"


class TestMetricsCollection:
    """Test metrics collection and aggregation."""

    def test_request_counter_increments(self):
        """Test request counters increment correctly per tool."""
        from bio_mcp.http.observability.metrics import MetricsCollector

        collector = MetricsCollector()

        # Simulate requests
        collector.increment_request("rag.search", "success")
        collector.increment_request("rag.search", "success")
        collector.increment_request("rag.search", "error")
        collector.increment_request("pubmed.sync", "success")

        # Check counters
        metrics = collector.get_metrics()
        assert metrics["bio_mcp_requests_total"]["rag.search"]["success"] == 2
        assert metrics["bio_mcp_requests_total"]["rag.search"]["error"] == 1
        assert metrics["bio_mcp_requests_total"]["pubmed.sync"]["success"] == 1

    def test_error_counter_categorization(self):
        """Test error counters categorized by error_code."""
        from bio_mcp.http.observability.metrics import MetricsCollector

        collector = MetricsCollector()

        # Simulate different errors
        collector.increment_error("rag.search", "WEAVIATE_TIMEOUT")
        collector.increment_error("rag.search", "WEAVIATE_TIMEOUT")
        collector.increment_error("pubmed.sync", "RATE_LIMIT")
        collector.increment_error("pubmed.sync", "NETWORK_ERROR")

        # Check error counters
        metrics = collector.get_metrics()
        assert metrics["bio_mcp_errors_total"]["rag.search"]["WEAVIATE_TIMEOUT"] == 2
        assert metrics["bio_mcp_errors_total"]["pubmed.sync"]["RATE_LIMIT"] == 1
        assert metrics["bio_mcp_errors_total"]["pubmed.sync"]["NETWORK_ERROR"] == 1

    def test_latency_histogram_buckets(self):
        """Test latency is recorded in correct histogram buckets."""
        from bio_mcp.http.observability.metrics import MetricsCollector

        collector = MetricsCollector()

        # Record various latencies
        latencies = [10, 50, 100, 200, 500, 1000, 2000, 5000]
        for latency in latencies:
            collector.record_latency("rag.search", latency)

        # Check histogram
        metrics = collector.get_metrics()
        histogram = metrics["bio_mcp_latency_ms"]["rag.search"]

        # Verify percentiles (median of [10, 50, 100, 200, 500, 1000, 2000, 5000] is between 200 and 500)
        assert 150 <= histogram["p50"] <= 500  # Median should be around 350
        assert histogram["p95"] <= 5000
        assert histogram["p99"] <= 5000
        assert histogram["count"] == len(latencies)

    def test_concurrent_gauge_tracking(self):
        """Test inflight request gauge updates correctly."""
        from bio_mcp.http.observability.metrics import MetricsCollector

        collector = MetricsCollector()

        # Start requests
        collector.increment_inflight("rag.search")
        collector.increment_inflight("rag.search")
        collector.increment_inflight("pubmed.sync")

        metrics = collector.get_metrics()
        assert metrics["bio_mcp_inflight_requests"]["rag.search"] == 2
        assert metrics["bio_mcp_inflight_requests"]["pubmed.sync"] == 1

        # Complete requests
        collector.decrement_inflight("rag.search")

        metrics = collector.get_metrics()
        assert metrics["bio_mcp_inflight_requests"]["rag.search"] == 1


class TestMetricsExport:
    """Test metrics export in various formats."""

    def test_prometheus_text_format(self):
        """Test Prometheus text format generation."""
        from bio_mcp.http.observability.metrics import (
            MetricsCollector,
            PrometheusExporter,
        )

        collector = MetricsCollector()
        exporter = PrometheusExporter(collector)

        # Add some metrics
        collector.increment_request("rag.search", "success")
        collector.record_latency("rag.search", 150.5)
        collector.increment_inflight("pubmed.sync")

        # Export to Prometheus format
        prometheus_text = exporter.export()

        # Verify format
        assert "# HELP bio_mcp_requests_total" in prometheus_text
        assert "# TYPE bio_mcp_requests_total counter" in prometheus_text
        assert (
            'bio_mcp_requests_total{tool="rag.search",status="success"} 1'
            in prometheus_text
        )

        assert "# HELP bio_mcp_latency_ms" in prometheus_text
        assert "# TYPE bio_mcp_latency_ms histogram" in prometheus_text

        assert "# HELP bio_mcp_inflight_requests" in prometheus_text
        assert "# TYPE bio_mcp_inflight_requests gauge" in prometheus_text
        assert 'bio_mcp_inflight_requests{tool="pubmed.sync"} 1' in prometheus_text

    def test_cloudwatch_emf_format(self):
        """Test CloudWatch Embedded Metric Format output."""
        from bio_mcp.http.observability.metrics import (
            CloudWatchEMFExporter,
            MetricsCollector,
        )

        collector = MetricsCollector()
        exporter = CloudWatchEMFExporter(collector, namespace="BioMCP")

        # Add metrics
        collector.increment_request("rag.search", "success")
        collector.record_latency("rag.search", 150.5)

        # Export to EMF
        emf_json = exporter.export()
        emf_data = json.loads(emf_json)

        # Verify EMF structure
        assert "_aws" in emf_data
        assert emf_data["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "BioMCP"

        metrics = emf_data["_aws"]["CloudWatchMetrics"][0]["Metrics"]
        assert any(m["Name"] == "RequestCount" for m in metrics)
        assert any(m["Name"] == "Latency" for m in metrics)

        # Verify dimensions
        dimensions = emf_data["_aws"]["CloudWatchMetrics"][0]["Dimensions"]
        assert ["Tool", "Status"] in dimensions

    def test_metrics_cardinality_limits(self):
        """Test that metrics respect cardinality limits."""
        from bio_mcp.http.observability.metrics import MetricsCollector

        collector = MetricsCollector(max_labels=100)

        # Try to create too many label combinations
        for i in range(150):
            tool = f"tool_{i}"
            collector.increment_request(tool, "success")

        # Should only track up to max_labels
        metrics = collector.get_metrics()
        total_labels = sum(
            len(tool_metrics)
            for tool_metrics in metrics["bio_mcp_requests_total"].values()
        )
        assert total_labels <= 100


class TestObservabilityIntegration:
    """Test complete observability pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_request_tracing(self):
        """Test request generates logs and metrics correctly."""
        from bio_mcp.http.observability import observe_tool_invocation
        from bio_mcp.http.observability.metrics import get_global_collector

        @observe_tool_invocation
        async def mock_tool(query: str) -> dict:
            """Mock tool for testing."""
            await asyncio.sleep(0.1)  # Simulate work
            return {"results": ["result1", "result2"]}

        # Execute tool
        _result = await mock_tool(query="test query")

        # Check metrics were recorded
        collector = get_global_collector()
        metrics = collector.get_metrics()

        assert metrics["bio_mcp_requests_total"]["mock_tool"]["success"] == 1
        assert "mock_tool" in metrics["bio_mcp_latency_ms"]
        assert metrics["bio_mcp_latency_ms"]["mock_tool"]["count"] == 1

    @pytest.mark.asyncio
    async def test_error_observability(self):
        """Test errors are logged and counted correctly."""
        from bio_mcp.http.observability import observe_tool_invocation
        from bio_mcp.http.observability.metrics import get_global_collector

        @observe_tool_invocation
        async def failing_tool() -> dict:
            """Tool that always fails."""
            raise ValueError("Simulated error")

        # Execute and expect failure
        with pytest.raises(ValueError):
            await failing_tool()

        # Check error metrics
        collector = get_global_collector()
        metrics = collector.get_metrics()

        assert metrics["bio_mcp_requests_total"]["failing_tool"]["error"] == 1
        assert metrics["bio_mcp_errors_total"]["failing_tool"]["ValueError"] == 1

    # TODO: Add metrics endpoint test when HTTP app is implemented
    # @pytest.mark.asyncio
    # async def test_metrics_endpoint(self, test_client):
    #     """Test /metrics endpoint returns valid Prometheus metrics."""
    #     response = await test_client.get("/metrics")
    #
    #     assert response.status_code == 200
    #     assert response.headers["content-type"] == "text/plain; version=0.0.4"
    #
    #     # Parse Prometheus format
    #     text = response.text
    #     assert "# HELP" in text
    #     assert "# TYPE" in text
    #     assert "bio_mcp_requests_total" in text
